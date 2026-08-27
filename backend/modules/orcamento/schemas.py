from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class LinhaOrcamentoBase(BaseModel):
    id_planilha: str
    tenant_id: Optional[str] = Field(default=None, description="Injetado pelo Header de Auth Server-Side")
    codigo: Optional[str] = None
    descricao: str
    unidade: str
    quantidade: float = Field(default=0.0)
    preco_unitario: float = Field(default=0.0)

class LinhaOrcamentoUpsert(LinhaOrcamentoBase):
    id: str # UUID que vem do Frontend

class LoteUpsertRequest(BaseModel):
    linhas: List[LinhaOrcamentoUpsert]

class DeleteLinhasRequest(BaseModel):
    ids: List[str]
    id_planilha: str

class FeedbackRLHF(BaseModel):
    tenant_id: Optional[str] = None
    termo_original: str
    codigo_escolhido: str
    parecer: str = "Aprendizado forçado via UX (RLHF)"

# --- ESTRUTURAS RÍGIDAS PARA A IA (Structured Outputs) ---

class AnaliseIA(BaseModel):
    raciocinio_step_by_step: str = Field(
        description="PENSE ANTES DE AGIR: Analise a família do item original, compare restrições físicas (dimensões, tipo de serviço) com as opções, e justifique os prós/contras antes de emitir qualquer classificação."
    )
    categoria_rigor: Literal["BAIXO", "ALTO"] = Field(
        description="ALTO para itens estruturais/críticos (elétrica, hidráulica). BAIXO para provisórios/comuns."
    )
    aceito_com_tolerancia: bool = Field(
        default=False,
        description="True SOMENTE se não houver equivalente exato e a diferença dimensional for <=15% em atributo NÃO estrutural. Implica status RESSALVA obrigatório. False para rejeição ou aceitação exata."
    )
    codigo_selecionado: Optional[str] = Field(description="O código do item vencedor. Vazio se nenhuma opção atender.")
    parecer_tecnico: str = Field(description="Explicação detalhada da decisão.")
