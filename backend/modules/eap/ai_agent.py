from typing import List, Optional
from pydantic import BaseModel, Field
from core.ai_client import openai_client as client
import uuid

# Re-utilizamos os schemas para a saída da IA
class MacroItemProposto(BaseModel):
    descricao: str = Field(description="Título da etapa em CAIXA ALTA (ex: 'SERVIÇOS PRELIMINARES', 'ALVENARIA').")
    indice_primeiro_item_filho: int = Field(description="O ÍNDICE (número) do PRIMEIRO item original da planilha que marca o início desta etapa.")

class IAEstruturaEAP(BaseModel):
    macro_itens: List[MacroItemProposto] = Field(description="Lista de etapas lógicas da obra e onde elas começam.")

async def estruturar_eap_com_ia(linhas_originais: List[dict]) -> List[dict]:
    try:
        # Preparar a entrada para o prompt limitando para não estourar tokens se for gigantesco
        # Enviamos os índices (inteiros) e as descrições na ordem, economizando milhares de tokens que os UUIDs usariam
        texto_linhas = ""
        for i, linha in enumerate(linhas_originais):
            texto_linhas += f"[{i}] {linha['descricao']}\n"

        system_prompt = """
Você é um Engenheiro de Custos especialista em orçamentos de obras públicas.
O usuário enviou uma lista de serviços ("lista plana") sem nenhuma estrutura analítica de projeto (EAP) ou títulos de etapas.

Sua tarefa é agrupar os itens logicamente em Etapas (Macro Itens) típicas de uma obra civil.
Em vez de reescrever a lista inteira, você deve apenas me dizer QUAIS SÃO as etapas e ONDE elas começam.

Regras:
1. Analise a ordem dos serviços fornecida. A ordem não pode ser alterada.
2. Identifique os pontos de quebra natural de etapas (ex: quando terminam as escavações e começam as fundações).
3. Para cada nova etapa identificada, crie um `MacroItemProposto`.
4. `descricao`: O nome da etapa em CAIXA ALTA.
5. `indice_primeiro_item_filho`: Copie EXATAMENTE o ÍNDICE (o número entre colchetes) do primeiro item que pertence a esta nova etapa.
6. A primeira etapa DEVE obrigatoriamente começar no índice 0.
"""

        response = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Identifique as etapas e onde começam para a seguinte lista:\n{texto_linhas}"}
            ],
            response_format=IAEstruturaEAP,
            temperature=0.1
        )
        estrutura = response.choices[0].message.parsed
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erro crasso na OpenAI (Agente EAP): {e}")
        raise e
    
    # Reconstruir a lista intercalando os Macro Itens gerados
    # Mapear qual índice recebe qual macro item antes dele
    mapa_insercoes = {}
    for macro in estrutura.macro_itens:
        if macro.indice_primeiro_item_filho not in mapa_insercoes:
            mapa_insercoes[macro.indice_primeiro_item_filho] = macro.descricao

    resultado = []
    contador_macro = 0
    contador_item = 1
    
    for i, linha in enumerate(linhas_originais):
        
        # Se este item for o início de uma nova etapa, insere o Macro Item primeiro
        if i in mapa_insercoes:
            contador_macro += 1
            contador_item = 1
            resultado.append({
                "id": str(uuid.uuid4()),
                "item": f"{contador_macro}.0",
                "descricao": mapa_insercoes[i],
                "is_macro_item": True
            })
        
        # Se a IA não gerou Macro Item para o primeiro item, a gente força um genérico
        if contador_macro == 0:
            contador_macro = 1
            resultado.append({
                "id": str(uuid.uuid4()),
                "item": "1.0",
                "descricao": "SERVIÇOS GERAIS",
                "is_macro_item": True
            })
            
        # Insere o item original
        resultado.append({
            "id": linha["id"],
            "item": f"{contador_macro}.{contador_item}",
            "descricao": linha["descricao"],
            "is_macro_item": False
        })
        contador_item += 1
                
    return resultado
