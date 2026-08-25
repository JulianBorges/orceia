"""
Testes do Motor RRF (Reciprocal Rank Fusion) — sem dependências externas.
Valida a lógica de fusão usando listas mockadas (sem chamar Pinecone ou Supabase).
"""
import pytest
import sys
import os

# Isola o módulo do motor RRF sem precisar de conexões externas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def aplicar_rrf(pg_results: list[dict], pc_results: list[dict], k: int = 60) -> list[dict]:
    """
    Lógica RRF extraída diretamente do search_engine.py para teste unitário isolado.
    Qualquer alteração no algoritmo real deve ser refletida aqui.
    """
    scores_rrf = {}
    master_dict = {}

    for rank, item in enumerate(pg_results):
        cod = item["codigo"]
        scores_rrf[cod] = scores_rrf.get(cod, 0) + (1.0 / (k + rank + 1))
        master_dict[cod] = item

    for rank, item in enumerate(pc_results):
        cod = item["codigo"]
        if cod in scores_rrf:
            scores_rrf[cod] += (1.0 / (k + rank + 1))
            scores_rrf[cod] *= 1.20  # Boost de consenso: +20%
        else:
            scores_rrf[cod] = (1.0 / (k + rank + 1))
            master_dict[cod] = item

    ranking = sorted(scores_rrf.items(), key=lambda x: x[1], reverse=True)

    top_items = []
    for cod, score in ranking[:10]:
        item = master_dict[cod].copy()
        item["preco"] = float(item["preco"]) if item.get("preco") is not None else 0.0
        item["score_rrf_interno"] = round(score * 100, 2)
        item.setdefault("score_lexico", None)
        item.setdefault("score_semantico", None)
        top_items.append(item)

    return top_items


# -------------------------------------------------------------------
# Fixtures reutilizáveis
# -------------------------------------------------------------------

def make_item(codigo: str, descricao: str = "desc", preco: float = 100.0) -> dict:
    return {"codigo": codigo, "descricao": descricao, "preco": preco, "unidade": "M2"}


# -------------------------------------------------------------------
# Testes
# -------------------------------------------------------------------

class TestRRFOrdenacao:
    def test_item_no_topo_de_ambas_as_listas_vence(self):
        """Item no rank #1 em ambas as fontes deve ser o vencedor absoluto."""
        pg = [make_item("A"), make_item("B"), make_item("C")]
        pc = [make_item("A"), make_item("D"), make_item("E")]

        result = aplicar_rrf(pg, pc)

        assert result[0]["codigo"] == "A", "Item consensual deve liderar o ranking"

    def test_ordenacao_decrescente_por_score(self):
        """O resultado deve estar ordenado por score_rrf_interno de forma decrescente."""
        pg = [make_item("A"), make_item("B"), make_item("C")]
        pc = [make_item("D"), make_item("E"), make_item("F")]

        result = aplicar_rrf(pg, pc)

        scores = [r["score_rrf_interno"] for r in result]
        assert scores == sorted(scores, reverse=True), "Scores devem estar em ordem decrescente"

    def test_top_10_maximo(self):
        """O resultado nunca deve retornar mais que 10 itens."""
        pg = [make_item(f"PG{i}") for i in range(15)]
        pc = [make_item(f"PC{i}") for i in range(15)]

        result = aplicar_rrf(pg, pc)

        assert len(result) <= 10, "RRF deve cortar para no máximo Top 10"

    def test_resultado_vazio_com_listas_vazias(self):
        """Listas vazias em ambas as fontes devem retornar lista vazia."""
        result = aplicar_rrf([], [])
        assert result == []


class TestRRFBoostConsenso:
    def test_boost_20_porcento_aplicado(self):
        """Item presente em ambas as listas deve ter score maior que item só em uma."""
        # "CONSENSO" aparece em pg[0] e pc[0] → boost 20%
        # "APENAS_PG" aparece só em pg[1] → sem boost
        pg = [make_item("CONSENSO"), make_item("APENAS_PG")]
        pc = [make_item("CONSENSO"), make_item("APENAS_PC")]

        result = aplicar_rrf(pg, pc)
        by_codigo = {r["codigo"]: r["score_rrf_interno"] for r in result}

        assert by_codigo["CONSENSO"] > by_codigo["APENAS_PG"], \
            "Item consensual deve ter score maior que item de fonte única"
        assert by_codigo["CONSENSO"] > by_codigo["APENAS_PC"], \
            "Item consensual deve ter score maior que item de fonte única"

    def test_item_exclusivo_pinecone_entra_no_ranking(self):
        """Item que aparece apenas no Pinecone deve entrar no ranking (sem boost)."""
        pg = [make_item("PG_ONLY")]
        pc = [make_item("PC_ONLY")]

        result = aplicar_rrf(pg, pc)
        codigos = [r["codigo"] for r in result]

        assert "PC_ONLY" in codigos, "Item exclusivo do Pinecone deve estar no resultado"


class TestRRFNormalizacaoCampos:
    def test_campos_obrigatorios_presentes(self):
        """Todos os itens do resultado devem ter os campos obrigatórios."""
        pg = [make_item("A")]
        pc = []

        result = aplicar_rrf(pg, pc)

        for item in result:
            assert "codigo" in item
            assert "score_rrf_interno" in item
            assert "score_lexico" in item
            assert "score_semantico" in item

    def test_preco_none_convertido_para_zero(self):
        """Preço None vindo do banco deve ser convertido para 0.0 (não quebrar JSON)."""
        pg = [{"codigo": "X", "descricao": "desc", "preco": None, "unidade": "UN"}]
        pc = []

        result = aplicar_rrf(pg, pc)

        assert result[0]["preco"] == 0.0, "Preco None deve ser convertido para 0.0"

    def test_preco_convertido_para_float(self):
        """Preco retornado como Decimal pelo asyncpg deve ser convertido para float."""
        from decimal import Decimal

        pg = [{"codigo": "Y", "descricao": "desc", "preco": Decimal("150.50"), "unidade": "M3"}]
        pc = []

        result = aplicar_rrf(pg, pc)

        assert isinstance(result[0]["preco"], float), "Preco deve ser float nativo"
        assert result[0]["preco"] == 150.50
