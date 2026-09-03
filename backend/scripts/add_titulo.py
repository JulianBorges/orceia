import asyncio
import os
import sys

# Adiciona o diretório backend ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db import init_db_pool, get_db_pool, close_db_pool

async def main():
    await init_db_pool()
    pool = get_db_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("ALTER TABLE planilhas ADD COLUMN IF NOT EXISTS titulo VARCHAR(255);")
            print("Coluna 'titulo' adicionada com sucesso ou já existia.")
            
            # Aproveitando para adicionar created_at e updated_at
            await conn.execute("ALTER TABLE planilhas ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
            await conn.execute("ALTER TABLE planilhas ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
            print("Colunas 'created_at' e 'updated_at' garantidas.")
        except Exception as e:
            print(f"Erro ao alterar tabela: {e}")
    await close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
