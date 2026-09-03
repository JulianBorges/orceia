# backend/modules/auditoria/services.py
"""
Pipeline de Ingestão e Consulta de Memoriais Descritivos (PDF).

Fluxo:
  PDF → pypdf → parágrafos → embeddings (text-embedding-3-small) → Pinecone
  Namespace isolado por tenant e projeto: memorial:{tenant_id}:{projeto_id}

Compatível com o Motor RRF existente (namespaces distintos — sem colisão).
"""
import asyncio
from io import BytesIO
from pypdf import PdfReader
from pinecone import Pinecone
from core.config import settings
from core.ai_client import openai_client

# Limiar mínimo de similaridade para aceitar um trecho do memorial como relevante.
# Abaixo disso, o contexto não é injetado (evita ruído semântico).
_SCORE_MINIMO_MEMORIAL = 0.65

# Tamanho máximo de caracteres por chunk (aprox. 120-200 tokens).
_TAMANHO_MAX_CHUNK = 800


def _get_pinecone_index():
    """Singleton lazy do índice Pinecone (reutiliza o mesmo índice do Motor RRF)."""
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    return pc.Index(settings.PINECONE_INDEX_NAME)


def _extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """Extrai texto de todas as páginas do PDF usando pypdf."""
    reader = PdfReader(BytesIO(conteudo_bytes))
    paginas = []
    for page in reader.pages:
        texto = page.extract_text()
        if texto and texto.strip():
            paginas.append(texto.strip())

    texto_completo = "\n\n".join(paginas)
    if not texto_completo.strip():
        raise ValueError(
            "PDF sem texto extraível. "
            "Verifique se o arquivo não é um PDF escaneado (apenas imagem)."
        )
    return texto_completo


def _chunkar_por_paragrafo(texto: str, tamanho_max: int = _TAMANHO_MAX_CHUNK) -> list[str]:
    """
    Divide o texto em chunks semânticos por parágrafo.
    Chunks muito pequenos são agrupados com o próximo para evitar vetores sem contexto.
    """
    paragrafos = [p.strip() for p in texto.split("\n\n") if len(p.strip()) > 30]
    chunks: list[str] = []
    acumulador = ""

    for paragrafo in paragrafos:
        if len(acumulador) + len(paragrafo) > tamanho_max and acumulador:
            chunks.append(acumulador.strip())
            acumulador = paragrafo
        else:
            acumulador = (acumulador + "\n\n" + paragrafo).strip() if acumulador else paragrafo

    if acumulador:
        chunks.append(acumulador.strip())

    return chunks


async def ingerir_memorial_pdf(conteudo_bytes: bytes, tenant_id: str, projeto_id: str) -> int:
    """
    Pipeline completo: PDF → texto → chunks → embeddings → Pinecone.

    Args:
        conteudo_bytes: Conteúdo binário do arquivo PDF.
        tenant_id: ID do tenant (isolamento B2B).
        projeto_id: ID do projeto/obra — vincula o memorial ao orçamento.

    Returns:
        Número de chunks vetorizados e salvos no Pinecone.
    """
    # 1. Extrair e chunkar o texto
    texto = _extrair_texto_pdf(conteudo_bytes)
    chunks = _chunkar_por_paragrafo(texto)

    if not chunks:
        raise ValueError("Nenhum parágrafo encontrado no PDF.")

    print(f"[MEMORIAL] PDF processado: {len(chunks)} chunks gerados para projeto '{projeto_id}'")

    # 2. Gerar embeddings em lote (OpenAI suporta até 2048 inputs por chamada)
    response = await openai_client.embeddings.create(
        input=chunks,
        model="text-embedding-3-small"
    )
    vetores = [item.embedding for item in response.data]

    # 3. Montar payload para o Pinecone
    namespace = f"memorial:{tenant_id}:{projeto_id}"
    vectors_payload = []
    for i, (chunk, vetor) in enumerate(zip(chunks, vetores)):
        vectors_payload.append({
            "id": f"{projeto_id}_chunk_{i}",
            "values": vetor,
            "metadata": {
                # Pinecone metadata value limit: 40kb. Truncamos para 1000 chars por segurança.
                "texto": chunk[:1000],
                "chunk_index": i,
                "projeto_id": projeto_id,
                "tenant_id": tenant_id,
            }
        })

    # 4. Upsert em batches de 100 (limite da API Pinecone)
    def upsert_em_lotes():
        idx = _get_pinecone_index()
        batch_size = 100
        for i in range(0, len(vectors_payload), batch_size):
            lote = vectors_payload[i : i + batch_size]
            idx.upsert(vectors=lote, namespace=namespace)
        return len(vectors_payload)

    total = await asyncio.to_thread(upsert_em_lotes)
    print(f"[MEMORIAL] {total} vetores salvos no namespace '{namespace}'")
    return total


async def buscar_contexto_memorial(
    termo: str,
    tenant_id: str,
    projeto_id: str,
    top_k: int = 2
) -> str | None:
    """
    Busca os trechos mais relevantes do memorial para um dado item do orçamento.
    Retorna None se não houver memorial carregado ou se o score for insuficiente.

    Usado pelo Modo Geração: enriquece o prompt do Agente Mapeador.
    """
    namespace = f"memorial:{tenant_id}:{projeto_id}"

    try:
        # Gera embedding do termo
        embed_response = await openai_client.embeddings.create(
            input=termo,
            model="text-embedding-3-small"
        )
        vetor = embed_response.data[0].embedding

        # Consulta o Pinecone no namespace do memorial
        def query_memorial():
            idx = _get_pinecone_index()
            return idx.query(
                vector=vetor,
                top_k=top_k,
                include_metadata=True,
                namespace=namespace
            )

        resultado = await asyncio.to_thread(query_memorial)

        if not resultado.matches:
            return None

        # Filtra por score mínimo para evitar ruído semântico
        matches_relevantes = [
            m for m in resultado.matches
            if m.score >= _SCORE_MINIMO_MEMORIAL and m.metadata
        ]

        if not matches_relevantes:
            return None

        trechos = [m.metadata.get("texto", "") for m in matches_relevantes]
        return "\n---\n".join(trechos)

    except Exception as e:
        # Falha silenciosa: o motor de orçamentação continua sem o memorial
        print(f"[MEMORIAL] Erro ao buscar contexto (não-bloqueante): {e}")
        return None


async def checar_status_memorial(tenant_id: str, projeto_id: str) -> dict:
    """
    Verifica se existe um memorial carregado para o projeto consultando as stats do Pinecone.
    """
    namespace = f"memorial:{tenant_id}:{projeto_id}"

    def query_stats():
        idx = _get_pinecone_index()
        stats = idx.describe_index_stats()
        # Pinecone v5: stats.namespaces é um dict[str, NamespaceSummary]
        namespaces = stats.namespaces or {}
        ns_info = namespaces.get(namespace)
        return ns_info.vector_count if ns_info else 0

    try:
        count = await asyncio.to_thread(query_stats)
        if count > 0:
            return {"status": "pronto", "chunks": count}
        return {"status": "nao_encontrado", "chunks": 0}
    except Exception as e:
        print(f"[MEMORIAL] Erro ao checar status: {e}")
        return {"status": "erro", "chunks": 0}
