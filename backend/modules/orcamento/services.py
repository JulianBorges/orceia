import asyncio
import random
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from modules.orcamento.schemas import LinhaOrcamentoUpsert
from modules.orcamento.search_engine import realizar_busca_hibrida
from modules.orcamento.ai_agents import consultar_agente_engenheiro
from core.redis_client import publish_sse_event, get_ai_cache, set_ai_cache

# Limite máximo de consultas simultâneas na nuvem (protege a API da OpenAI e o Banco)
MAX_CONCURRENT_TASKS = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

async def check_rlhf_memory(tenant_id: str, termo: str) -> dict | None:
    """Consulta o banco de memórias do Cliente (Engenharia Humana)"""
    from core.db import get_db_pool
    query = "SELECT codigo_escolhido, parecer FROM memoria_organizacional WHERE tenant_id = $1 AND termo_original = $2 LIMIT 1"
    pool = get_db_pool()
    async with pool.acquire() as conn:
        record = await asyncio.wait_for(conn.fetchrow(query, tenant_id, termo.strip().lower()), timeout=5.0)
        
    if record:
        return {
            "codigo_novo": record["codigo_escolhido"],
            "status_ia": "MEMÓRIA HUMANA",
            "parecer": record["parecer"],
            "rigor": "BAIXO",
            "origem": "RLHF_DATABASE"
        }
    return None

# Essa função engloba o RRF + OpenAI e usa Tenacity para refazer a consulta se a rede cair
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
async def processar_linha_inteligente(linha: LinhaOrcamentoUpsert, id_planilha: str) -> dict:
    if not linha.descricao:
        raise ValueError("Descrição vazia")
        
    # 0. Verifica RLHF (Reinforcement Learning from Human Feedback) B2B
    rlhf_result = await check_rlhf_memory(linha.tenant_id, linha.descricao)
    if rlhf_result:
        rlhf_result["id"] = linha.id
        return rlhf_result
        
    # 1. Busca Híbrida RRF (Pinecone + Postgres Trigramas) com Tenant ID
    opcoes_rrf = await realizar_busca_hibrida(linha.descricao, id_planilha, linha.tenant_id)

    # 2. Verifica no Cache Global Criptográfico (SHA-256) com "Trava de Cache Seguro"
    cache = await get_ai_cache(linha.descricao)
    if cache:
        codigos_validos_rrf = [op["codigo"] for op in opcoes_rrf]
        if cache.get("codigo_novo") in codigos_validos_rrf or not cache.get("codigo_novo"):
            cache["origem"] = "CACHE_REDIS"
            cache["id"] = linha.id # Sobrescreve a ID velha do cache com a ID atual da requisição!
            return cache
        else:
            # O item foi removido do SINAPI ou Pinecone recentemente! Cache invalidado.
            print(f"[CACHE] Invalidação por Segurança! Código {cache.get('codigo_novo')} não está mais no Top 15.")
    
    # 3. Agente de IA toma a decisão baseada no Structured Outputs e Curva ABC
    valor_financeiro_total = linha.quantidade * linha.preco_unitario
    analise = await consultar_agente_engenheiro(linha.descricao, opcoes_rrf, valor_financeiro_total)
    
    # 4. Observabilidade do CoT e Formatação do resultado final
    print(f"[CoT] Raciocínio (ID {linha.id}): {analise.raciocinio_step_by_step}")
    
    status_ia = "ACEITO"
    if not analise.codigo_selecionado:
        status_ia = "REJEITADO"
    elif analise.categoria_rigor == "ALTO":
        status_ia = "RESSALVA"

    resultado = {
        "id": linha.id,
        "codigo_novo": analise.codigo_selecionado,
        "status_ia": status_ia,
        "parecer": analise.parecer_tecnico,
        "rigor": analise.categoria_rigor,
        "memoria_calculo": [op.model_dump() for op in analise.composicoes_analisadas]
    }
    
    # 5. Salva o veredito no Redis para não gastar API nas próximas vezes
    await set_ai_cache(linha.descricao, resultado)
    resultado["origem"] = "OPENAI"
    
    return resultado

async def processar_linha_com_semaforo(linha: LinhaOrcamentoUpsert, id_planilha: str):
    """Estrangula a requisição usando Semaphore e publica o resultado no Redis Stream"""
    async with semaphore:
        try:
            # Roda a inteligência brutal em cascata
            resultado = await processar_linha_inteligente(linha, id_planilha)
            
            # Formata pacote SSE
            evento_sse = {
                "id": linha.id,
                "status": "sucesso",
                "dados_ia": resultado
            }
        except Exception as e:
            evento_sse = {
                "id": linha.id,
                "status": "erro",
                "mensagem": str(e)
            }
        
        # Joga a resposta de volta no barramento (Redis) para o Frontend capturar
        stream_key = f"stream:{linha.tenant_id}:planilha:{id_planilha}"
        await publish_sse_event(stream_key, evento_sse)

async def iniciar_processamento_lote_em_background(linhas: list[LinhaOrcamentoUpsert], id_planilha: str):
    """Cria tasks paralelas, porém limitadas pelo semaphore de 10 slots"""
    try:
        tasks = [processar_linha_com_semaforo(linha, id_planilha) for linha in linhas]
        
        # O gather roda todos, mas o Semaphore internamente na função segura os cavalos.
        # return_exceptions=True garante que se 1 linha explodir de vez, as outras não parem.
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # Ao final de tudo, aconteça o que acontecer, joga um evento de conclusão para a UI destravar
        tenant_id = linhas[0].tenant_id if linhas else "default"
        await publish_sse_event(f"stream:{tenant_id}:planilha:{id_planilha}", {"status": "lote_concluido", "total": len(linhas)})

async def bulk_upsert_linhas_orcamento(linhas: list[LinhaOrcamentoUpsert], tenant_id: str):
    """Executa um upsert massivo de forma atômica e em uma única viagem ao banco."""
    from core.db import get_db_pool
    
    if not linhas:
        return
        
    id_planilha = linhas[0].id_planilha

    query_mae = """
        INSERT INTO planilhas (id, tenant_id) 
        VALUES ($1, $2)
        ON CONFLICT (id) DO NOTHING;
    """
    
    query_filhas = """
        INSERT INTO planilhas_linhas (id, id_planilha, tenant_id, codigo, descricao, unidade, quantidade, preco_unitario)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (id) 
        DO UPDATE SET 
            codigo = EXCLUDED.codigo,
            descricao = EXCLUDED.descricao,
            unidade = EXCLUDED.unidade,
            quantidade = EXCLUDED.quantidade,
            preco_unitario = EXCLUDED.preco_unitario,
            updated_at = CURRENT_TIMESTAMP
        WHERE planilhas_linhas.tenant_id = EXCLUDED.tenant_id; 
    """
    
    # Prepara a matriz de dados para a inserção binária do asyncpg
    dados = [
        (
            linha.id, 
            linha.id_planilha, 
            tenant_id,
            linha.codigo, 
            linha.descricao, 
            linha.unidade, 
            linha.quantidade, 
            linha.preco_unitario
        )
        for linha in linhas
    ]

    pool = get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Assegura a integridade referencial: cria a planilha se ela não existir
            await conn.execute(query_mae, id_planilha, tenant_id)
            # executemany processa os milhares de registros numa pancada só (Custo O(1) de rede)
            await conn.executemany(query_filhas, dados)
