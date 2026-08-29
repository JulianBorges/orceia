import asyncio
from core.db import get_db_pool
from modules.orcamento.preprocessor import normalizar_termo_busca
from core.ai_client import openai_client
from pinecone import Pinecone
from core.config import settings
from modules.shared.sinapi_search import search_sinapi_por_trigrama as _postgres_search

_pc = None
_index = None

def get_pinecone_index():
    global _pc, _index
    if _index is None:
        _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        _index = _pc.Index(settings.PINECONE_INDEX_NAME)
    return _index


async def _pinecone_search(termo: str, tenant_id: str, tipo: str = "composicoes") -> list[dict]:
    """Busca Semântica gerando o Embedding e buscando no Pinecone isolado por cliente."""
    # 1. Gera Embedding em tempo real usando o modelo super rápido da OpenAI
    response = await openai_client.embeddings.create(
        input=termo,
        model="text-embedding-3-small"
    )
    vetor = response.data[0].embedding
    
    # 2. Define os namespaces
    sufixo = "composicoes_sinapi" if tipo == "composicoes" else "insumos_sinapi"
    namespace_tenant = f"{tenant_id}_{sufixo}"
    namespace_global = sufixo  # O namespace base compartilhado
    
    # 3. Consulta ao Pinecone (encapsulada numa thread para não bloquear o AsyncIO do FastAPI)
    def query_pinecone():
        try:
            idx = get_pinecone_index()
            # Tenta primeiro os embeddings customizados do tenant
            result = idx.query(
                vector=vetor,
                top_k=20,
                include_metadata=True,
                namespace=namespace_tenant
            )
            # Fallback para base SINAPI global
            if not result.matches:
                result = idx.query(
                    vector=vetor,
                    top_k=20,
                    include_metadata=True,
                    namespace=namespace_global
                )
            return result
        except Exception:
            # Fallback seguro caso dê falha de conexão ou api key
            from collections import namedtuple
            return namedtuple('MockResult', ['matches'])([])
            
    resultado_vetorial = await asyncio.to_thread(query_pinecone)
    
    # 4. Formata o payload igual ao SQL para que o Algoritmo RRF case perfeitamente
    opcoes = []
    for match in resultado_vetorial.matches:
        meta = match.metadata or {}
        opcoes.append({
            "codigo": meta.get("codigo"),
            "descricao": meta.get("descricao"),
            "preco": meta.get("preco"),
            "unidade": meta.get("unidade"),
            "score_semantico": match.score
        })
        
    return opcoes

async def realizar_busca_hibrida(termo_busca: str, id_planilha: str, tenant_id: str) -> tuple[list[dict], str]:
    """
    Reciprocal Rank Fusion (RRF).
    Funde a nota do PostgreSQL com a nota do Pinecone e retorna o Top 10 Absoluto.
    """
    # Agente Corretor: normaliza o termo antes do embedding (nao afeta busca lexical)
    termo_normalizado = normalizar_termo_busca(termo_busca)
    print(f"[Preprocessor] '{termo_busca}' -> Limpo: '{termo_normalizado.termo_limpo}'")

    # Busca lexical usa o termo ORIGINAL (trigramas funcionam melhor com texto completo)
    pg_task = asyncio.create_task(_postgres_search(termo_busca, "composicoes"))
    # Busca vetorial usa o termo LIMPO (embedding sem ruido dimensional)
    pc_task = asyncio.create_task(_pinecone_search(termo_normalizado.termo_limpo, tenant_id, "composicoes"))
    
    pg_results, pc_results = await asyncio.gather(pg_task, pc_task)
    
    k = 60
    scores_rrf = {}
    master_dict = {}
    
    # Avaliando Postgres (Trigramas)
    for rank, item in enumerate(pg_results):
        cod = item["codigo"]
        scores_rrf[cod] = scores_rrf.get(cod, 0) + (1.0 / (k + rank + 1))
        master_dict[cod] = item
        
    # Avaliando Pinecone (Embeddings)
    for rank, item in enumerate(pc_results):
        cod = item["codigo"]
        score_pc = 1.0 / (k + rank + 1)
        if cod in scores_rrf:
            # BOOST DE CONSENSO: aplica +20% APENAS sobre o score incremental do Pinecone.
            # Nao multiplica o total acumulado — evita distorcao matematica em edge cases.
            scores_rrf[cod] += score_pc * 1.20
        else:
            scores_rrf[cod] = score_pc
            master_dict[cod] = item
            
    # Ordena pelo Score RRF
    ranking = sorted(scores_rrf.items(), key=lambda x: x[1], reverse=True)
    
    # Formata a entrega e corta para apenas os Top 10 vencedores
    top_items = []
    for cod, score in ranking[:10]:
        item = master_dict[cod].copy()
        # Converte Numeric do Postgres para Float nativo (necessário pro JSON)
        item["preco"] = float(item["preco"]) if item.get("preco") is not None else 0.0
        print(f"[RRF] {cod}: score={round(score * 100, 2)}")
        # Garante campos consistentes independente da origem (Postgres ou Pinecone)
        item.setdefault("score_lexico", None)
        item.setdefault("score_semantico", None)
        top_items.append(item)
        
    return top_items, termo_normalizado.caracteristicas_extras
