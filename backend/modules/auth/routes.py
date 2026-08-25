from fastapi import APIRouter, Depends, HTTPException, Header
from core.config import settings
from core.db import get_db_pool

router = APIRouter(prefix="/auth", tags=["auth"])


async def verify_proxy_secret(x_api_secret: str = Header(...)):
    if x_api_secret != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    return x_api_secret


@router.get("/validate-tenant", dependencies=[Depends(verify_proxy_secret)])
async def validate_tenant(x_tenant_id: str = Header(None)):
    """
    Valida se um tenant_id está autorizado a operar no sistema.
    Consultado pelo proxy Next.js no momento do login, antes de setar o cookie.
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(status_code=400, detail="tenant_id ausente")

    pool = get_db_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT id FROM tenants WHERE id = $1 AND ativo = true",
            x_tenant_id.strip()
        )

    if not record:
        raise HTTPException(
            status_code=401,
            detail="Tenant não autorizado. Solicite acesso ao administrador."
        )

    return {"status": "authorized", "tenant": x_tenant_id}
