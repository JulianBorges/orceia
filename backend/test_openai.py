import asyncio
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

async def test_openai():
    client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    print(f"OpenAI beta: {dir(client.beta)}")
    try:
        from pydantic import BaseModel
        class Test(BaseModel):
            nome: str
            
        res = await client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "olá"}],
            response_format=Test
        )
        print(res.choices[0].message.parsed)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test_openai())
