from openai import AsyncOpenAI
from core.config import settings

# Singleton: um único pool de conexões HTTP para toda a aplicação.
# Todos os módulos que precisam da OpenAI devem importar este cliente,
# evitando múltiplos pools de conexão desperdiçados.
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
