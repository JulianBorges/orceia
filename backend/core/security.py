from fastapi import Header, HTTPException
from core.config import settings

async def verify_proxy_secret(x_api_secret: str = Header(...)):
    """Verifica que a requisicao vem do Proxy Next.js interno (nao do browser)."""
    if x_api_secret != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso nao autorizado")
    return x_api_secret

async def get_current_tenant(x_tenant_id: str = Header(None)):
    """Extrai o Tenant ID do header injetado pelo middleware Next.js."""
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail="Sessao Expirada ou Tenant Nao Encontrado")
    return x_tenant_id

from fastapi import Query
import core.redis_client as rc

async def verify_stream_token(token: str = Query(...)):
    """Valida Token Efêmero de Streaming (Bypass Proxy)"""
    if not rc.redis_client:
        raise HTTPException(status_code=500, detail="Redis offline")
    
    tenant_id = await rc.redis_client.get(f"sse_token:{token}")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token de Streaming Invalido ou Expirado")
    
    # decode porque o aioredis retorna bytes as vezes
    if isinstance(tenant_id, bytes):
        tenant_id = tenant_id.decode('utf-8')
        
    return tenant_id
