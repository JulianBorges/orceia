# backend/modules/auditoria/routes.py
"""
Endpoints do módulo Auditoria — Pipeline Bidirecional de Memoriais Descritivos.

POST /auditoria/ingerir-memorial   → PDF → Pinecone (Etapa A: fundação compartilhada)
GET  /auditoria/status/{id}        → Verifica se memorial está carregado
POST /auditoria/auditar-planilha   → SSE — Cruza orçamento com memorial (Modo Auditoria)
"""
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from core.security import verify_proxy_secret, get_current_tenant
from modules.auditoria.schemas import (
    IngerirMemorialResponse,
    StatusMemorialResponse,
    LoteAuditoriaRequest,
)
from modules.auditoria.services import (
    ingerir_memorial_pdf,
    buscar_contexto_memorial,
    checar_status_memorial,
)
from modules.auditoria.ai_agent import auditar_item_contra_memorial

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.post(
    "/ingerir-memorial",
    response_model=IngerirMemorialResponse,
    dependencies=[Depends(verify_proxy_secret)],
)
async def ingerir_memorial(
    arquivo: UploadFile = File(..., description="Arquivo PDF do memorial descritivo"),
    projeto_id: str = Form(default=None, description="ID do projeto. Gerado automaticamente se omitido."),
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Ingere um PDF de memorial descritivo:
    1. Extrai texto via pypdf
    2. Chunkeia por parágrafo semântico
    3. Gera embeddings (text-embedding-3-small)
    4. Salva no Pinecone (namespace: memorial:{tenant_id}:{projeto_id})

    Retorna o projeto_id para vincular ao orçamento no frontend.
    """
    # Validação de tipo de arquivo
    if not arquivo.filename or not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF (.pdf) são aceitos.")

    # Gera projeto_id se não fornecido pelo cliente
    if not projeto_id:
        projeto_id = str(uuid.uuid4())

    conteudo = await arquivo.read()

    if len(conteudo) == 0:
        raise HTTPException(status_code=400, detail="Arquivo PDF vazio.")

    try:
        chunks = await ingerir_memorial_pdf(conteudo, tenant_id, projeto_id)
        return IngerirMemorialResponse(
            projeto_id=projeto_id,
            chunks_gerados=chunks,
            status="pronto",
        )
    except ValueError as e:
        # PDF escaneado ou sem texto extraível
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"[AUDITORIA] Erro inesperado ao ingerir memorial: {e}")
        raise HTTPException(status_code=500, detail="Falha ao processar o PDF. Tente novamente.")


@router.get(
    "/status/{projeto_id}",
    response_model=StatusMemorialResponse,
    dependencies=[Depends(verify_proxy_secret)],
)
async def status_memorial(
    projeto_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Verifica se o memorial de um projeto já foi ingerido e está pronto para consulta."""
    resultado = await checar_status_memorial(tenant_id, projeto_id)
    return StatusMemorialResponse(projeto_id=projeto_id, **resultado)


@router.post(
    "/auditar-planilha",
    dependencies=[Depends(verify_proxy_secret)],
)
async def auditar_planilha(
    lote: LoteAuditoriaRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Modo Auditoria (SSE): Cruza cada linha do orçamento contra o memorial descritivo.
    Retorna um Laudo de Conformidade via Server-Sent Events.

    Cada evento SSE contém:
      { "status": "sucesso", "dados": { "id", "status_conformidade", "justificativa", "trecho_memorial" } }
    Evento final:
      { "status": "auditoria_concluida", "total": N }
    """
    if not lote.linhas:
        raise HTTPException(status_code=400, detail="Nenhum item enviado para auditoria.")

    # Semáforo local de auditoria — controla chamadas à OpenAI sem bloquear o SSE
    # Valor conservador: auditoria é menos urgente que orçamentação e compartilha cota da API
    import asyncio as _asyncio
    _sem = _asyncio.Semaphore(5)

    async def auditar_linha_com_semaforo(linha):
        """Processa um item com controle de concorrência, retornando o dict de resultado."""
        async with _sem:
            trechos = await buscar_contexto_memorial(
                linha.descricao, tenant_id, lote.projeto_id
            )
            if not trechos:
                return {
                    "id": linha.id,
                    "status_conformidade": "SEM_REFERENCIA",
                    "justificativa": "O memorial não menciona este tipo de serviço.",
                    "trecho_memorial": None,
                }
            analise = await auditar_item_contra_memorial(
                linha.descricao, linha.codigo, trechos
            )
            print(f"[AUDITORIA CoT] Item '{linha.descricao[:50]}': {analise.raciocinio_auditoria}")
            return {
                "id": linha.id,
                "status_conformidade": analise.status_conformidade,
                "justificativa": analise.justificativa,
                "trecho_memorial": analise.trecho_memorial,
            }

    async def event_generator():
        # Cria todas as tasks de auditoria de uma vez (o semáforo controla a concorrência)
        tasks = [
            _asyncio.create_task(auditar_linha_com_semaforo(linha))
            for linha in lote.linhas
        ]

        for task in tasks:
            try:
                resultado = await task
                yield f"data: {json.dumps({'status': 'sucesso', 'dados': resultado}, ensure_ascii=False)}\n\n"
            except Exception as e:
                # Tenta identificar qual linha falhou para notificar o frontend
                yield f"data: {json.dumps({'status': 'erro', 'mensagem': str(e)}, ensure_ascii=False)}\n\n"

        # Evento de conclusão
        yield f"data: {json.dumps({'status': 'auditoria_concluida', 'total': len(lote.linhas)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
