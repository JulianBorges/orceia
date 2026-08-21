import json
from openai import AsyncOpenAI
from core.config import settings
from modules.orcamento.schemas import AnaliseIA

# Inicializa o Client Oficial da OpenAI assíncrono
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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
1. DISCIPLINA CONSTRUTIVA: Nunca selecione uma composição apenas porque as dimensões (ex: "20 cm", "5 mm") ou unidades batem. A natureza do serviço (ex: Terraplenagem vs Alvenaria vs Hidráulica) DEVE ser compatível.
2. REJEIÇÃO OBRIGATÓRIA: Se nenhuma opção for tecnicamente correspondente ao serviço original, você DEVE retornar `codigo_selecionado` como null. É preferível deixar o item sem código do que aprovar um falso positivo que arruinará o orçamento.
3. CURVA ABC E RIGOR: Classifique a 'categoria_rigor' como ALTO se o item for estruturalmente crítico ou tiver alto valor financeiro.
4. JUSTIFICATIVA TÉCNICA: Documente na memória de cálculo por que as opções foram aceitas ou recusadas.

Sua saída deve ser estritamente o JSON definido no schema."""

    prompt_usuario = f"Item original da planilha: {termo_busca}\nValor Total Esperado do Item na Obra: R$ {valor_total_linha:.2f}\nOpções extraídas do RRF:\n{contexto}"

    try:
        # MAGIA DA SPRINT 3: Substituímos o prompt engessado pelo beta.chat.completions.parse!
        import openai
        print(f"DEBUG: OpenAI Version = {openai.__version__}")
        print(f"DEBUG: client = {type(client)}, beta = {type(client.beta)}, has_chat = {hasattr(client.beta, 'chat')}")
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
