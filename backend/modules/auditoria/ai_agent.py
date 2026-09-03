# backend/modules/auditoria/ai_agent.py
"""
Agente Auditor — Modo Auditoria (PDF chega depois do orçamento).

Recebe:
  - Descrição de um item do orçamento + código SINAPI
  - Trechos relevantes do memorial descritivo (já recuperados via Pinecone)

Retorna:
  - status_conformidade: CONFORME | DIVERGENTE | SEM_REFERENCIA
  - trecho_memorial: trecho exato que fundamenta a decisão
  - justificativa: explicação técnica

IMPORTANTE: raciocinio_auditoria é efêmero — vai para logs e NUNCA persiste no banco.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field
from core.ai_client import openai_client as client


class ResultadoConformidade(BaseModel):
    raciocinio_auditoria: str = Field(
        description=(
            "Raciocínio step-by-step CONCISO (máx. 30 palavras). "
            "EFÊMERO — vai apenas para logs, nunca persiste no banco."
        )
    )
    status_conformidade: Literal["CONFORME", "DIVERGENTE", "SEM_REFERENCIA"] = Field(
        description=(
            "CONFORME: o serviço é compatível com as especificações do memorial. "
            "DIVERGENTE: há contradição explícita — ex: memorial exige FCK 30 MPa, item usa FCK 25 MPa. "
            "SEM_REFERENCIA: o memorial não menciona este tipo de serviço."
        )
    )
    trecho_memorial: Optional[str] = Field(
        default=None,
        description=(
            "Cite o trecho EXATO do memorial que fundamenta sua decisão (máx. 150 chars). "
            "Retornar null apenas para SEM_REFERENCIA."
        )
    )
    justificativa: str = Field(
        description="Explicação técnica da decisão em no máximo 2 frases diretas."
    )


_PROMPT_SISTEMA = """Você é um Auditor de Contratos de Engenharia especialista em SINAPI e memoriais descritivos de obras públicas.
Sua missão: verificar se um item do orçamento está em conformidade com as especificações do memorial descritivo fornecido.

REGRAS DE OURO:
1. Compare o serviço do item (tipo, dimensão, material, método executivo) com os trechos do memorial.
2. CONFORME: a especificação é compatível. Pequenas diferenças de nomenclatura não constituem divergência.
3. DIVERGENTE: há contradição EXPLÍCITA e MENSURÁVEL — ex: dimensão errada, material proibido, método vetado.
4. SEM_REFERENCIA: o memorial não menciona este tipo de serviço e não é possível julgar conformidade.
5. Cite SEMPRE o trecho EXATO do memorial que fundamenta sua decisão (exceto SEM_REFERENCIA).
6. Raciocínio conciso — máximo 30 palavras.
7. Na dúvida razoável, prefira CONFORME a DIVERGENTE — evite falsos alarmes que paralisem a obra."""


async def auditar_item_contra_memorial(
    descricao_item: str,
    codigo_sinapi: Optional[str],
    trechos_memorial: str
) -> ResultadoConformidade:
    """
    Cruza um item do orçamento com os trechos relevantes do memorial via Structured Outputs.
    """
    contexto_usuario = (
        f"Item do Orçamento: {descricao_item}\n"
        f"Código SINAPI: {codigo_sinapi or 'Não mapeado'}\n\n"
        f"Trechos relevantes do Memorial Descritivo:\n{trechos_memorial}"
    )

    try:
        completion = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _PROMPT_SISTEMA},
                {"role": "user", "content": contexto_usuario}
            ],
            response_format=ResultadoConformidade,
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[AGENTE AUDITOR] Erro ao auditar item: {e}")
        raise e
