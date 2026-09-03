from fastapi import APIRouter, Depends
from core.security import verify_proxy_secret
from modules.eap.schemas import EstruturarEAPRequest, EstruturarEAPResponse, LinhaSaida
from modules.eap.ai_agent import estruturar_eap_com_ia

router = APIRouter(
    prefix="/eap",
    tags=["EAP"],
    dependencies=[Depends(verify_proxy_secret)]
)

@router.post("/estruturar", response_model=EstruturarEAPResponse)
async def estruturar_eap(request: EstruturarEAPRequest):
    # Converter para dict
    linhas_originais = [linha.model_dump() for linha in request.linhas]
    
    # Processar com IA
    linhas_estruturadas = await estruturar_eap_com_ia(linhas_originais)
    
    # Converter de volta para schema
    resultado = [LinhaSaida(**linha) for linha in linhas_estruturadas]
    return EstruturarEAPResponse(linhas=resultado)
