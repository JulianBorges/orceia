import asyncio
import random
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from openai import RateLimitError, APITimeoutError, APIConnectionError
from modules.orcamento.schemas import LinhaOrcamentoUpsert
from modules.orcamento.search_engine import realizar_busca_hibrida
from modules.orcamento.ai_agents import consultar_agente_engenheiro
from modules.orcamento.preprocessor import extrair_dimensoes_numericas
from core.redis_client import publish_sse_event, get_ai_cache, set_ai_cache
from core.db import get_db_pool
from core.text_utils import normalizar_chave

# ATENÇÃO: Este semáforo é por-processo (Python in-memory).
# O servidor DEVE rodar com 1 worker apenas (uvicorn --workers 1).
# Para múltiplos workers, migrar para semáforo distribuído via Redis.
MAX_CONCURRENT_TASKS = 3  # Reduzido de 10 para 3 para proteger Rate Limit em auto-scaling (Cloud Run)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

async def check_rlhf_memory(tenant_id: str, termo: str) -> dict | None:
    """Consulta o banco de memórias do Cliente (Engenharia Humana)"""
    query = "SELECT codigo_escolhido, parecer FROM memoria_organizacional WHERE tenant_id = $1 AND termo_original = $2 LIMIT 1"
    pool = get_db_pool()
    async with pool.acquire() as conn:
        record = await asyncio.wait_for(conn.fetchrow(query, tenant_id, normalizar_chave(termo)), timeout=5.0)
        
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
    # Retenta APENAS erros de infra recuperaveis. ValueError e ValidationError NAO devem ser retentados.
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError, ConnectionError)),
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
        
    # 1. Busca Híbrida RRF (Pinecone + Postgres Trigramas) com Tenant ID e Filtro de Unidade
    opcoes_rrf, caracteristicas_extras = await realizar_busca_hibrida(linha.descricao, id_planilha, linha.tenant_id, linha.unidade)

    # 2. Verifica no Cache Global Criptográfico (SHA-256) com "Trava de Cache Seguro"
    cache = await get_ai_cache(linha.descricao)
    if cache:
        codigos_validos_rrf = [op["codigo"] for op in opcoes_rrf]
        if cache.get("codigo_novo") in codigos_validos_rrf or not cache.get("codigo_novo"):
            # Enriquece o veredito cacheado com memoria_calculo frescos do RRF atual
            if cache.get("codigo_novo"):
                memoria_fresca = [op for op in opcoes_rrf if op["codigo"] == cache.get("codigo_novo")]
                if not memoria_fresca:
                    memoria_fresca = opcoes_rrf
                    parecer_original = cache.get("parecer", "")
                    cache["parecer"] = f"[AVISO DE CACHE: O código validado saiu do Top 15 da busca atual] {parecer_original}"
            else:
                memoria_fresca = opcoes_rrf
                
            return {
                "id": linha.id,
                **cache,
                "memoria_calculo": memoria_fresca,
                "origem": "CACHE_REDIS",
            }
        else:
            # O item foi removido do SINAPI ou Pinecone recentemente! Cache invalidado.
            print(f"[CACHE] Invalidação por Segurança! Código {cache.get('codigo_novo')} não está mais no Top 15.")
    
    # 3. Agente de IA toma a decisão baseada no Structured Outputs e Curva ABC
    # valor_financeiro_total removido: lógica ABC delegada para pós-processamento determinístico
    # Injeta caracteristicas dimensionais como contexto para o Agente Mapeador avaliar tolerancias
    termo_com_contexto = linha.descricao
    if getattr(linha, 'macro_item_context', None):
        termo_com_contexto = f"Etapa da Obra: {linha.macro_item_context}\nItem: {termo_com_contexto}"

    if caracteristicas_extras:
        termo_com_contexto = f"{termo_com_contexto} [Specs extraídas: {caracteristicas_extras}]"
        
    # --- Lógica Determinística de Tolerância Dimensional ---
    dimensoes_usuario = extrair_dimensoes_numericas(linha.descricao)
    if dimensoes_usuario:
        for op in opcoes_rrf:
            dimensoes_sinapi = extrair_dimensoes_numericas(op.get("descricao", ""))
            tolerancia_ok = False
            
            if dimensoes_sinapi and len(dimensoes_sinapi) == len(dimensoes_usuario):
                diffs_ok = True
                for du, ds in zip(dimensoes_usuario, dimensoes_sinapi):
                    if ds == 0:
                        diffs_ok = False
                        break
                    diff = abs(du - ds) / ds
                    if diff > 0.15:
                        diffs_ok = False
                        break
                tolerancia_ok = diffs_ok
                
            if tolerancia_ok:
                op["descricao"] += " [TOLERÂNCIA: ACEITÁVEL]"
            else:
                op["descricao"] += " [TOLERÂNCIA: INACEITÁVEL]"

    analise = await consultar_agente_engenheiro(termo_com_contexto, opcoes_rrf)
    
    # 4. Observabilidade do CoT e Formatação do resultado final
    print(f"[CoT] Raciocínio (ID {linha.id}): {analise.raciocinio_step_by_step}")
    
    status_ia = "ACEITO"
    if not analise.codigo_selecionado:
        status_ia = "REJEITADO"
    elif getattr(analise, "aceito_com_tolerancia", False):
        # Tolerancia dimensional <=15% aceita — sempre RESSALVA para rastreabilidade SINAPI
        status_ia = "RESSALVA"
    elif analise.categoria_rigor == "ALTO":
        # Item critico ou Classe A da Curva ABC — sempre RESSALVA para auditoria
        status_ia = "RESSALVA"

    # Cache armazena APENAS o veredito lógico — preços são perecíveis (SINAPI mensal)
    resultado_cacheavel = {
        "codigo_novo": analise.codigo_selecionado,
        "status_ia": status_ia,
        "parecer": analise.parecer_tecnico,
        "rigor": analise.categoria_rigor,
        "aceito_com_tolerancia": getattr(analise, "aceito_com_tolerancia", False),
    }
    
    # 5. Salva APENAS o veredito no Redis (sem memoria_calculo — precos nao sao cacheados)
    await set_ai_cache(linha.descricao, resultado_cacheavel)

    # Monta resultado completo com memoria_calculo frescos do RRF atual
    resultado = {
        "id": linha.id,
        **resultado_cacheavel,
        "memoria_calculo": opcoes_rrf,
        "origem": "OPENAI",
    }
    
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


async def bulk_delete_linhas_orcamento(ids: list[str], id_planilha: str, tenant_id: str):
    """
    Remove linhas do banco de forma atômica com proteção cross-tenant.
    A cláusula WHERE tenant_id = $3 garante que um tenant nunca deleta dados de outro.
    """
    from core.db import get_db_pool

    if not ids:
        return

    pool = get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Deleção em lote com proteção de tenant — usa ANY($1) para evitar N queries
            deleted = await conn.execute(
                """
                DELETE FROM planilhas_linhas
                WHERE id = ANY($1::varchar[])
                  AND id_planilha = $2
                  AND tenant_id = $3
                """,
                ids,
                id_planilha,
                tenant_id,
            )
            print(f"[DELETE] {deleted} linhas removidas (planilha: {id_planilha}, tenant: {tenant_id})")

