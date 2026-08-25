# OrceIA V3 — Regras do Backend (FastAPI + asyncpg + OpenAI)

> Lido automaticamente quando a IA modifica arquivos em `backend/`.
> Para regras globais: `GEMINI.md`. Para arquitetura: `01_core_architecture.md`.

---

## 1. Concorrência e Rate Limiting

```python
# ✅ CORRETO: Semáforo único e compartilhado — definido em services.py
# ATENÇÃO: Este semáforo é por-processo (Python in-memory).
# O servidor DEVE rodar com --workers 1 (uvicorn).
# Para escalar: adicionar réplicas do container, NÃO adicionar workers.
MAX_CONCURRENT_TASKS = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

# ❌ PROIBIDO: criar semáforos independentes por feature (dobraria o limite)
semaphore_curva_abc = asyncio.Semaphore(10)  # ERRADO — Sprint 4.2 deve reusar o semáforo acima
```

```python
# ✅ OBRIGATÓRIO: return_exceptions=True em todo asyncio.gather()
results = await asyncio.gather(*tasks, return_exceptions=True)

# ❌ PROIBIDO: gather sem proteção interrompe o SSE do usuário se a OpenAI cair
results = await asyncio.gather(*tasks)
```

---

## 2. Cliente OpenAI — Singleton

```python
# ✅ CORRETO: importar o singleton de core/ai_client.py
from core.ai_client import openai_client

# ❌ PROIBIDO: criar nova instância em cada módulo (gera N pools de conexão HTTP)
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
```

**Sempre usar Structured Outputs — NUNCA parse de Markdown ou Regex:**
```python
# ✅ CORRETO
completion = await openai_client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    response_format=AnaliseIA,  # Schema Pydantic fechado
    ...
)

# ❌ PROIBIDO — BUG #1 e #2
import re
result = re.findall(r'codigo: (\w+)', completion.choices[0].message.content)
```

---

## 3. Chain of Thought (CoT) — Onde Vai e Onde Não Vai

```python
# ✅ CORRETO: extrair o raciocínio ANTES de montar o DTO de resposta
analise: AnaliseIA = completion.choices[0].message.parsed
raciocinio = analise.raciocinio_step_by_step  # Extraído aqui
print(f"[CoT] {raciocinio}")  # Apenas em logs efêmeros

# Montar o DTO SEM o raciocínio
dto = {
    "codigo": analise.codigo_sinapi,
    "descricao": analise.descricao_oficial,
    "ai_status": analise.status,
    # raciocinio_step_by_step NÃO vai aqui
}

# ❌ PROIBIDO: persistir o CoT no Supabase — BUG #9
await conn.execute("INSERT INTO planilhas_linhas (..., raciocinio) VALUES (..., $x)", raciocinio)

# ❌ PROIBIDO: enviar o CoT no payload SSE
await publish_sse_event({"raciocinio": raciocinio, ...})
```

---

## 4. asyncpg — Configuração Obrigatória

```python
# ✅ CORRETO: statement_cache_size=0 obrigatório para compatibilidade com PgBouncer/Supabase
pool = await asyncpg.create_pool(
    dsn=settings.SUPABASE_DATABASE_URL,
    min_size=2,
    max_size=10,
    statement_cache_size=0,  # ← NUNCA REMOVA
)

# ✅ CORRETO: Upsert em lote (custo O(1) de viagens ao banco)
await conn.executemany(query_upsert, list_of_tuples)

# ❌ PROIBIDO: loop com execute individual (custo O(N))
for linha in linhas:
    await conn.execute(query_upsert, linha.campo1, linha.campo2, ...)
```

---

## 5. Segurança Multi-Tenant nas Queries

```python
# ✅ CORRETO: cláusula WHERE tenant_id em TODA query de dados do usuário
await conn.fetch("SELECT * FROM planilhas_linhas WHERE id_planilha = $1 AND tenant_id = $2", id, tenant_id)

# ❌ PROIBIDO: query sem filtro de tenant (permite cross-tenant data leak)
await conn.fetch("SELECT * FROM planilhas_linhas WHERE id_planilha = $1", id)

# ✅ CORRETO: DELETE com proteção tripla (id + planilha + tenant)
await conn.execute(
    "DELETE FROM planilhas_linhas WHERE id = ANY($1::varchar[]) AND id_planilha = $2 AND tenant_id = $3",
    ids, id_planilha, tenant_id
)
```

---

## 6. Redis — Estrutura de Chaves

```python
# ✅ CORRETO: namespace por tenant em todas as chaves de dados do usuário
stream_key = f"stream:{tenant_id}:planilha:{id_planilha}"

# ✅ CORRETO: cache de IA é global (SINAPI é o mesmo para todos os tenants)
cache_key = f"cache:ai:{hashlib.sha256(termo.encode()).hexdigest()}"

# ❌ PROIBIDO: chave pública sem tenant — BUG #7
stream_key = f"stream:planilha:{id_planilha}"
```

---

## 7. Imports e Organização

```python
# ✅ CORRETO: imports no topo do arquivo (PEP 8)
import asyncio
import hashlib
from core.db import get_db_pool
from core.ai_client import openai_client

# ❌ PROIBIDO: lazy imports dentro de funções (dificulta análise estática)
async def minha_funcao():
    from core.db import get_db_pool  # ← Mover para o topo
```

---

## 8. Retry com Tenacity

```python
# ✅ CORRETO: retry com backoff exponencial para chamadas à OpenAI
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception)
)
async def chamar_openai():
    ...
```

---

## 9. Novos Módulos — Checklist DDD

Ao criar um novo módulo em `backend/modules/`:
1. Criar pasta própria com `__init__.py`
2. Criar `routes.py`, `schemas.py`, `services.py` isolados
3. Registrar o router em `main.py`
4. Compartilhar funções via `modules/shared/` — nunca importar de outro módulo de negócio
5. Usar o singleton `core/ai_client.py` se precisar de OpenAI
6. Aplicar `Depends(verify_proxy_secret)` e `Depends(get_current_tenant)` em todas as rotas autenticadas
