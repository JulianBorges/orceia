import asyncio
import re
from core.db import get_db_pool


def _limpar_termo_lexico(termo: str) -> str:
    """Remove sufixos universais SINAPI que criam overlap espúrio no pg_trgm."""
    # Remove "FORNECIMENTO E INSTALAÇÃO" e variantes
    termo = re.sub(r'(?i)\bfornecimento\s+e\s+instala[çc][aã]o\.?', '', termo)
    # Remove código de atualização AF_MM/AAAA
    termo = re.sub(r'(?i)\bAF_\d{2}/\d{4}', '', termo)
    # Limpa espaços extras
    return ' '.join(termo.split()).strip()


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
    TABELAS_VALIDAS: dict[str, str] = {
        "composicoes": "sinapi_composicoes",
        "insumos": "sinapi_insumos",
    }
    tabela = TABELAS_VALIDAS.get(tipo)
    if tabela is None:
        raise ValueError(f"Tipo de busca SINAPI invalido: '{tipo}'. Aceitos: {list(TABELAS_VALIDAS.keys())}")

    termo_pg = _limpar_termo_lexico(termo)

    # word_similarity é a função do pg_trgm. Quanto mais perto de 1.0, mais parecido.
    query = f"""
        SELECT codigo, descricao, preco, unidade, word_similarity(descricao, $1) as score_lexico
        FROM {tabela}
        WHERE word_similarity(descricao, $1) > 0.12
        ORDER BY score_lexico DESC
        LIMIT 30;
    """

    pool = get_db_pool()
    try:
        async with pool.acquire() as conn:
            records = await asyncio.wait_for(conn.fetch(query, termo_pg), timeout=3.0)
        return [dict(r) for r in records]
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[RRF] Timeout ou erro na busca léxica (PostgreSQL) para '{termo}': {e}")
        return []
