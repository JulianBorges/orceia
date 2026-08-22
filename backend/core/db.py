import asyncpg
from core.config import settings

# Global pool
_pool = None

async def init_db_pool():
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.SUPABASE_DATABASE_URL,
                min_size=2,
                max_size=20,
                command_timeout=60,
                statement_cache_size=0,
            )
            print("PostgreSQL connection pool via asyncpg initialized.")
        except Exception as e:
            print(f"Failed to initialize database pool: {e}")
            raise e

async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        print("PostgreSQL connection pool closed.")

def get_db_pool():
    if _pool is None:
        raise Exception("Database pool is not initialized. Check lifespan.")
    return _pool

async def get_db_connection():
    if _pool is None:
        await init_db_pool()
    async with _pool.acquire() as connection:
        yield connection
