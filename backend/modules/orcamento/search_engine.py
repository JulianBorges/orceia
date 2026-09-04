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


async def _pinecone_search(termo: str, tenant_id: str, tipo: str = "composicoes", unidade_filtro: str = None) -> list[dict]:
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
            
            kwargs = {
                "vector": vetor,
                "top_k": 20,
                "include_metadata": True
            }
            if unidade_filtro:
                kwargs["filter"] = {"unidade": {"$eq": unidade_filtro}}
                
            # Tenta primeiro os embeddings customizados do tenant
            result = idx.query(namespace=namespace_tenant, **kwargs)
            
            # Se filtrou por unidade e não achou quase nada, tenta sem o filtro (fallback relaxado)
            if unidade_filtro and len(result.matches) < 3:
                kwargs.pop("filter", None)
                result = idx.query(namespace=namespace_tenant, **kwargs)
                
            # Fallback para base SINAPI global
            if not result.matches:
                if unidade_filtro:
                    kwargs["filter"] = {"unidade": {"$eq": unidade_filtro}}
                result = idx.query(namespace=namespace_global, **kwargs)
                
                if unidade_filtro and len(result.matches) < 3:
                    kwargs.pop("filter", None)
                    result = idx.query(namespace=namespace_global, **kwargs)
                    
            return result
        except Exception as e:
            print(f"[PINECONE] Fallback por erro de conexão: {e}")
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

async def realizar_busca_hibrida(termo_busca: str, id_planilha: str, tenant_id: str, unidade: str = None) -> tuple[list[dict], str]:
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
    pc_task = asyncio.create_task(_pinecone_search(termo_normalizado.termo_limpo, tenant_id, "composicoes", unidade))
    
    pg_results, pc_results = await asyncio.gather(pg_task, pc_task)
    
    k = 60
    scores_rrf = {}
    master_dict = {}
    
    def processar_resultados(pg_res, pc_res):
        # Avaliando Postgres (Trigramas)
        for rank, item in enumerate(pg_res):
            cod = item["codigo"]
            scores_rrf[cod] = scores_rrf.get(cod, 0) + (1.0 / (k + rank + 1))
            master_dict[cod] = item
            
        # Avaliando Pinecone (Embeddings)
        for rank, item in enumerate(pc_res):
            cod = item["codigo"]
            score_pc = 1.0 / (k + rank + 1)
            if cod in scores_rrf:
                scores_rrf[cod] += score_pc * 1.20
            else:
                scores_rrf[cod] = score_pc
                master_dict[cod] = item

    processar_resultados(pg_results, pc_results)
            
    # Ordena pelo Score RRF
    ranking = sorted(scores_rrf.items(), key=lambda x: x[1], reverse=True)
    
    # Avalia confiança do resultado considerando as duas escalas possíveis:
    # - Score máximo de consenso (top 1 em ambos): 1/61 * 1.20 + 1/61 = 2.2/61
    # - Score máximo de fonte única (top 1 só em uma): 1/61
    # Normaliza pelo score de fonte única para dar chance justa a itens sem cobertura vetorial.
    # O Fallback só é acionado se o melhor resultado também seria ruim mesmo se tivesse vindo de uma fonte.
    max_score_unica_fonte = 1.0 / (k + 1)  # score de rank 0 numa única fonte
    best_score = ranking[0][1] if ranking else 0

    # Desnormaliza o boost de consenso antes de comparar com a escala de fonte única
    # Se o item tem consenso (score > 1/61), o score base real é ~ score / 2.2
    # Comparamos o score com 85% do máximo de fonte única para fairness
    limiar_fallback = max_score_unica_fonte * 0.85
    acionar_fallback = best_score < limiar_fallback
    best_pct = min((best_score / (max_score_unica_fonte * 2.2)) * 100, 100.0)

    # Fallback Orçamentista Virtual se a confiança estiver baixa (Abaixo de 85%)
    if acionar_fallback:
        print(f"[RRF FALLBACK] Confiança muito baixa ({round(best_pct, 1)}%) para '{termo_busca}'. Acionando GPT Reformulador...")
        from modules.orcamento.reformulador import gerar_variacoes_tecnicas
        sinonimos = await gerar_variacoes_tecnicas(termo_busca)
        
        if sinonimos:
            fallback_tasks = []
            for sin in sinonimos:
                sin_norm = normalizar_termo_busca(sin)
                fallback_tasks.append(_postgres_search(sin, "composicoes"))
                fallback_tasks.append(_pinecone_search(sin_norm.termo_limpo, tenant_id, "composicoes", unidade))
                
            resultados_fallback = await asyncio.gather(*fallback_tasks)
            
            # Os resultados vêm intercalados: [pg1, pc1, pg2, pc2, pg3, pc3]
            for i in range(0, len(resultados_fallback), 2):
                processar_resultados(resultados_fallback[i], resultados_fallback[i+1])
                
            # Reordena com os novos competidores misturados
            ranking = sorted(scores_rrf.items(), key=lambda x: x[1], reverse=True)

    # Formata a entrega e corta para apenas os Top 10 vencedores
    top_items = []
    for cod, score in ranking[:10]:
        item = master_dict[cod].copy()
        # Converte Numeric do Postgres para Float nativo (necessário pro JSON)
        item["preco"] = float(item["preco"]) if item.get("preco") is not None else 0.0
        
        normalized_percentage = min((score / (max_score_unica_fonte * 2.2)) * 100, 100.0)
        
        print(f"[RRF] {cod}: raw_score={score}, pct={round(normalized_percentage, 1)}%")
        # Garante campos consistentes independente da origem (Postgres ou Pinecone)
        item.setdefault("score_lexico", None)
        item.setdefault("score_semantico", None)
        item["score"] = round(normalized_percentage, 1) # Injeta o score final RRF em %
        top_items.append(item)
        
    return top_items, termo_normalizado.caracteristicas_extras
