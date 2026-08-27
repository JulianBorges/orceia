# backend/modules/orcamento/preprocessor.py
"""
Agente Corretor de Termos — Pré-processamento para o Motor RRF.

Extrai especificações dimensionais/numéricas do núcleo semântico da descrição
antes de gerar o embedding vetorial (Pinecone). As características são preservadas
para análise lógica posterior pelo Agente Mapeador no prompt do GPT.

Exemplos de transformação:
  "CONCRETO FCK 30 MPA ESPESSURA 15CM" -> termo_limpo: "CONCRETO USINADO BOMBEADO"
                                           caracteristicas: "FCK 30 MPA ESPESSURA 15CM"
  "TUBO PVC 100MM JE"                  -> termo_limpo: "TUBO PVC JE"
                                           caracteristicas: "100MM"
  "ALVENARIA DE TIJOLO"                -> termo_limpo: "ALVENARIA DE TIJOLO"
                                           caracteristicas: ""
"""
import re
from pydantic import BaseModel


class TermoNormalizado(BaseModel):
    termo_limpo: str
    """Nucleo semantico sem dimensoes — otimizado para embedding vetorial."""
    caracteristicas_extras: str
    """Especificacoes dimensionais/numericas extraidas — contexto para o Agente Mapeador."""


# Padrao: numeros seguidos (ou nao) por unidades de engenharia
_PADRAO_DIMENSIONAL = re.compile(
    r'\b\d+[\.,]?\d*\s*'
    r'(mm|cm|dm|m2|m3|m|kg|kn|kpa|mpa|fck|kgf|psi|mca|kva|kw|kwh|hp|l|lt)?\b',
    re.IGNORECASE
)


def normalizar_termo_busca(descricao: str) -> TermoNormalizado:
    """
    Separa o nucleo semantico da descricao de suas especificacoes numericas.

    Args:
        descricao: Descricao original do item da planilha.

    Returns:
        TermoNormalizado com `termo_limpo` (para embedding) e
        `caracteristicas_extras` (para contexto do agente IA).
    """
    descricao = descricao.strip()
    if not descricao:
        return TermoNormalizado(termo_limpo="", caracteristicas_extras="")

    raw_specs = _PADRAO_DIMENSIONAL.findall(descricao)

    # Remove as especificacoes do nucleo
    termo_limpo = _PADRAO_DIMENSIONAL.sub(' ', descricao)
    # Limpa espacos duplos resultantes da remocao
    termo_limpo = ' '.join(termo_limpo.split()).strip()

    # Fallback: se o termo ficou vazio (era tudo numero), usa o original
    if not termo_limpo:
        return TermoNormalizado(termo_limpo=descricao, caracteristicas_extras="")

    # Preserva a descricao original como contexto dimensional compacto
    caracteristicas = descricao[:150] if raw_specs else ""

    return TermoNormalizado(
        termo_limpo=termo_limpo,
        caracteristicas_extras=caracteristicas
    )
