import json
from core.ai_client import openai_client as client
from modules.orcamento.schemas import AnaliseIA

async def consultar_agente_engenheiro(termo_busca: str, opcoes_banco: list[dict]) -> AnaliseIA:
    """
    Agente Mapeador e Revisor em Cascata.
    Obriga a OpenAI a cuspir um JSON perfeitamente compatível com o Schema Pydantic.
    """
    
    # Mascara dados não sensíveis para jogar no Prompt (A memória do Pinecone)
    contexto = json.dumps(opcoes_banco, indent=2, ensure_ascii=False)
    
    prompt_sistema = """Você é um Engenheiro de Orçamentos Sênior (Copiloto OrceIA), especialista em tabelas SINAPI.
Sua missão é auditar o "item original da planilha" e encontrar a correspondência exata entre as "opções do SINAPI" fornecidas.

REGRAS DE OURO (ANTI-ALUCINAÇÃO):
1. RACIOCÍNIO EXPLÍCITO: Utilize a variável 'raciocinio_step_by_step' para registrar sua análise. Seja extremamente conciso (máximo 2 frases curtas, máx 30 palavras) ANTES de definir o código ou rigor.
2. DISCIPLINA CONSTRUTIVA: Nunca selecione uma composição apenas porque as dimensões (ex: "20 cm", "5 mm") ou unidades batem. A natureza do serviço (ex: Terraplenagem vs Alvenaria vs Hidráulica) DEVE ser compatível.
3. REJEIÇÃO OBRIGATÓRIA: Se nenhuma opção for tecnicamente correspondente ao serviço original, você DEVE retornar `codigo_selecionado` como null. É preferível deixar o item sem código do que aprovar um falso positivo que arruinará o orçamento.
4. CRITICIDADE TÉCNICA E RIGOR: Classifique a 'categoria_rigor' como ALTO EXCLUSIVAMENTE se o item for estruturalmente crítico (fundação, estrutura, elétrica, hidráulica, impermeabilização). Para itens comuns ou provisórios, use BAIXO.
5. TOLERÂNCIA DIMENSIONAL (<=15%): Se não existir equivalente exato no SINAPI, você PODE aceitar uma composição com diferença dimensional <=15% em atributos NÃO estruturais (ex: bitola de tubo acessório, espessura de revestimento não estrutural). Neste caso: marque aceito_com_tolerancia=True. O status será automaticamente RESSALVA. Para diferença >15% ou atributo estrutural (ex: fck do concreto, secção de aço): REJEITAR.
6. PROIBIDO: Nunca aceite composição de família de serviço diferente (ex: alvenaria no lugar de estrutura metálica), independente de qualquer dimensão coincidir.
7. MAPEAMENTO PARA COMPOSIÇÕES: O objetivo final é orçar serviços completos. Mesmo que o item original da planilha pareça ser apenas um material puro (insumo, ex: 'Areia', 'Cimento'), você DEVE mapeá-lo para a COMPOSIÇÃO (serviço) que melhor represente o fornecimento e/ou aplicação daquele material na obra. Não rejeite composições apenas porque o item legado omitiu a palavra 'fornecimento' ou 'instalação'.

Sua saída deve ser estritamente o JSON definido no schema."""

    prompt_usuario = f"Item original da planilha: {termo_busca}\nOpções extraídas do RRF:\n{contexto}"

    try:
        completion = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_sistema},
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
