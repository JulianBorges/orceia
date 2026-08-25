from core.db import get_db_pool


async def search_sinapi_por_trigrama(termo: str, tipo: str = "composicoes") -> list[dict]:
    """
    Busca Lexical (Trigramas pg_trgm) no PostgreSQL — função pública e compartilhada.

    Usada por:
    - modules/orcamento/search_engine.py  (motor RRF)
    - modules/sinapi/routes.py            (autocomplete manual do usuário)

    Args:
        termo: Texto a ser buscado.
        tipo:  "composicoes" (default) ou "insumos".

    Returns:
        Lista de dicts com campos: codigo, descricao, preco, unidade, score_lexico.
    """
    tabela = "sinapi_composicoes" if tipo == "composicoes" else "sinapi_insumos"

    # word_similarity é a função do pg_trgm. Quanto mais perto de 1.0, mais parecido.
    query = f"""
        SELECT codigo, descricao, preco, unidade, word_similarity(descricao, $1) as score_lexico
        FROM {tabela}
        WHERE word_similarity(descricao, $1) > 0.1
        ORDER BY score_lexico DESC
        LIMIT 15;
    """

    pool = get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(query, termo)

    return [dict(r) for r in records]
