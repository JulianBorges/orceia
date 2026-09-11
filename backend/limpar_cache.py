import asyncio
import sys
import os

# Adiciona o diretório atual ao PYTHONPATH para conseguir importar 'core'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import core.redis_client as rc

async def limpar():
    print("Conectando ao Redis...")
    await rc.init_redis()
    try:
        # Comando FLUSHDB apaga todas as chaves do banco de dados atual (caches, streams, tokens travados)
        await rc.redis_client.flushdb(asynchronous=False)
        print("[OK] Sucesso! Banco de Dados Redis (FLUSHDB) esvaziado completamente.")
    except Exception as e:
        print(f"[ERRO] Erro ao limpar o cache: {e}")
    finally:
        await rc.close_redis()

if __name__ == "__main__":
    asyncio.run(limpar())
