import json
from core.ai_client import openai_client as client
from modules.orcamento.schemas import AnaliseIA

async def consultar_agente_engenheiro(termo_busca: str, opcoes_banco: list[dict], valor_total_linha: float = 0.0) -> AnaliseIA:
    """
    Agente Mapeador e Revisor em Cascata.
    Obriga a OpenAI a cuspir um JSON perfeitamente compatível com o Schema Pydantic.
    """
    
    # Mascara dados não sensíveis para jogar no Prompt (A memória do Pinecone)
    contexto = json.dumps(opcoes_banco, indent=2, ensure_ascii=False)
    
    prompt_sistema = """Você é um Engenheiro de Orçamentos Sênior (Copiloto OrceIA), especialista em tabelas SINAPI.
Sua missão é auditar o "item original da planilha" e encontrar a correspondência exata entre as "opções do SINAPI" fornecidas.

REGRAS DE OURO (ANTI-ALUCINAÇÃO):
1. RACIOCÍNIO EXPLÍCITO: Utilize a variável 'raciocinio_step_by_step' para registrar sua análise estrutural e comparativa ANTES de definir o código ou o rigor.
2. DISCIPLINA CONSTRUTIVA: Nunca selecione uma composição apenas porque as dimensões (ex: "20 cm", "5 mm") ou unidades batem. A natureza do serviço (ex: Terraplenagem vs Alvenaria vs Hidráulica) DEVE ser compatível.
3. REJEIÇÃO OBRIGATÓRIA: Se nenhuma opção for tecnicamente correspondente ao serviço original, você DEVE retornar `codigo_selecionado` como null. É preferível deixar o item sem código do que aprovar um falso positivo que arruinará o orçamento.
4. CURVA ABC E RIGOR: Classifique a 'categoria_rigor' como ALTO se o item for estruturalmente crítico ou tiver alto valor financeiro.

Sua saída deve ser estritamente o JSON definido no schema."""

    prompt_usuario = f"Item original da planilha: {termo_busca}\nValor Total Esperado do Item na Obra: R$ {valor_total_linha:.2f}\nOpções extraídas do RRF:\n{contexto}"

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
