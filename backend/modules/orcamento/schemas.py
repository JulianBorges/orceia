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
    ordem: int = Field(default=0)
    macro_item_context: Optional[str] = None
    projeto_id: Optional[str] = Field(default=None, description="ID do projeto/obra — vincula a linha ao memorial descritivo para Modo Geração")

class LinhaOrcamentoUpsert(LinhaOrcamentoBase):
    id: str # UUID que vem do Frontend

class LoteUpsertRequest(BaseModel):
    linhas: List[LinhaOrcamentoUpsert]
    titulo: Optional[str] = "Orçamento"
    memorial_id: Optional[str] = None

class DeleteLinhasRequest(BaseModel):
    ids: List[str]
    id_planilha: str

class PlanilhaResponse(BaseModel):
    id: str
    titulo: Optional[str]
    created_at: str
    updated_at: str
    memorial_id: Optional[str] = None

class PlanilhaLinhasResponse(BaseModel):
    id_planilha: str
    titulo: Optional[str]
    linhas: List[LinhaOrcamentoUpsert]
    memorial_id: Optional[str] = None


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
        description=(
            "Classifique o risco técnico de uma especificação incorreta deste item. "
            "ALTO: o erro compromete segurança humana ou integridade estrutural. "
            "Exemplos ALTO: concreto estrutural (fck/resistência), aço de armadura, "
            "impermeabilização de fundações, sistemas de combate a incêndio, "
            "instalações elétricas de média/alta tensão, estruturas portantes de madeira ou aço. "
            "BAIXO: todo o restante, incluindo tubulações hidráulicas prediais convencionais "
            "(água fria, esgoto, pluvial), eletrodutos de baixa tensão, instalações elétricas "
            "residenciais/comerciais comuns (tomadas, iluminação, interruptores), "
            "revestimentos, pinturas, terraplanagem, serviços provisórios, "
            "esquadrias e divisórias. Na dúvida: classifique como BAIXO."
        )
    )
    aceito_com_tolerancia: bool = Field(
        default=False,
        description=(
            "True APENAS quando TODAS estas condições forem verdadeiras: "
            "(1) não existe nenhuma opção com especificações exatas do item original na lista apresentada; "
            "(2) a composição aceita difere SOMENTE em atributos NÃO estruturais; "
            "(3) o contexto da busca informar explicitamente que a tolerância dimensional calculada pelo sistema [TOLERÂNCIA: ACEITÁVEL] é aceitável. "
            "Se existir equivalente exato, marque False e selecione o exato. "
            "Se o sistema indicar [TOLERÂNCIA: INACEITÁVEL] ou para atributo estrutural (fck, seção de aço): retorne codigo_selecionado=null."
        )
    )
    codigo_selecionado: Optional[str] = Field(description="O código do item vencedor. Vazio se nenhuma opção atender.")
    parecer_tecnico: str = Field(description="Explicação detalhada da decisão.")
