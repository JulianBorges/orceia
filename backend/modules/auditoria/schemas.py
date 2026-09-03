# backend/modules/auditoria/schemas.py
from pydantic import BaseModel
from typing import Optional, Literal, List


class IngerirMemorialResponse(BaseModel):
    projeto_id: str
    chunks_gerados: int
    status: str


class StatusMemorialResponse(BaseModel):
    projeto_id: str
    status: Literal["pronto", "nao_encontrado", "erro"]
    chunks: int


class LinhaAuditoriaInput(BaseModel):
    """Representa uma linha do orçamento para o Modo Auditoria."""
    id: str
    descricao: str
    codigo: Optional[str] = None
    status_ia: Optional[str] = None


class LoteAuditoriaRequest(BaseModel):
    projeto_id: str
    linhas: List[LinhaAuditoriaInput]
