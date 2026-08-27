from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse
from core.config import settings
from modules.orcamento.schemas import LoteUpsertRequest, FeedbackRLHF, DeleteLinhasRequest
from modules.orcamento.services import (
    iniciar_processamento_lote_em_background,
    bulk_upsert_linhas_orcamento,
    bulk_delete_linhas_orcamento,
)
from core.db import get_db_pool
import core.redis_client as rc
from core.redis_client import delete_ai_cache
import asyncio
import json

router = APIRouter(prefix="/orcamento", tags=["orcamento"])

from core.security import verify_proxy_secret, get_current_tenant

@router.post("/feedback", dependencies=[Depends(verify_proxy_secret)])
async def save_rlhf_feedback(feedback: FeedbackRLHF, tenant_id: str = Depends(get_current_tenant)):
    """Guarda a decisão humana no banco (Memória Organizacional B2B)"""
    # Blindagem: Ignora o que o cliente mandou no JSON e força o uso do Tenant Autenticado no Cookie
    feedback.tenant_id = tenant_id
    query = """
        INSERT INTO memoria_organizacional (tenant_id, termo_original, codigo_escolhido, parecer)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (tenant_id, termo_original) 
        DO UPDATE SET codigo_escolhido = $3, parecer = $4, updated_at = CURRENT_TIMESTAMP
    """
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, feedback.tenant_id, feedback.termo_original.strip().lower(), feedback.codigo_escolhido, feedback.parecer)
        # Invalida o cache Redis para o termo corrigido pelo humano
        await delete_ai_cache(feedback.termo_original)
        print(f"[RLHF] Cache invalidado para: '{feedback.termo_original[:50]}'")
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
        
    # Despacha a bomba para o background. O Frontend fica livre instantaneamente (0 latência)
    background_tasks.add_task(iniciar_processamento_lote_em_background, lote.linhas, planilha_id)
    
    return {"status": "processing_started", "linhas": len(lote.linhas)}

@router.post("/save-linhas", dependencies=[Depends(verify_proxy_secret)])
async def save_linhas(lote: LoteUpsertRequest, tenant_id: str = Depends(get_current_tenant)):
    """
    Persiste as alterações instantâneas (Auto-Save) oriundas do frontend.
    """
    if not lote.linhas:
        return {"status": "success"}
    
    try:
        await bulk_upsert_linhas_orcamento(lote.linhas, tenant_id)
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

@router.get("/stream/{id_planilha}", dependencies=[Depends(verify_proxy_secret)])
async def sse_stream(id_planilha: str, last_event_id: str = Header(default="0-0"), tenant_id: str = Depends(get_current_tenant)):
    """Canal de Eventos (SSE). O frontend escuta aqui e atualiza a UI instantaneamente"""
    async def event_generator():
        stream_key = f"stream:{tenant_id}:planilha:{id_planilha}"
        last_id = last_event_id
        MAX_IDLE_PINGS_POS_CONCLUSAO = 12  # 12 x 5s = 60s apos lote_concluido
        idle_count = 0
        lote_concluido = False

        try:
            while True:
                if rc.redis_client is None:
                    break

                streams = await rc.redis_client.xread({stream_key: last_id}, block=5000, count=10)

                if streams:
                    idle_count = 0
                    for stream_name, messages in streams:
                        for message_id, message_data in messages:
                            last_id = message_id
                            payload = message_data.get("payload", "{}")
                            yield f"id: {message_id}\ndata: {payload}\n\n"

                            try:
                                data = json.loads(payload)
                                if data.get("status") == "lote_concluido":
                                    lote_concluido = True
                            except (json.JSONDecodeError, AttributeError):
                                pass
                else:
                    idle_count += 1
                    if lote_concluido and idle_count >= MAX_IDLE_PINGS_POS_CONCLUSAO:
                        print(f"[SSE] Stream encerrado por idle timeout (planilha: {id_planilha})")
                        break
                    yield ": ping\n\n"

        except asyncio.CancelledError:
            print(f"SSE Streaming desconectado pelo cliente para a planilha {id_planilha}.")
        except Exception as e:
            print(f"Erro fatal no SSE: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'status': 'erro', 'id': 'fatal', 'mensagem': f'ERRO INTERNO REDIS: {str(e)}'})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/health")
async def health_check():
    return {"status": "ok", "module": "orcamento"}
