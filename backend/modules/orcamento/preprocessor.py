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

# Variante RESTRITA do padrão dimensional: só extrai números com unidade EXPLÍCITA.
# Usada em extrair_dimensoes_numericas para comparação de tolerância.
# Exclui números isolados sem unidade (ex: "2 DEMÃOS", "90 DIAS") para evitar
# falsos positivos no cálculo de tolerância dimensional.
_PADRAO_DIMENSIONAL_COM_UNIDADE = re.compile(
    # Dimensões cruzadas: 75x50mm, 4x4cm, 50X40MM
    r'\b\d+[.,]?\d*\s*[xX×]\s*\d+[.,]?\d*(?:\s*[xX×]\s*\d+[.,]?\d*)?\s*'
    r'(?:mm2?|cm2?|m2|m3|m\b|kg|kn|kpa|mpa|awg|bwg)?\b'
    # Unidade colada: 35MM2, 6MM2, 110MM, 8AWG, 2,77MM
    r'|\b\d+[.,]?\d*(?:mm2?|cm2?|dm|m2|m3|kg|kn|kpa|mpa|fck|kgf|psi|mca|kva|kw|kwh|hp|awg|bwg)\b'
    # Unidade com espaço: 35 MM, 50 CM, 20 CM, 6 MM²
    r'|\b\d+[.,]?\d*\s+(?:mm|cm|dm|m2|m3|m|kg|kn|kpa|mpa|fck|kgf|psi|mca|kva|kw|kwh|hp|l|lt)\b',
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

    # --- Sinonimização Contextual (não pode ser feita no dicionário global) ---
    # "fio → cabo" APENAS em contexto elétrico (condutor isolado, AWG, mm², etc.)
    # Evita substituir "fio" em "TELA ARAME FIO 12 BWG" (arame de malha ≠ condutor).
    # ATENÇÃO: usa mm2|mm² (seção elétrica), NÃO mm2? que casaria com mm simples em dimensões.
    _CONTEXTO_ELETRICO = re.compile(
        r'(isolado|mm2|mm²|awg|kwh|kv\b|circuito|cobre|anti.chama|fase|neutro|terra)',
        re.IGNORECASE
    )
    if _CONTEXTO_ELETRICO.search(descricao):
        descricao = re.sub(r'\bfio\b', 'cabo', descricao, flags=re.IGNORECASE)

    # "cordoalha → cabo" (CABO DE COBRE NU = CORDOALHA DE COBRE NU no SINAPI)
    descricao = re.sub(r'\bcordoalha\b', 'cabo', descricao, flags=re.IGNORECASE)

    # "juncao simples → juncao reducao" (SINAPI usa "redução invertida")
    descricao = re.sub(r'\bjuncao\s+simples\b', 'juncao reducao', descricao, flags=re.IGNORECASE)

    raw_specs = _PADRAO_DIMENSIONAL.findall(descricao)

    # Remove as especificacoes dimensionais do nucleo
    termo_limpo = _PADRAO_DIMENSIONAL.sub(' ', descricao)
    # Remove siglas de referência técnica que degradam o embedding
    termo_limpo = _SIGLAS_REFERENCIA.sub(' ', termo_limpo)

    # Bug Fix: Remove pontuação órfã resultante da extração dimensional.
    # Ex: "6,0MM2 (8AWG)" → "( )" → removido.
    # Parênteses vazios ou com só espaço/pontuação dentro:
    termo_limpo = re.sub(r'\(\s*[^a-zA-ZÀ-ú]*\s*\)', ' ', termo_limpo)
    # Vírgulas, barras, travessões e hifens isolados no final ou entre espaços:
    termo_limpo = re.sub(r'(?<!\w)[,;/\\-](?!\w)', ' ', termo_limpo)
    # Trailing pontuação solta:
    termo_limpo = re.sub(r'[\s,;/\\.:-]+$', '', termo_limpo)

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
    Extrai apenas os valores numéricos com UNIDADE EXPLÍCITA (mm, cm, kg, etc.) do texto.
    Exclui números isolados sem unidade (ex: "2 DEMÃOS", "90 DIAS") para evitar
    falsos positivos no cálculo de tolerância dimensional.
    Usado para comparação matemática de tolerância (ex: 100mm vs 110mm).
    """
    if not texto:
        return []
        
    # Usa o padrão RESTRITO que exige unidade explícita — não extrai contagens simples
    specs = _PADRAO_DIMENSIONAL_COM_UNIDADE.findall(texto)
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


def injetar_tolerancia_dimensional(descricao_usuario: str, opcoes_rrf: list[dict]) -> None:
    """
    Injeta o marcador [TOLERÂNCIA: ACEITÁVEL] ou [TOLERÂNCIA: INACEITÁVEL] em cada
    opção do RRF, comparando suas dimensões numéricas COM UNIDADE com as do item do usuário.

    Tolerância aceita: desvio <= 25% por dimensão (cobre equivalências métricas/imperiais
    como 3/4" = DN 25mm e malhas próximas como 4x4cm ≈ 5x5cm).
    Regra de comparação: apenas quando o número de dimensões do SINAPI bate com o do usuário.
    Números sem unidade (ex: "2 DEMÃOS") são ignorados na comparação.

    Modifica `opcoes_rrf` in-place. Função compartilhada entre services.py e scripts de diagnóstico.
    """
    dimensoes_usuario = extrair_dimensoes_numericas(descricao_usuario)
    if not dimensoes_usuario:
        return

    for op in opcoes_rrf:
        dimensoes_sinapi = extrair_dimensoes_numericas(op.get("descricao", ""))
        tolerancia_ok = False

        if dimensoes_sinapi and len(dimensoes_sinapi) == len(dimensoes_usuario):
            diffs_ok = True
            for du, ds in zip(dimensoes_usuario, dimensoes_sinapi):
                if ds == 0:
                    diffs_ok = False
                    break
                diff = abs(du - ds) / ds
                if diff > 0.25:   # 25% threshold — cobre equivalências métricas/imperiais
                    diffs_ok = False
                    break
            tolerancia_ok = diffs_ok

        if tolerancia_ok:
            op["descricao"] += " [TOLERÂNCIA: ACEITÁVEL]"
        else:
            op["descricao"] += " [TOLERÂNCIA: INACEITÁVEL]"
