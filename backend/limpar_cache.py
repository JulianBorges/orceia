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
        # Busca todas as chaves do cache da IA
        keys = await rc.redis_client.keys("cache_ia:*")
        if keys:
            await rc.redis_client.delete(*keys)
            print(f"[OK] Sucesso! {len(keys)} registros de cache da IA foram removidos.")
        else:
            print("[OK] O cache ja esta limpo. Nenhuma chave encontrada.")
    except Exception as e:
        print(f"[ERRO] Erro ao limpar o cache: {e}")
    finally:
        await rc.close_redis()

if __name__ == "__main__":
    asyncio.run(limpar())
