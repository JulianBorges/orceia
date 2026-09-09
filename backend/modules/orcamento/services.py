import asyncio
import random
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from openai import RateLimitError, APITimeoutError, APIConnectionError
from modules.orcamento.schemas import LinhaOrcamentoUpsert
from modules.orcamento.search_engine import realizar_busca_hibrida
from modules.orcamento.ai_agents import consultar_agente_engenheiro
from modules.orcamento.preprocessor import extrair_dimensoes_numericas
from core.redis_client import publish_sse_event, get_ai_cache, set_ai_cache, RedisSemaphore
from core.db import get_db_pool
from core.text_utils import normalizar_chave

MAX_CONCURRENT_TASKS = 3  # Protege o Rate Limit em auto-scaling (Cloud Run)

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
        raise ValueError("Descriçāo vazia")
        
    # 1. A Busca Universal RRF SEMPRE roda primeiro
    # Traz os preços frescos do SINAPI e as 20 opções garantidas para a auditoria visual
    opcoes_rrf, caracteristicas_extras = await realizar_busca_hibrida(linha.descricao, id_planilha, linha.tenant_id, linha.unidade)

    # 2. Verifica RLHF (Engenharia Humana) B2B
    rlhf_result = await check_rlhf_memory(linha.tenant_id, linha.descricao)
    if rlhf_result:
        rlhf_result["id"] = linha.id
        rlhf_result["memoria_calculo"] = opcoes_rrf  # Rastreabilidade garantida!
        return rlhf_result
        
    # 3. Verifica Cache da OpenAI no Redis (para poupar tempo e custo de API)
    cache = await get_ai_cache(linha.descricao)
    if cache:
        if not cache.get("codigo_novo"):
            # Foi REJEITADO pela IA no passado. Preserva a recusa, mas entrega as 20 opções frescas
            return {
                "id": linha.id,
                **cache,
                "memoria_calculo": opcoes_rrf,
                "origem": "CACHE_REDIS",
            }
        else:
            # Foi ACEITO pela IA no passado. Valida se o SINAPI não o removeu do RRF:
            codigos_validos_rrf = [op["codigo"] for op in opcoes_rrf]
            if cache.get("codigo_novo") in codigos_validos_rrf:
                # O item continua existindo. Retornamos TODAS as 20 opções (sem mutilar)
                return {
                    "id": linha.id,
                    **cache,
                    "memoria_calculo": opcoes_rrf,
                    "origem": "CACHE_REDIS",
                }
            else:
                # O item sumiu do RRF (pode ter sido descontinuado no SINAPI)
                print(f"[CACHE] Invalidação de Segurança! Código {cache.get('codigo_novo')} não está mais no RRF.")
    
    # 4. Agente de IA toma a decisão baseada no Structured Outputs e Curva ABC
    # valor_financeiro_total removido: lógica ABC delegada para pós-processamento determinístico
    # Injeta caracteristicas dimensionais como contexto para o Agente Mapeador avaliar tolerancias
    termo_com_contexto = linha.descricao
    if getattr(linha, 'macro_item_context', None):
        termo_com_contexto = f"Etapa da Obra: {linha.macro_item_context}\nItem: {termo_com_contexto}"

    if caracteristicas_extras:
        termo_com_contexto = f"{termo_com_contexto} [Specs extraídas: {caracteristicas_extras}]"

    # Modo Geração: enriquece o prompt com trecho relevante do Memorial Descritivo (se disponível).
    # Fallback silencioso: se não houver memorial ou score for baixo, fluxo continua normalmente.
    termo_ctx = termo_com_contexto
    if getattr(linha, 'projeto_id', None) and getattr(linha, 'tenant_id', None):
        from modules.auditoria.services import buscar_contexto_memorial
        trecho_memorial = await buscar_contexto_memorial(
            linha.descricao,
            linha.tenant_id,
            linha.projeto_id
        )
        if trecho_memorial:
            termo_ctx = (
                f"{termo_com_contexto}\n\n[Especificação do Memorial Descritivo — use como referência de conformidade]:\n"
                f"{trecho_memorial}"
            )
            print(f"[MEMORIAL] Contexto injetado para: '{linha.descricao[:60]}'")

    # --- Lógica Determinística de Tolerância Dimensional ---
    import copy
    from modules.orcamento.preprocessor import injetar_tolerancia_dimensional
    
    # Criamos uma cópia para o cérebro da IA para NÃO vazar os marcadores [TOLERÂNCIA...] 
    # de volta para a Memória de Cálculo da UI e para o Banco de Dados
    opcoes_para_ia = copy.deepcopy(opcoes_rrf[:10])
    injetar_tolerancia_dimensional(linha.descricao, opcoes_para_ia)

    analise = await consultar_agente_engenheiro(termo_ctx, opcoes_para_ia)
    
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
    async with RedisSemaphore(MAX_CONCURRENT_TASKS):
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
    """Cria tasks paralelas, porém limitadas pelo semaphore local e global"""
    local_semaphore = asyncio.Semaphore(15) # Limita as chamadas à rede Redis locais
    
    async def processar_com_filtro_local(linha):
        async with local_semaphore:
            return await processar_linha_com_semaforo(linha, id_planilha)

    try:
        tasks = [processar_com_filtro_local(linha) for linha in linhas]
        
        # O gather roda todos, mas o Semaphore internamente na função segura os cavalos.
        # return_exceptions=True garante que se 1 linha explodir de vez, as outras não parem.
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # Ao final de tudo, aconteça o que acontecer, joga um evento de conclusão para a UI destravar
        tenant_id = linhas[0].tenant_id if linhas else "default"
        await publish_sse_event(f"stream:{tenant_id}:planilha:{id_planilha}", {"status": "lote_concluido", "total": len(linhas)})

async def bulk_upsert_linhas_orcamento(linhas: list[LinhaOrcamentoUpsert], tenant_id: str, titulo: str = "Orçamento", memorial_id: str = None):
    """Executa um upsert massivo de forma atômica e em uma única viagem ao banco."""
    
    if not linhas:
        return
        
    query_mae = """
        INSERT INTO planilhas (id, tenant_id, titulo, memorial_id) 
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET titulo = EXCLUDED.titulo, memorial_id = EXCLUDED.memorial_id, updated_at = CURRENT_TIMESTAMP;
    """
    
    query_filhas = """
        INSERT INTO planilhas_linhas (id, id_planilha, tenant_id, codigo, descricao, descricao_legada, unidade, quantidade, preco_unitario, ordem, ai_status, ai_parecer_tecnico, memoria_calculo)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT (id) 
        DO UPDATE SET 
            codigo = EXCLUDED.codigo,
            descricao = EXCLUDED.descricao,
            -- descricao_legada intencionalmente omitida do UPDATE para preservar o legado
            unidade = EXCLUDED.unidade,
            quantidade = EXCLUDED.quantidade,
            preco_unitario = EXCLUDED.preco_unitario,
            ordem = EXCLUDED.ordem,
            ai_status = EXCLUDED.ai_status,
            ai_parecer_tecnico = EXCLUDED.ai_parecer_tecnico,
            memoria_calculo = EXCLUDED.memoria_calculo,
            updated_at = CURRENT_TIMESTAMP
        WHERE planilhas_linhas.tenant_id = EXCLUDED.tenant_id; 
    """
    
    import json
    
    # Prepara a matriz de dados para a inserção binária do asyncpg
    dados = [
        (
            linha.id, 
            linha.id_planilha, 
            tenant_id,
            linha.codigo, 
            linha.descricao, 
            linha.descricao_legada or linha.descricao, # Fallback seguro no momento zero
            linha.unidade, 
            linha.quantidade, 
            linha.preco_unitario,
            linha.ordem,
            linha.ai_status,
            linha.ai_parecer_tecnico,
            json.dumps(linha.memoria_calculo) if linha.memoria_calculo else None
        )
        for linha in linhas
    ]

    pool = get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            id_planilha = linhas[0].id_planilha
            # Assegura a integridade referencial: cria a planilha se ela não existir
            await conn.execute(query_mae, id_planilha, tenant_id, titulo, memorial_id)
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

async def delete_planilha(id_planilha: str, tenant_id: str):
    """
    Remove o orçamento completo (e consequentemente suas linhas via CASCADE) 
    protegendo o escopo cross-tenant.
    """
    pool = get_db_pool()
    async with pool.acquire() as conn:
        deleted = await conn.execute(
            "DELETE FROM planilhas WHERE id = $1 AND tenant_id = $2",
            id_planilha,
            tenant_id
        )
        print(f"[DELETE] Planilha {id_planilha} removida pelo tenant {tenant_id}.")
        return deleted

async def get_planilhas_by_tenant(tenant_id: str) -> list[dict]:
    query = """
        SELECT CAST(id AS TEXT) as id, titulo, CAST(created_at AS TEXT) as created_at, CAST(updated_at AS TEXT) as updated_at, memorial_id
        FROM planilhas 
        WHERE tenant_id = $1 
        ORDER BY updated_at DESC
    """
    pool = get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(query, tenant_id)
        return [dict(r) for r in records]

async def get_linhas_by_planilha(id_planilha: str, tenant_id: str) -> dict:
    query_mae = "SELECT titulo, memorial_id FROM planilhas WHERE id = $1 AND tenant_id = $2"
    
    query_filhas = """
        SELECT CAST(id AS TEXT) as id, CAST(id_planilha AS TEXT) as id_planilha, 
               codigo, descricao, unidade, quantidade, preco_unitario, ordem, ai_status, ai_parecer_tecnico,
               CAST(memoria_calculo AS TEXT) as memoria_calculo
        FROM planilhas_linhas 
        WHERE id_planilha = $1 AND tenant_id = $2
        ORDER BY ordem ASC
    """
    
    import json
    pool = get_db_pool()
    async with pool.acquire() as conn:
        mae = await conn.fetchrow(query_mae, id_planilha, tenant_id)
        if not mae:
            raise ValueError("Planilha não encontrada")
            
        filhas = await conn.fetch(query_filhas, id_planilha, tenant_id)
        
        linhas_parsed = []
        for r in filhas:
            linha_dict = dict(r)
            if linha_dict.get("memoria_calculo"):
                try:
                    linha_dict["memoria_calculo"] = json.loads(linha_dict["memoria_calculo"])
                except Exception:
                    linha_dict["memoria_calculo"] = []
            else:
                linha_dict["memoria_calculo"] = []
            linhas_parsed.append(linha_dict)
        
        return {
            "id_planilha": id_planilha,
            "titulo": mae["titulo"],
            "memorial_id": mae["memorial_id"],
            "linhas": linhas_parsed
        }
