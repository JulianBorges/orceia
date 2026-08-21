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

class FeedbackRLHF(BaseModel):
    tenant_id: Optional[str] = None
    termo_original: str
    codigo_escolhido: str
    parecer: str = "Aprendizado forçado via UX (RLHF)"

# --- ESTRUTURAS RÍGIDAS PARA A IA (Structured Outputs) ---

class ComposicaoEscolhida(BaseModel):
    codigo: str = Field(description="Código SINAPI do item.")
    descricao: str
    unidade: str
    preco: float
    score: float = Field(description="Percentual de precisão/match.")
    justificativa: str = Field(description="Por que essa composição atende ou não ao item da planilha original?")

class AnaliseIA(BaseModel):
    categoria_rigor: Literal["BAIXO", "ALTO"] = Field(
        description="ALTO para itens estruturais/críticos (elétrica, hidráulica). BAIXO para provisórios/comuns."
    )
    codigo_selecionado: Optional[str] = Field(description="O código do item vencedor. Vazio se nenhuma opção atender.")
    parecer_tecnico: str = Field(description="Explicação detalhada da decisão.")
    composicoes_analisadas: List[ComposicaoEscolhida] = Field(description="A memória de cálculo mostrando os detalhes técnicos das opções avaliadas.")
