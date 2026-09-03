from pydantic import BaseModel, Field
from typing import List, Optional

class LinhaEntrada(BaseModel):
    id: str
    descricao: str

class EstruturarEAPRequest(BaseModel):
    linhas: List[LinhaEntrada]

class LinhaSaida(BaseModel):
    id: Optional[str] = None
    item: Optional[str] = None
    descricao: str
    is_macro_item: bool

class EstruturarEAPResponse(BaseModel):
    linhas: List[LinhaSaida]
