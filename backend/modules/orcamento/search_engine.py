import asyncio
from core.db import get_db_pool
from core.config import settings
from openai import AsyncOpenAI
from pinecone import Pinecone

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX_NAME)

async def _postgres_search(termo: str, tipo: str = "composicoes") -> list[dict]:
    """Busca Lexical (Trigramas) diretamente no PostgreSQL via asyncpg."""
    tabela = "sinapi_composicoes" if tipo == "composicoes" else "sinapi_insumos"
    
    # word_similarity é a mágica do pg_trgm. Quanto mais perto de 1.0, mais parecido.
    query = f"""
        SELECT codigo, descricao, preco, unidade, word_similarity(descricao, $1) as score_lexico
        FROM {tabela}
        WHERE word_similarity(descricao, $1) > 0.1
        ORDER BY score_lexico DESC
        LIMIT 15;
    """
    
    pool = get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(query, termo)
    
    # Converte Record do asyncpg para dicionário limpo
    return [dict(r) for r in records]

async def _pinecone_search(termo: str, tenant_id: str, tipo: str = "composicoes") -> list[dict]:
    """Busca Semântica gerando o Embedding e buscando no Pinecone isolado por cliente."""
    # 1. Gera Embedding em tempo real usando o modelo super rápido da OpenAI
    response = await openai_client.embeddings.create(
        input=termo,
        model="text-embedding-3-small"
    )
    vetor = response.data[0].embedding
    
    # 2. Define o namespace dinâmico por Tenant SaaS (Ex: "construtoraX_composicoes")
    sufixo = "composicoes_sinapi" if tipo == "composicoes" else "insumos_sinapi"
    namespace = f"{tenant_id}_{sufixo}"
    
    # 3. Consulta ao Pinecone (encapsulada numa thread para não bloquear o AsyncIO do FastAPI)
    def query_pinecone():
        try:
            return index.query(
                vector=vetor,
                top_k=15,
                include_metadata=True,
                namespace=namespace
            )
        except Exception:
            # Fallback seguro caso o namespace ainda não exista para um tenant novo
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

async def realizar_busca_hibrida(termo_busca: str, id_planilha: str, tenant_id: str) -> list[dict]:
    """
    Reciprocal Rank Fusion (RRF).
    Funde a nota do PostgreSQL com a nota do Pinecone e retorna o Top 10 Absoluto.
    """
    # Lança as buscas simultaneamente para cortar o tempo de resposta pela metade
    pg_task = asyncio.create_task(_postgres_search(termo_busca, "composicoes"))
    pc_task = asyncio.create_task(_pinecone_search(termo_busca, tenant_id, "composicoes"))
    
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
        if cod in scores_rrf:
            # HUB MÁGICO: Encontrado em ambos! Boost matemático de 20%
            scores_rrf[cod] += (1.0 / (k + rank + 1))
            scores_rrf[cod] *= 1.20
        else:
            scores_rrf[cod] = (1.0 / (k + rank + 1))
            master_dict[cod] = item
            
    # Ordena pelo Score RRF
    ranking = sorted(scores_rrf.items(), key=lambda x: x[1], reverse=True)
    
    # Formata a entrega e corta para apenas os Top 10 vencedores
    top_items = []
    for cod, score in ranking[:10]:
        item = master_dict[cod].copy()
        # Opcional: Converter Numeric do Postgres para Float nativo do Python (necessário pro JSON)
        item["preco"] = float(item["preco"]) if item.get("preco") is not None else 0.0
        item["score_rrf_interno"] = round(score * 100, 2)
        top_items.append(item)
        
    return top_items
