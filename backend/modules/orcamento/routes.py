from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from fastapi.responses import StreamingResponse
from core.config import settings
from modules.orcamento.schemas import LoteUpsertRequest, FeedbackRLHF
from modules.orcamento.services import iniciar_processamento_lote_em_background
from core.db import get_db_pool
import core.redis_client as rc
import asyncio
import json

router = APIRouter(prefix="/orcamento", tags=["orcamento"])

async def verify_proxy_secret(x_api_secret: str = Header(...)):
    if x_api_secret != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    return x_api_secret

@router.post("/feedback", dependencies=[Depends(verify_proxy_secret)])
async def save_rlhf_feedback(feedback: FeedbackRLHF):
    """Guarda a decisão humana no banco (Memória Organizacional B2B)"""
    query = """
        INSERT INTO memoria_organizacional (tenant_id, termo_original, codigo_escolhido, parecer)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (tenant_id, termo_original) 
        DO UPDATE SET codigo_escolhido = $3, parecer = $4
    """
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, feedback.tenant_id, feedback.termo_original.strip().lower(), feedback.codigo_escolhido, feedback.parecer)
        return {"status": "success", "message": "Feedback memorizado para o Tenant"}
    except Exception as e:
        print(f"Erro salvando RLHF (talvez a tabela não exista ainda): {e}")
        return {"status": "error", "message": str(e)}

@router.post("/upsert-linhas", dependencies=[Depends(verify_proxy_secret)])
async def upsert_linhas(lote: LoteUpsertRequest, background_tasks: BackgroundTasks):
    if not lote.linhas:
        return {"status": "success"}
    
    planilha_id = lote.linhas[0].id_planilha
    # Despacha a bomba para o background. O Frontend fica livre instantaneamente (0 latência)
    background_tasks.add_task(iniciar_processamento_lote_em_background, lote.linhas, planilha_id)
    
    return {"status": "processing_started", "linhas": len(lote.linhas)}

@router.get("/stream/{id_planilha}")
async def sse_stream(id_planilha: str, last_event_id: str = Header(default="0-0")):
    """Canal de Eventos (SSE). O frontend escuta aqui e atualiza a UI instantaneamente"""
    async def event_generator():
        stream_key = f"stream:planilha:{id_planilha}"
        last_id = last_event_id
        
        try:
            while True:
                # XREAD trava o loop (block=5000ms) esperando novos itens a partir do last_id
                # Isso impede loop infinito vazio no processador.
                if rc.redis_client is None:
                    break
                    
                streams = await rc.redis_client.xread({stream_key: last_id}, block=5000, count=10)
                
                if streams:
                    for stream_name, messages in streams:
                        for message_id, message_data in messages:
                            last_id = message_id
                            payload = message_data.get("payload", "{}")
                            
                            # Cuidado: O protocolo SSE requer que os dados iniciem com 'data: '
                            yield f"id: {message_id}\ndata: {payload}\n\n"
                            
                else:
                    # Envia ping para manter conexão TCP viva no Cloud Run/Vercel
                    yield ": ping\n\n"
                    
        except asyncio.CancelledError:
            # O usuário fechou a aba ou internet caiu
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
