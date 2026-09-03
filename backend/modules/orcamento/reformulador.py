from pydantic import BaseModel, Field
from core.ai_client import openai_client

class SinonimosTecnicos(BaseModel):
    sinonimos: list[str] = Field(
        description="Lista de até 3 nomes técnicos alternativos para o equipamento, ferramenta ou serviço. Use terminologia formal de engenharia (SINAPI)."
    )

async def gerar_variacoes_tecnicas(termo: str) -> list[str]:
    """
    Recebe um termo de baixa confiança e usa o modelo rápido (gpt-4o-mini)
    para gerar variações técnicas que podem ter match melhor no banco.
    """
    try:
        response = await openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um engenheiro civil especialista no jargão do SINAPI. "
                        "O usuário pesquisou por um termo de canteiro de obras ou muito genérico. "
                        "Retorne até 3 variações extremamente técnicas ou classes genéricas (ex: 'Talha tirfor' -> 'Guincho de alavanca', 'Equipamento de içamento')."
                    )
                },
                {"role": "user", "content": f"Termo buscado: {termo}"}
            ],
            response_format=SinonimosTecnicos,
            temperature=0.3
        )
        return response.choices[0].message.parsed.sinonimos
    except Exception as e:
        print(f"[REFORMULADOR] Erro ao gerar sinônimos: {e}")
        return []
