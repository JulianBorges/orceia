import asyncio
from core.db import init_db_pool, close_db_pool, get_db_pool

async def clear_db():
    await init_db_pool()
    pool = get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, titulo, tenant_id FROM planilhas")
        print(f"Encontrei {len(rows)} planilhas no banco.")
        for r in rows:
            print(f"- {r['titulo']} ({r['id']})")
            await conn.execute("DELETE FROM planilhas WHERE id = $1", r['id'])
            print(f"Deletada!")
    await close_db_pool()

if __name__ == "__main__":
    asyncio.run(clear_db())
