import asyncio
import re
from core.db import get_db_pool


def _limpar_termo_lexico(termo: str) -> str:
    """Remove sufixos universais SINAPI que criam overlap espúrio no pg_trgm."""
    # Remove "FORNECIMENTO E INSTALAÇÃO" e variantes
    termo = re.sub(r'(?i)\bfornecimento\s+e\s+instala[çc][aã]o\.?', '', termo)
    # Remove código de atualização AF_MM/AAAA
    termo = re.sub(r'(?i)\bAF_\d{2}/\d{4}', '', termo)
    # Uniformiza multiplicadores (ex: 75x50 -> 75 X 50) para garantir parse correto no FTS
    termo = re.sub(r'(\d+)\s*[xX]\s*(?=\d)', r'\1 X ', termo)
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

    # Limpa termo base
    termo_base = _limpar_termo_lexico(termo)
    
    # Prepara tokens para Busca Textual (OR)
    raw_tokens = [w for w in termo_base.split() if w.isalnum()]
    expanded_tokens = []
    for t in raw_tokens:
        expanded_tokens.append(t)
        # Se for "110MM", injeta tambem "110" e "MM"
        match = re.match(r'^(\d+)([a-zA-Z]+)$', t)
        if match:
            expanded_tokens.extend([match.group(1), match.group(2)])
            
    termo_fts = ' | '.join(expanded_tokens)
    
    # Adiciona espaço entre números e letras APENAS para que o Trigram ache '110 MM' corretamente
    termo_limpo = re.sub(r'(\d+)([a-zA-Z]+)', r'\1 \2', termo_base)
    
    if not expanded_tokens:
        return []

    # Busca Híbrida Postgres: Trigram + TSVector BM25
    query = f"""
        SELECT codigo, descricao, preco, unidade, 
               (
                 ts_rank(to_tsvector('simple', descricao), to_tsquery('simple', $2)) * 2.0
                 + word_similarity(descricao, $1)
               ) as score_lexico
        FROM {tabela}
        WHERE word_similarity(descricao, $1) > 0.15
           OR to_tsvector('simple', descricao) @@ to_tsquery('simple', $2)
        ORDER BY score_lexico DESC
        LIMIT 50;
    """

    pool = get_db_pool()
    try:
        async with pool.acquire() as conn:
            records = await asyncio.wait_for(conn.fetch(query, termo_limpo, termo_fts), timeout=3.0)
        return [dict(r) for r in records]
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[RRF] Timeout ou erro na busca lexica (PostgreSQL) para '{termo}': {e}")
        return []
