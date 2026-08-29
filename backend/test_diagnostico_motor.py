"""
Script de Diagnostico Detalhado do Motor OrceIA
Roda TODOS os itens do CSV PLANILHA AJUSTE MOTOR contra:
  - Preprocessor (normalizacao)
  - Busca Hibrida RRF (PostgreSQL trigramas + Pinecone embeddings)
  - LLM (Agente Engenheiro gpt-4o-mini)

Uso: cd backend && python test_diagnostico_motor.py
"""
import asyncio
import json
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from core.db import init_db_pool, close_db_pool
from modules.orcamento.search_engine import realizar_busca_hibrida
from modules.orcamento.ai_agents import consultar_agente_engenheiro
from modules.orcamento.preprocessor import normalizar_termo_busca

CASOS_TESTE = [
    {"descricao_legada": 'PROJETO "AS BUILT" ARQUITETURA', "descricao_sinapi": "N/A", "codigo_esperado": None, "expectativa": "REJEICAO"},
    {"descricao_legada": "PLACA DE OBRA-PINTADA/FIXADA ESTRUTURA DE MADEIRA", "descricao_sinapi": "FORNECIMENTO E INSTALACAO DE PLACA DE OBRA COM CHAPA GALVANIZADA E ESTRUTURA DE MADEIRA. AF_03/2022_PS", "codigo_esperado": "103689", "expectativa": "ACEITACAO"},
    {"descricao_legada": "INSTALACAO PROVISORIA UNIDADE SANITARIA - 5,0M2", "descricao_sinapi": "N/A", "codigo_esperado": None, "expectativa": "REJEICAO"},
    {"descricao_legada": "REGULARIZACAO E COMPACTACAO DE SUBLEITO ATE 20 CM DE ESPESSURA", "descricao_sinapi": "MULTIPLOS", "codigo_esperado": ["100576", "100577", "105598", "105597"], "expectativa": "ACEITACAO qualquer um dos 4 codigos"},
    {"descricao_legada": "FIO ISOLADO 6,0MM2 (8AWG)", "descricao_sinapi": "CABO DE COBRE FLEXIVEL ISOLADO, 6 MM, ANTI-CHAMA 0,6/1,0 KV, PARA CIRCUITOS TERMINAIS - FORNECIMENTO E INSTALACAO. AF_03/2023", "codigo_esperado": "91931", "expectativa": "ACEITACAO FIO CABO equivalencia"},
    {"descricao_legada": "CABO DE COBRE FLEXIVEL ISOLADO, 10 MM, ANTI-CHAMA 0,6/1,0 KV, PARA CIRCUITOS TERMINAIS - FORNECIMENTO E INSTALACAO. AF_12/2015", "descricao_sinapi": "mesmo item data AF_03/2023", "codigo_esperado": "91933", "expectativa": "ACEITACAO mesmo item data diferente"},
    {"descricao_legada": "TELA ARAME GALVANIZADO FIO 12 BWG 2,77mm DN 1 1/4 4x4 cm", "descricao_sinapi": "ALAMBRADO PARA QUADRA POLIESPORTIVA TELA ARAME GALVANIZADO FIO 12 BWG MALHA 5X5CM AF_12/2025", "codigo_esperado": "102363", "expectativa": "ACEITACAO TELA ALAMBRADO variacao"},
    {"descricao_legada": "ABRACADEIRA GALVANIZADA ELETROLITICA CUNHA 3/4", "descricao_sinapi": "N/A", "codigo_esperado": None, "expectativa": "REJEICAO"},
    {"descricao_legada": "ELETRODUTO PVC RIGIDO ROSCAVEL 3/4 19MM", "descricao_sinapi": "ELETRODUTO RIGIDO ROSCAVEL PVC DN 25 MM 3/4 CIRCUITOS TERMINAIS PAREDE FORNECIMENTO INSTALACAO AF_03/2023", "codigo_esperado": "91871", "expectativa": "ACEITACAO 3/4 = DN 25mm"},
    {"descricao_legada": "PINTURA ACRILICA SOBRE REBOCO - 2 DEMAOS", "descricao_sinapi": "PINTURA LATEX ACRILICA STANDARD APLICACAO MANUAL PAREDES DUAS DEMAOS AF_04/2023", "codigo_esperado": "104642", "expectativa": "ACEITACAO sinonimia"},
    {"descricao_legada": "CABO DE COBRE NU 35MM2 - FORNECIMENTO E INSTALACAO", "descricao_sinapi": "CORDOALHA DE COBRE NU 35 MM NAO ENTERRADA COM ISOLADOR FORNECIMENTO INSTALACAO AF_08/2023", "codigo_esperado": "96973", "expectativa": "ACEITACAO CABO CORDOALHA"},
    {"descricao_legada": "TUBO PVC RIGIDO SOLDAVEL 110MM", "descricao_sinapi": "TUBO PVC SOLDAVEL 110MM RESERVACAO PREDIAL AGUA FORNECIMENTO INSTALACAO AF_04/2024", "codigo_esperado": "94655", "expectativa": "ACEITACAO"},
    {"descricao_legada": "CAIXA SIFONADA, PVC, DN 100 X 100 X 50 MM, FORNECIDA E INSTALADA EM RAMAIS DE ENCAMINHAMENTO DE AGUA PLUVIAL. AF_12/2014", "descricao_sinapi": "mesmo item AF_06/2022", "codigo_esperado": "89482", "expectativa": "ACEITACAO data diferente"},
    {"descricao_legada": "JOELHO 45 PVC RIGIDO SOLDAVEL 50MM", "descricao_sinapi": "JOELHO 45 GRAUS PVC SOLDAVEL DN 50MM RAMAL DISTRIBUICAO AGUA FORNECIMENTO INSTALACAO AF_06/2022", "codigo_esperado": "103985", "expectativa": "ACEITACAO"},
    {"descricao_legada": "JOELHO 90 PVC RIGIDO SOLDAVEL 50MM", "descricao_sinapi": "JOELHO 90 GRAUS PVC SOLDAVEL DN 50MM RAMAL DISTRIBUICAO AGUA FORNECIMENTO INSTALACAO AF_06/2022", "codigo_esperado": "103984", "expectativa": "ACEITACAO"},
    {"descricao_legada": "JUNCAO SIMPLES PVC 75x50 mm ESGOTO", "descricao_sinapi": "JUNCAO REDUCAO INVERTIDA PVC SERIE NORMAL ESGOTO PREDIAL DN 75 X 50 MM JUNTA ELASTICA RAMAL DESCARGA AF_08/2022", "codigo_esperado": "104343", "expectativa": "ACEITACAO JUNCAO SIMPLES REDUCAO INVERTIDA"},
    {"descricao_legada": "TE, PVC, SOLDAVEL, DN 50 MM INSTALADO EM RESERVACAO DE AGUA DE EDIFICACAO QUE POSSUA RESERVATORIO DE FIBRA/FIBROCIMENTO FORNECIMENTO E INSTALACAO. AF_06/2016", "descricao_sinapi": "TE PVC SOLDAVEL DN 50 MM RESERVACAO PREDIAL AGUA FORNECIMENTO INSTALACAO AF_04/2024", "codigo_esperado": "94694", "expectativa": "ACEITACAO data diferente"},
    {"descricao_legada": "TE DE REDUCAO, PVC, SOLDAVEL, DN 50 MM X 40 MM, INSTALADO EM RESERVACAO DE AGUA DE EDIFICACAO QUE POSSUA RESERVATORIO DE FIBRA/FIBROCIMENTO FORNECIMENTO E INSTALACAO. AF_06/2016", "descricao_sinapi": "TE DE REDUCAO PVC SOLDAVEL DN 50 MM X 40 MM RESERVACAO PREDIAL AGUA FORNECIMENTO INSTALACAO AF_04/2024", "codigo_esperado": "94695", "expectativa": "ACEITACAO data diferente"},
]

TENANT_ID = "test_diagnostico"
ID_PLANILHA = "planilha_ajuste_motor_2026"


async def rodar_caso(caso, idx):
    print(f"\n{'='*65}")
    print(f"[{idx+1:02d}/{len(CASOS_TESTE)}] {caso['descricao_legada'][:70]}")
    print(f"      Esperado: {caso['codigo_esperado']} | {caso['expectativa']}")

    resultado = {
        "idx": idx + 1,
        "descricao_legada": caso["descricao_legada"],
        "descricao_sinapi_esperada": caso["descricao_sinapi"],
        "codigo_esperado": caso["codigo_esperado"],
        "expectativa": caso["expectativa"],
        "preprocessor": {},
        "rrf_results": [],
        "esperado_no_rrf": None,
        "codigos_esperados_encontrados_no_rrf": [],
        "llm": {},
        "acertou": False,
        "veredicto": "",
        "erro": None,
    }

    try:
        normalizado = normalizar_termo_busca(caso["descricao_legada"])
        resultado["preprocessor"] = {
            "termo_limpo": normalizado.termo_limpo,
            "caracteristicas_extras": normalizado.caracteristicas_extras,
        }
        print(f"      [Preprocessor] limpo='{normalizado.termo_limpo}'")
        print(f"                     extras='{normalizado.caracteristicas_extras}'")

        opcoes_rrf, caracteristicas = await realizar_busca_hibrida(caso["descricao_legada"], ID_PLANILHA, TENANT_ID)
        codigos_rrf = [op.get("codigo") for op in opcoes_rrf]
        resultado["rrf_results"] = [
            {"rank": i+1, "codigo": op.get("codigo"), "descricao": op.get("descricao"), "unidade": op.get("unidade"), "preco": op.get("preco"), "score_lexico": op.get("score_lexico"), "score_semantico": op.get("score_semantico")}
            for i, op in enumerate(opcoes_rrf)
        ]

        esperado = caso["codigo_esperado"]
        if isinstance(esperado, list):
            encontrados = [c for c in esperado if c in codigos_rrf]
            resultado["esperado_no_rrf"] = len(encontrados) > 0
            resultado["codigos_esperados_encontrados_no_rrf"] = encontrados
        elif esperado is None:
            resultado["esperado_no_rrf"] = None
            resultado["codigos_esperados_encontrados_no_rrf"] = []
        else:
            resultado["esperado_no_rrf"] = str(esperado) in [str(c) for c in codigos_rrf]
            resultado["codigos_esperados_encontrados_no_rrf"] = [esperado] if resultado["esperado_no_rrf"] else []

        print(f"      [RRF] {len(opcoes_rrf)} itens: {codigos_rrf}")
        print(f"      [RRF] Esperado no top-10: {resultado['esperado_no_rrf']}")

        termo_ctx = caso["descricao_legada"]
        if caracteristicas:
            termo_ctx = f"{caso['descricao_legada']} [Specs extraidas: {caracteristicas}]"

        analise = await consultar_agente_engenheiro(termo_ctx, opcoes_rrf)
        resultado["llm"] = {
            "codigo_selecionado": analise.codigo_selecionado,
            "categoria_rigor": analise.categoria_rigor,
            "aceito_com_tolerancia": analise.aceito_com_tolerancia,
            "raciocinio": analise.raciocinio_step_by_step,
            "parecer": analise.parecer_tecnico,
        }

        sel = analise.codigo_selecionado
        if isinstance(esperado, list):
            acertou = sel in esperado
        elif esperado is None:
            acertou = sel is None
        else:
            acertou = str(sel) == str(esperado) if sel else False

        resultado["acertou"] = acertou
        resultado["veredicto"] = "OK_CORRETO" if acertou else f"ERRADO selecionou={sel} esperado={esperado}"
        print(f"      [LLM] Selecionado={sel} | Rigor={analise.categoria_rigor}")
        print(f"      [LLM] Raciocinio: {analise.raciocinio_step_by_step[:120]}")
        print(f"      VEREDITO: {resultado['veredicto']}")

    except Exception as e:
        import traceback
        resultado["erro"] = str(e)
        resultado["traceback"] = traceback.format_exc()
        resultado["acertou"] = False
        resultado["veredicto"] = f"EXCECAO: {e}"
        print(f"      ERRO: {e}")

    return resultado


async def main():
    print("=" * 65)
    print("  DIAGNOSTICO COMPLETO DO MOTOR OrceIA v3")
    print(f"  Total de casos: {len(CASOS_TESTE)}")
    print("=" * 65)

    await init_db_pool()
    resultados = []
    for idx, caso in enumerate(CASOS_TESTE):
        r = await rodar_caso(caso, idx)
        resultados.append(r)
        await asyncio.sleep(0.8)

    await close_db_pool()

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados_diagnostico_motor.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    total = len(resultados)
    acertos = sum(1 for r in resultados if r.get("acertou") is True)
    falhos = sum(1 for r in resultados if r.get("acertou") is False and not r.get("erro"))
    excecoes = sum(1 for r in resultados if r.get("erro"))
    rrf_miss = sum(1 for r in resultados if r.get("esperado_no_rrf") is False)

    print("\n" + "=" * 65)
    print("  RESUMO EXECUTIVO")
    print("=" * 65)
    print(f"  Total              : {total}")
    print(f"  Acertos LLM        : {acertos} ({acertos/total*100:.0f}%)")
    print(f"  Erros LLM          : {falhos}")
    print(f"  Excecoes           : {excecoes}")
    print(f"  Falha no RRF       : {rrf_miss}")
    print(f"\n  Saida JSON: {out_path}")

    for r in resultados:
        if not r.get("acertou"):
            print(f"  PROBLEMA [{r['idx']:02d}] {r['descricao_legada'][:60]}")
            print(f"    RRF_miss={r.get('esperado_no_rrf') is False} | {r.get('veredicto')}")


if __name__ == "__main__":
    asyncio.run(main())