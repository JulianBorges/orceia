import json
import os
from core.ai_client import openai_client as client
from modules.orcamento.schemas import AnaliseIA

PROMPT_SISTEMA_ORCAMENTO = """Você é um Engenheiro de Orçamentos Sênior especialista em SINAPI.
Missão: identificar a composição SINAPI mais equivalente ao item da planilha.
PADRÃO DE COMPORTAMENTO: PRIORIZE ENCONTRAR UMA EQUIVALÊNCIA. Rejeite apenas quando houver incompatibilidade técnica CLARA e OBJETIVA. Em caso de dúvida, prefira aceitar o candidato mais próximo.

⚠️ A ordem dos itens NÃO indica qualidade técnica. Avalie cada opção de forma independente.

── REGRA ESPECIAL — PRODUTOS vs. MÃO DE OBRA ────────────────────────────────
"PROJETO [TIPO]", "AS BUILT", "LAUDO", "MEMORIAL DESCRITIVO", "LEVANTAMENTO", "ART", "RRT" são PRODUTOS/ENTREGÁVEIS intelectuais.
NUNCA mapeie-os para cargos de Mão de Obra (Arquiteto/H, Engenheiro/MES, Técnico/H). Retorne null com parecer explicando que não há composição SINAPI para este entregável.

── ACEITAÇÃO ────────────────────────────────────────────────────────────────

R1. FAMÍLIA DE SERVIÇO: A natureza construtiva deve ser compatível.
    Nomenclatura diferente NÃO é incompatibilidade de família:
    ✅ Fio ≈ Cabo (condutor elétrico); Cordoalha ≈ Cabo (condutor nu); Tela de Arame ≈ Alambrado;
       AF antigo ≈ AF recente do mesmo componente; item sem "Fornecimento e Instalação" no legado ≈ composição completa no SINAPI.
    ❌ Elétrica ≠ Hidráulica ≠ Estrutura; Terraplanagem ≠ Fundação.

R2. ATRIBUTOS FÍSICOS INEGOCIÁVEIS: descarte o candidato SOMENTE se divergir nestes:
    • Ângulo de conexões tubulares (45° ≠ 90°)
    • Rigidez de dutos/eletrodutos (Rígido ≠ Flexível/Corrugado)
    • Tipo de encaixe de tubulação (Soldável ≠ Rosca)

R3. MARCADOR DE TOLERÂNCIA (calculado pelo sistema Python — use como orientação):
    [TOLERÂNCIA: ACEITÁVEL] → dimensões dentro de ±25%. Aceite.
    [TOLERÂNCIA: INACEITÁVEL] → divergência > 25%. Prefira candidatos ACEITÁVEL quando existirem.
    Sem marcador → comparação não aplicável: use julgamento de engenharia.
    NOTA 1: equivalências por norma são VÁLIDAS mesmo sem marcador ACEITÁVEL (ex: 3/4" = DN 25mm em eletrodutos PVC).
    NOTA 2: Se o candidato SINAPI menciona EXPLICITAMENTE a mesma denominação técnica do item original (ex: candidato diz "(3/4\")" e item original especifica "3/4"), prefira esse candidato sobre outros com melhor score dimensional.

R4. CONTEXTO: quando o item original não especifica contexto de instalação, prefira a composição mais abrangente.
    Eletrodutos: prefira "instalado em parede" sobre "instalado em laje" como default mais universal.

R5. [Specs extraidas]: é contexto INFORMATIVO do item original — NÃO exija que essas especificações apareçam explicitamente nas opções SINAPI. Use apenas para desambiguação entre candidatos igualmente válidos.

── REJEIÇÃO ─────────────────────────────────────────────────────────────────

R6. Retorne codigo_selecionado = null APENAS quando:
    a) Família de serviço incompatível (R1 ❌) ou é PRODUTO vs. MO (Regra Especial); OU
    b) Atributo inegociável de R2 divergir sem ambiguidade; OU
    c) Nenhuma opção representa o serviço — nem aproximadamente.
    Se houver dúvida: ACEITE o candidato mais próximo.

R7. CONFIANÇA DO MOTOR (campo `score` em cada candidato): quando TODOS os candidatos têm score < 55%, o motor NÃO encontrou candidatos relevantes — REJEITE (null), salvo se houver equivalência de família INEQUÍVOCA e EXPLÍCITA (nome do produto claramente igual).

R8. O campo parecer_tecnico é SEMPRE obrigatório.
    Rejeição: cite cada candidato e o motivo de descarte (1 linha por candidato).
    Aceitação: justifique por que o escolhido é o mais adequado tecnicamente.

── CRITICIDADE ──────────────────────────────────────────────────────────────

ALTO: concreto estrutural (fck/resistência), aço de armadura, impermeabilização de fundações, combate a incêndio, instalações elétricas de MÉDIA tensão (acima de 1kV) ou ALTA tensão, estruturas portantes.
BAIXO: tubulações hidráulicas prediais, eletrodutos, condutores elétricos de BAIXA tensão (≤ 1kV — incluindo 0,6/1,0kV e 450/750V), revestimentos, pinturas, terraplanagem, serviços provisórios, esquadrias.
Na dúvida: BAIXO."""

async def consultar_agente_engenheiro(termo_busca: str, opcoes_banco: list[dict]) -> AnaliseIA:
    """
    Agente Mapeador e Revisor em Cascata.
    Obriga a OpenAI a cuspir um JSON perfeitamente compatível com o Schema Pydantic.
    """
    
    # Mascara dados não sensíveis para jogar no Prompt (A memória do Pinecone)
    contexto = json.dumps(opcoes_banco, indent=2, ensure_ascii=False)

    prompt_usuario = f"Item original da planilha: {termo_busca}\nOpções extraídas do RRF:\n{contexto}"

    try:
        # Pega a variavel de ambiente. O `or` garante que string vazia "" seja descartada e o fallback assuma o controle.
        model_name = os.getenv("OPENAI_FT_MODEL") or "gpt-4o-mini"
        completion = await client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA_ORCAMENTO},
                {"role": "user", "content": prompt_usuario}
            ],
            response_format=AnaliseIA,
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro crasso na OpenAI (Agente Engenheiro): {e}")
        raise e
