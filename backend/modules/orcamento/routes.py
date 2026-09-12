from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse
from core.config import settings
from modules.orcamento.schemas import LoteUpsertRequest, FeedbackRLHF, DeleteLinhasRequest, PlanilhaResponse, PlanilhaLinhasResponse
from modules.orcamento.services import (
    iniciar_processamento_lote_em_background,
    bulk_upsert_linhas_orcamento,
    bulk_delete_linhas_orcamento,
    get_planilhas_by_tenant,
    get_linhas_by_planilha,
    delete_planilha
)
from core.db import get_db_pool
import core.redis_client as rc
from core.redis_client import delete_ai_cache
from core.text_utils import normalizar_chave
import asyncio
import json
import secrets

router = APIRouter(prefix="/orcamento", tags=["orcamento"])

from core.security import verify_proxy_secret, get_current_tenant, verify_stream_token

@router.post("/feedback", dependencies=[Depends(verify_proxy_secret)])
async def save_rlhf_feedback(feedback: FeedbackRLHF, tenant_id: str = Depends(get_current_tenant)):
    """Guarda a decisão humana no banco (Memória Organizacional B2B)"""
    # Blindagem: Ignora o que o cliente mandou no JSON e força o uso do Tenant Autenticado no Cookie
    feedback.tenant_id = tenant_id
    query = """
        INSERT INTO memoria_organizacional (tenant_id, descricao_legada, codigo, descricao, parecer_tecnico)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (tenant_id, descricao_legada) 
        DO UPDATE SET codigo = $3, descricao = $4, parecer_tecnico = $5, updated_at = CURRENT_TIMESTAMP
    """
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, feedback.tenant_id, normalizar_chave(feedback.descricao_legada), feedback.codigo, feedback.descricao, feedback.parecer_tecnico)
        # Invalida o cache Redis para o termo corrigido pelo humano
        await delete_ai_cache(feedback.descricao_legada)
        print(f"[RLHF] Cache invalidado para: '{feedback.descricao_legada[:50]}'")
        return {"status": "success", "message": "Feedback memorizado para o Tenant"}
    except Exception as e:
        print(f"[ERRO RLHF] Falha ao salvar feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Erro salvando RLHF: {str(e)}")

@router.post("/upsert-linhas", dependencies=[Depends(verify_proxy_secret)])
async def upsert_linhas(lote: LoteUpsertRequest, background_tasks: BackgroundTasks, tenant_id: str = Depends(get_current_tenant)):
    if not lote.linhas:
        return {"status": "success"}
    
    planilha_id = lote.linhas[0].id_planilha
    # Força a marcação B2B (Segurança Server-Side)
    for linha in lote.linhas:
        linha.tenant_id = tenant_id
        
    stream_token = secrets.token_urlsafe(32)
    if rc.redis_client:
        start_id = "0-0"
        try:
            info = await rc.redis_client.xinfo_stream(f"stream:{tenant_id}:planilha:{planilha_id}")
            start_id = info.get("last-generated-id", "0-0")
        except Exception:
            pass # Stream nao existe ainda
            
        try:
            await rc.redis_client.setex(f"sse_token:{stream_token}", 7200, f"{tenant_id}::{start_id}") # Valido por 2h
        except Exception as e:
            print(f"[AVISO] Falha ao configurar token SSE no Redis (possível offline/rate limit): {e}")
        
    # Despacha a bomba para o background. O Frontend fica livre instantaneamente (0 latência)
    background_tasks.add_task(iniciar_processamento_lote_em_background, lote.linhas, planilha_id)
    
    return {"status": "processing_started", "linhas": len(lote.linhas), "stream_token": stream_token}

@router.post("/save-linhas", dependencies=[Depends(verify_proxy_secret)])
async def save_linhas(lote: LoteUpsertRequest, tenant_id: str = Depends(get_current_tenant)):
    """
    Persiste as alterações instantâneas (Auto-Save) oriundas do frontend.
    """
    if not lote.linhas:
        return {"status": "success"}
    
    try:
        await bulk_upsert_linhas_orcamento(lote.linhas, tenant_id, lote.titulo, lote.memorial_id)
        return {
            "status": "success",
            "linhas_salvas": len(lote.linhas)
        }
    except Exception as e:
        print(f"[ERRO DB] Falha no auto-save massivo: {e}")
        raise HTTPException(status_code=500, detail="Falha ao sincronizar o orçamento.")


@router.delete("/linhas", dependencies=[Depends(verify_proxy_secret)])
async def delete_linhas(body: DeleteLinhasRequest, tenant_id: str = Depends(get_current_tenant)):
    """
    Remove linhas do banco de forma atômica.
    Proteção cross-tenant garantida no service layer — um tenant jamais remove dados de outro.
    """
    if not body.ids:
        return {"status": "success", "removidas": 0}

    try:
        await bulk_delete_linhas_orcamento(body.ids, body.id_planilha, tenant_id)
        return {"status": "success", "removidas": len(body.ids)}
    except Exception as e:
        print(f"[ERRO DB] Falha ao deletar linhas: {e}")
        raise HTTPException(status_code=500, detail="Falha ao remover as linhas do orçamento.")

from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks, Request

# ... skips to sse_stream ...

@router.get("/stream/{id_planilha}")
async def sse_stream(request: Request, id_planilha: str, last_event_id: str = Header(default="0-0"), token_data: tuple = Depends(verify_stream_token)):
    """Canal de Eventos (SSE). O frontend escuta aqui DIRETAMENTE e atualiza a UI instantaneamente"""
    tenant_id, token_start_id = token_data
    
    async def event_generator():
        # Padding inicial de 8KB: força proxies governamentais (Fortinet/Squid/BlueCoat/McAfee)
        # a liberarem o buffer de Deep Packet Inspection e transmitirem em tempo real.
        # 2KB era insuficiente para proxies enterprise com buffer DPI configurado para 8KB.
        yield f": {' ' * 8192}\n\n"
        
        stream_key = f"stream:{tenant_id}:planilha:{id_planilha}"
        last_id = last_event_id
        if last_id and "," in last_id:
            last_id = last_id.split(",")[-1].strip()
            
        if not last_id or last_id in ("null", "undefined", ""):
            last_id = "0-0"
            
        if last_id == "$":
            # Se for uma nova conexao do frontend ($), começa exatamente do ponto em que o POST /upsert-linhas ocorreu
            last_id = token_start_id if token_start_id else "0-0"

        try:
            while True:
                # Checagem vital para evitar Zombie Clients no Redis (Timeout / Vercel cortando sujo)
                if await request.is_disconnected():
                    print(f"SSE Streaming abortado pelo Request Lifecycle (Planilha {id_planilha}).")
                    break

                if rc.redis_client is None:
                    break

                # IMPORTANTE: Lemos sem dar block. Isso devolve a conexao pro pool instantaneamente!
                # Com limite estrito no Redis Cloud (30 conexões), nao podemos reter a conexão em block=2000.
                streams = await rc.redis_client.xread({stream_key: last_id}, count=2)
                
                if streams:
                    for stream_name, messages in streams:
                        for message_id, message_data in messages:
                            if isinstance(message_id, bytes):
                                message_id = message_id.decode("utf-8")
                            last_id = message_id
                            payload = message_data.get("payload", "{}")
                            if isinstance(payload, bytes):
                                payload = payload.decode("utf-8")
                            yield f"id: {message_id}\ndata: {payload}\n\n"
                else:
                    await asyncio.sleep(1.0)
                    yield "event: ping\ndata: \n\n"

        except asyncio.CancelledError:
            print(f"SSE Streaming desconectado pelo cliente (Bypass Direto) para a planilha {id_planilha}.")
        except Exception as e:
            # Captura 'max number of clients reached' e fecha com graciosidade
            print(f"Erro fatal no SSE: {e}")
            yield f"data: {json.dumps({'status': 'erro', 'id': 'fatal', 'mensagem': f'ERRO INTERNO REDIS: {str(e)}'})}\n\n"
            
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

@router.get("/planilhas", response_model=list[PlanilhaResponse], dependencies=[Depends(verify_proxy_secret)])
async def list_planilhas(tenant_id: str = Depends(get_current_tenant)):
    """Lista todos os orçamentos salvos do tenant."""
    try:
        return await get_planilhas_by_tenant(tenant_id)
    except Exception as e:
        print(f"[ERRO DB] Falha ao listar planilhas: {e}")
        raise HTTPException(status_code=500, detail="Falha ao listar orçamentos.")

@router.get("/planilhas/{id_planilha}/linhas", response_model=PlanilhaLinhasResponse, dependencies=[Depends(verify_proxy_secret)])
async def get_planilha_linhas(id_planilha: str, tenant_id: str = Depends(get_current_tenant)):
    """Retorna as linhas e metadados de uma planilha específica."""
    try:
        return await get_linhas_by_planilha(id_planilha, tenant_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado.")
    except Exception as e:
        print(f"[ERRO DB] Falha ao carregar planilha {id_planilha}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao carregar o orçamento.")

@router.delete("/planilhas/{id_planilha}", dependencies=[Depends(verify_proxy_secret)])
async def delete_planilha_route(id_planilha: str, tenant_id: str = Depends(get_current_tenant)):
    """Deleta um orçamento completo pelo seu ID."""
    try:
        await delete_planilha(id_planilha, tenant_id)
        return {"status": "success", "message": "Orçamento deletado."}
    except Exception as e:
        print(f"[ERRO DB] Falha ao deletar planilha {id_planilha}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao excluir o orçamento.")

@router.get("/health")
async def health_check():
    return {"status": "ok", "module": "orcamento"}
