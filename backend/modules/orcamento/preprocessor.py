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


# Padrao revisado: captura dimensões sem espaço, dimensões cruzadas e unidades coladas.
# Protege ângulos como "45" ou "90" se seguidos por "graus" ou se não tiverem unidade de medida.
_PADRAO_DIMENSIONAL = re.compile(
    # Dimensões cruzadas: 75x50mm, 50X40MM, 100 x 100 x 50
    r'\b\d+[.,]?\d*\s*[xX×]\s*\d+[.,]?\d*(?:\s*[xX×]\s*\d+[.,]?\d*)?\s*'
    r'(?:mm2?|cm|m2|m3|m\b|kg|kn|kpa|mpa|awg|bwg)?\b'
    # Unidade colada ao número sem espaço: 35MM2, 6MM2, 110MM, 8AWG
    r'|\b\d+[.,]?\d*(?:mm2?|cm2?|dm|m2|m3|kg|kn|kpa|mpa|fck|kgf|psi|mca|kva|kw|kwh|hp|awg|bwg)\b'
    # Unidade com espaço: 35 MM, 6 MM², 50 cm
    r'|\b\d+[.,]?\d*\s+(?:mm|cm|dm|m2|m3|m|kg|kn|kpa|mpa|fck|kgf|psi|mca|kva|kw|kwh|hp|l|lt)\b'
    # Números isolados (com proteções de contexto para ângulos e multiplicadores)
    r'|(?<!tipo\s)(?<!fase\s)(?<!vez\s)(?<!/)(?<!\d[xX])\b\d+[.,]?\d*\b(?!\s*(?:vez|tipo|fase|graus?|/))',
    re.IGNORECASE
)


# Siglas de referência/escala técnica que NÃO são dimensões mas poluem o embedding se mantidas
_SIGLAS_REFERENCIA = re.compile(
    r'\b(?:AWG|BWG|AF_\d{2}/\d{4}|NM\b|ISO\b)\b',
    re.IGNORECASE
)


from core.vocabulario_obra import SINONIMOS_CANTEIRO

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

    # --- Nova camada Léxica (Dicionário de Canteiro) ---
    # Traduz jargões populares para a taxonomia técnica
    desc_lower = descricao.lower()
    for jargao, tecnico in SINONIMOS_CANTEIRO.items():
        # Regex com word boundary para substituir apenas palavras inteiras
        pattern = r'\b' + re.escape(jargao) + r'\b'
        desc_lower = re.sub(pattern, tecnico, desc_lower)
    
    descricao = desc_lower

    raw_specs = _PADRAO_DIMENSIONAL.findall(descricao)

    # Remove as especificacoes dimensionais do nucleo
    termo_limpo = _PADRAO_DIMENSIONAL.sub(' ', descricao)
    # Remove siglas de referência técnica que degradam o embedding
    termo_limpo = _SIGLAS_REFERENCIA.sub(' ', termo_limpo)
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

def extrair_dimensoes_numericas(texto: str) -> list[float]:
    """
    Extrai apenas os valores numéricos puros (como floats) das dimensões contidas no texto,
    ignorando as unidades. Usado para comparação matemática de tolerância (ex: 100mm vs 110mm).
    """
    if not texto:
        return []
        
    specs = _PADRAO_DIMENSIONAL.findall(texto)
    valores = []
    
    _NUMEROS = re.compile(r'\b\d+(?:[.,]\d+)?\b')
    
    for spec in specs:
        numeros_str = _NUMEROS.findall(spec)
        for num_str in numeros_str:
            try:
                valores.append(float(num_str.replace(',', '.')))
            except ValueError:
                pass
                
    return valores
