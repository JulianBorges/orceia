from fastapi import APIRouter, Depends, HTTPException, Header
from core.config import settings
from modules.orcamento.search_engine import _postgres_search

router = APIRouter(prefix="/sinapi", tags=["sinapi"])

async def verify_proxy_secret(x_api_secret: str = Header(...)):
    if x_api_secret != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    return x_api_secret

@router.get("/search", dependencies=[Depends(verify_proxy_secret)])
async def search_sinapi(q: str):
    """
    Busca manual de composições no banco de dados Lexical (PostgreSQL).
    Retorna opções para o menu de Autocomplete do Frontend.
    """
    if not q or len(q) < 3:
        return {"results": []}
        
    # Usamos o Trigramas do PostgreSQL para alta performance
    records = await _postgres_search(q, tipo="composicoes")
    
    results = []
    for r in records:
        results.append({
            "codigo": r["codigo"],
            "descricao": r["descricao"],
            "preco": r["preco"],
            "unidade": r["unidade"],
            "score": r["score_lexico"]
        })
        
    return {"results": results}
