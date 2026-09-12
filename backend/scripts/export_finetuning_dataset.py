import asyncio
import json
import os
import sys
import copy

# Ajusta o PYTHONPATH para importar módulos do backend
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.db import init_db_pool, close_db_pool, get_db_pool
from modules.orcamento.search_engine import realizar_busca_hibrida
from modules.orcamento.preprocessor import injetar_tolerancia_dimensional
from core.ai_client import openai_client
from modules.orcamento.schemas import AnaliseIA
from modules.orcamento.ai_agents import PROMPT_SISTEMA_ORCAMENTO

async def generate_teacher_analysis(termo_original: str, opcoes_banco: list[dict], codigo_correto: str | None, descricao_correta: str | None) -> AnaliseIA:
    """
    Usa o GPT-4o (Teacher Model) para construir a justificativa perfeita (Chain of Thought)
    sabendo de antemão qual é a resposta certa.
    """
    
    contexto = json.dumps(opcoes_banco, indent=2, ensure_ascii=False)
    
    decisao_str = f"O humano REJEITOU (não encontrou equivalência no SINAPI). Código esperado: NULL." if not codigo_correto else f"O humano escolheu a opção com CÓDIGO {codigo_correto} ({descricao_correta})."

    teacher_prompt = f"""Você é um Teacher Model de Inteligência Artificial.
Sua missão é gerar os dados sintéticos de Chain of Thought (Raciocínio) para treinar um LLM menor.
Você receberá o termo original da planilha, as opções da busca e a DECISÃO FINAL TOMADA PELO HUMANO.

Sua tarefa: preencha o JSON de saída (AnaliseIA) gerando um `raciocinio_step_by_step` brilhante, rigoroso e pedagógico que justifique EXATAMENTE a decisão do humano. A justificativa deve parecer natural, como se o LLM estivesse deduzindo essa decisão.
Garanta que `codigo_selecionado` seja EXATAMENTE o código que o humano escolheu (ou null se o humano rejeitou).
Preencha a `categoria_rigor` e `aceito_com_tolerancia` de forma coerente com o caso.
O `parecer_tecnico` deve ser sucinto e técnico.

Termo original: {termo_original}
Opções extraídas:
{contexto}

GABARITO HUMANO A SER SEGUIDO E JUSTIFICADO:
{decisao_str}
"""
    try:
        completion = await openai_client.beta.chat.completions.parse(
            model="gpt-4o", # Modelo grande gerando dados de treino para o mini
            messages=[
                {"role": "user", "content": teacher_prompt}
            ],
            response_format=AnaliseIA,
            temperature=0.2
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        print(f"Erro no Teacher Model: {e}")
        raise e

async def main():
    await init_db_pool()
    pool = get_db_pool()
    
    print("Buscando dados de treinamento exclusivamente da Memória Organizacional (Gabarito Humano)...")
    
    async with pool.acquire() as conn:
        registros_rlhf = await conn.fetch("SELECT tenant_id, descricao_legada, codigo, descricao, parecer_tecnico FROM memoria_organizacional")
    
    if not registros_rlhf:
        print("Nenhum dado encontrado na Memória Organizacional. Treine a IA na interface primeiro.")
        await close_db_pool()
        return

    dataset = []
    
    for row in registros_rlhf:
        tenant_id = row['tenant_id']
        descricao_legada = row['descricao_legada']
        codigo_esperado = row['codigo']
        descricao_sinapi = row['descricao']
        
        print(f"Processando: {descricao_legada[:50]}...")
        
        try:
            # 1. Recriar a Busca Híbrida Exatamente como em Produção
            opcoes_banco, caracteristicas = await realizar_busca_hibrida(descricao_legada, "finetuning", tenant_id)
            
            # 2. Replicar a Lógica do Motor Principal (Top 10 + Tolerância)
            top_10 = opcoes_banco[:10]
            opcoes_para_prompt = copy.deepcopy(top_10)
            injetar_tolerancia_dimensional(descricao_legada, opcoes_para_prompt)
            
            # Validação: Se não é rejeição e o item não está no top 10, o motor falhou na busca,
            # então o LLM não teria como acertar de qualquer jeito. Descartamos.
            if codigo_esperado:
                codigos_top_10 = [str(op.get("codigo")) for op in opcoes_para_prompt]
                if str(codigo_esperado) not in codigos_top_10:
                    print(f"[DESCARTADO] {descricao_legada}: Código {codigo_esperado} não estava no Top 10 RRF.")
                    continue
                
            # 3. Gerar Raciocínio (Teacher Model)
            teacher_analysis = await generate_teacher_analysis(descricao_legada, opcoes_para_prompt, codigo_esperado, descricao_sinapi)
            
            # 4. Empacotar JSONL Exatamente no Formato de Produção
            contexto_str = json.dumps(opcoes_para_prompt, indent=2, ensure_ascii=False)
            termo_ctx = descricao_legada
            if caracteristicas:
                termo_ctx = f"{descricao_legada} [Specs extraidas: {caracteristicas}]"
                
            prompt_usuario = f"Item original da planilha: {termo_ctx}\\nOpções extraídas do RRF:\\n{contexto_str}"
            
            # Forçar serialização do Pydantic para Dict
            resposta_json = json.loads(teacher_analysis.model_dump_json(exclude_none=False))
            
            dataset.append({
                "messages": [
                    {"role": "system", "content": PROMPT_SISTEMA_ORCAMENTO},
                    {"role": "user", "content": prompt_usuario},
                    {"role": "assistant", "content": json.dumps(resposta_json, ensure_ascii=False)}
                ]
            })
            print(f"[OK] Treino sintético gerado com GPT-4o.")
            
        except Exception as e:
            print(f"Erro ao processar '{descricao_legada}': {e}")
            
        await asyncio.sleep(0.5) 
        
    await close_db_pool()
    
    if len(dataset) == 0:
        print("\\n[ERRO] Nenhum item válido encontrado após filtragem.")
        return
        
    out_path = os.path.join(os.path.dirname(__file__), "dataset_orceia_v1.jsonl")
    with open(out_path, 'w', encoding='utf-8') as f:
        for ds_item in dataset:
            f.write(json.dumps(ds_item, ensure_ascii=False) + '\\n')
            
    print(f"\\n[SUCESSO] Dataset finalizado com {len(dataset)} exemplos de Ouro em: {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
