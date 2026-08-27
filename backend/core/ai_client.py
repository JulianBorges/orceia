# backend/core/ai_client.py
"""
Singleton do cliente OpenAI assincrono.
- timeout=30.0: Previne requests travados em falhas de rede.
- max_retries=0: Tenacity em services.py controla o retry com backoff configurado.
"""
from openai import AsyncOpenAI
from core.config import settings

openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=30.0,
    max_retries=0,
)
