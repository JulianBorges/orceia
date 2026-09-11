import asyncio
import core.redis_client as rc

async def check():
    await rc.init_redis()
    info = await rc.redis_client.info('memory')
    print('Memory used:', info['used_memory_human'])
    dbsize = await rc.redis_client.dbsize()
    print('Keys count:', dbsize)
    await rc.close_redis()

if __name__ == '__main__':
    asyncio.run(check())
