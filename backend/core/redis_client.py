import hashlib
import json
import redis.asyncio as redis
from core.config import settings
from core.text_utils import normalizar_chave

# Conexão global
redis_client = None

async def init_redis():
    global redis_client
    if redis_client is None:
        try:
            # O decode_responses=True garante que receberemos strings em vez de bytes
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # Testa a conexão
            await redis_client.ping()
            print("Redis connection initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize Redis: {e}")
            raise e

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.aclose()
        print("Redis connection closed.")

async def publish_sse_event(stream_key: str, event_data: dict):
    """Grava o evento no Redis Stream de uma planilha específica"""
    if redis_client is None:
        return
    # Grava no stream com limite de tamanho (aprox 10000 mensagens) para evitar estouro de memória
    await redis_client.xadd(stream_key, {"payload": json.dumps(event_data)}, maxlen=10000)

async def get_ai_cache(texto_busca: str) -> dict | None:
    """Procura se a IA já calculou esse item nos últimos 15 dias usando SHA-256."""
    if redis_client is None: 
        return None
        
    chave_hash = hashlib.sha256(normalizar_chave(texto_busca).encode()).hexdigest()
    resultado = await redis_client.get(f"cache_ia:{chave_hash}")
    return json.loads(resultado) if resultado else None

async def set_ai_cache(texto_busca: str, payload: dict):
    """Guarda o veredito da IA no Redis por 15 dias para poupar chamadas da API."""
    if redis_client is None: 
        return
        
    chave_hash = hashlib.sha256(normalizar_chave(texto_busca).encode()).hexdigest()
    # TTL de 15 dias (15 * 24 * 60 * 60 = 1296000 segundos)
    await redis_client.setex(f"cache_ia:{chave_hash}", 1296000, json.dumps(payload))

async def delete_ai_cache(texto_busca: str) -> bool:
    """
    Invalida o cache da IA para um termo especifico.
    Chamado pelo endpoint /feedback apos o engenheiro corrigir o veredito (RLHF).

    Returns:
        True se a chave existia e foi deletada, False caso contrario.
    """
    if redis_client is None:
        return False
    chave_hash = hashlib.sha256(normalizar_chave(texto_busca).encode()).hexdigest()
    deleted = await redis_client.delete(f"cache_ia:{chave_hash}")
    return deleted > 0
