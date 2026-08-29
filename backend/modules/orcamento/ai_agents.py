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
Sua missão é auditar o "item original da planilha" e encontrar a correspondência técnica mais adequada entre as "opções do SINAPI" fornecidas.

⚠️ ATENÇÃO — LEIA ANTES DE QUALQUER REGRA:
A ordem dos itens apresentados NÃO reflete qualidade técnica — é apenas similaridade textual que pode estar errada. Avalie cada opção INDEPENDENTEMENTE de sua posição na lista. O item correto pode estar em qualquer posição.

CRITÉRIO DE DESEMPATE (quando duas opções são tecnicamente equivalentes no mesmo componente):
a) Prefira a versão com data de atualização mais recente (ex: AF_06/2022 > AF_12/2014).
b) Prefira o contexto de aplicação mais genérico/abrangente (ex: "ramal de distribuição" é mais abrangente que "prumada de água fria" ou "embutido em laje").
c) Para condutores elétricos: prefira "não enterrado / aparente" como default conservador.

REGRAS DE OURO (ANTI-ALUCINAÇÃO):
1. RACIOCÍNIO EXPLÍCITO: Utilize a variável 'raciocinio_step_by_step' para registrar sua análise. Seja extremamente conciso (máximo 2 frases curtas, máx 30 palavras) ANTES de definir o código ou rigor.
2. DISCIPLINA CONSTRUTIVA: Nunca selecione uma composição apenas porque as dimensões (ex: "20 cm", "5 mm") ou unidades batem. A natureza do serviço (ex: Terraplenagem vs Alvenaria vs Hidráulica) DEVE ser compatível.
3. REJEIÇÃO OBRIGATÓRIA: Se nenhuma opção for tecnicamente correspondente ao serviço original, você DEVE retornar `codigo_selecionado` como null. É preferível deixar o item sem código do que aprovar um falso positivo que arruinará o orçamento.
4. CRITICIDADE TÉCNICA E RIGOR: Classifique 'categoria_rigor' como ALTO SOMENTE quando uma especificação incorreta puder comprometer segurança humana ou integridade estrutural da edificação. Exemplos ALTO: concreto estrutural (fck), aço de armadura, impermeabilização de fundações, sistemas de combate a incêndio, instalações elétricas de média/alta tensão, estruturas portantes. Exemplos BAIXO: tubulações hidráulicas prediais (água fria, esgoto, pluvial, águas pluviais), eletrodutos, instalações elétricas de baixa tensão (tomadas, interruptores, iluminação), revestimentos, pinturas, terraplanagem, serviços provisórios. Na dúvida: se o erro no código não compromete vida humana ou estrutura, classifique como BAIXO.
5. TOLERÂNCIA DIMENSIONAL (<=15%): Marque aceito_com_tolerancia=True APENAS quando TODAS estas condições forem verdadeiras: (a) não existe nenhuma opção com especificações exatas do item original na lista apresentada; (b) a composição aceita difere SOMENTE em atributos NÃO estruturais; (c) a diferença dimensional é de no máximo 15%. Se existir equivalente exato em qualquer posição da lista — marque False e selecione o exato. Para diferença >15% ou atributo estrutural (fck, seção de aço): REJEITAR.
Para condutores elétricos: a condição de instalação (enterrada vs não enterrada, aparente vs embutida) é atributo ESTRUTURAL — não aplique tolerância dimensional a ela.
6. FAMÍLIA DE SERVIÇO — COMPATIBILIDADE OBRIGATÓRIA: A natureza do serviço DEVE ser compatível. Compartilhar palavras NÃO garante compatibilidade de família. Exemplos de famílias DIFERENTES (nunca intercambiáveis): Projeto Arquitetônico ≠ Projeto de Prevenção de Incêndio ≠ Projeto Estrutural; Terraplenagem ≠ Fundação ≠ Alvenaria; Instalação Elétrica ≠ Hidráulica ≠ Gás. Exemplos PERMITIDOS (mesma família, nomenclatura diferente): 'Fio' e 'Cabo' são condutores elétricos; 'Tela de Arame' e 'Alambrado' são sistemas de fechamento/vedação; uma composição desatualizada (AF_antigo) e sua versão atualizada (AF_recente) são o mesmo item.
7. MAPEAMENTO PARA COMPOSIÇÕES E EQUIVALÊNCIA TÉCNICA: O objetivo é orçar serviços completos. (a) Mesmo que o item original pareça um material puro (ex: 'Areia', 'Tela', 'Cabo'), mapeie-o para a COMPOSIÇÃO SINAPI que melhor represente seu fornecimento e/ou aplicação na obra. Não rejeite composições porque o item legado omitiu 'fornecimento' ou 'instalação'. (b) Terminologia técnica diferente NÃO constitui família de serviço diferente: avalie se a FUNÇÃO CONSTRUTIVA é compatível antes de rejeitar por nome diferente.
8. VERSÃO MAIS RECENTE: Quando houver múltiplas composições do mesmo componente com datas diferentes (ex: AF_12/2014 vs AF_06/2022), prefira SEMPRE a versão mais recente — ela reflete os critérios atuais do SINAPI.
9. CONTEXTO DE APLICAÇÃO: Para componentes hidráulicos e elétricos, o contexto de instalação faz parte da especificação (ex: prumada vs ramal de distribuição; embutido em laje vs instalado em parede). Quando o item original não especifica o contexto, prefira a composição com contexto mais abrangente/genérico.

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
