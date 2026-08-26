# OrceIA V3 — Regras do Backend (FastAPI + asyncpg + OpenAI)

> Lido automaticamente quando a IA modifica arquivos em `backend/`.
> Para regras globais: `GEMINI.md`. Para arquitetura: `01_core_architecture.md`.

---

## 1. Concorrência e Rate Limiting

Toda chamada à OpenAI deve estar protegida pelo semáforo, e o processo deve rodar com `--workers 1`.
```python
# ✅ CORRETO: Semáforo único e compartilhado — definido em services.py
MAX_CONCURRENT_TASKS = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

# ❌ PROIBIDO: criar semáforos independentes por feature (dobraria o limite OpenAI)
```
- `asyncio.gather(*tasks, return_exceptions=True)` — **OBRIGATÓRIO** (nunca sem return_exceptions).
- Lotes massivos: Processados de **50 em 50 linhas** — nunca a planilha inteira. 
- Usar `asyncio.create_task()` e publicar via `XADD` (Redis) conforme chegam. Nunca aguardar o fim do lote.

---

## 2. Cliente OpenAI — Singleton e Retry

```python
# ✅ CORRETO: importar o singleton
from core.ai_client import openai_client
```
Sempre usar **Structured Outputs**:
```python
# ✅ CORRETO (Pydantic estrito)
completion = await openai_client.beta.chat.completions.parse(..., response_format=AnaliseIA)
# ❌ PROIBIDO: parse de markdown ou regex
```
**Retry com Tenacity (Obrigatório)**:
- NUNCA usar `time.sleep()`.
- NUNCA derrubar a requisição por erro 429 sem retentar.
```python
from tenacity import retry, wait_exponential_jitter, stop_after_attempt
@retry(stop=stop_after_attempt(4), wait=wait_exponential_jitter(initial=1, max=30))
async def chamar_openai(): ...
```

---

## 3. Chain of Thought (CoT) — Regra de Isolamento

```python
analise: AnaliseIA = completion.choices[0].message.parsed
raciocinio = analise.raciocinio_step_by_step  # Extraído aqui (log efêmero)

# ❌ PROIBIDO: persistir o CoT no Supabase (Bug #9 - Storage Bloat)
# ❌ PROIBIDO: enviar o CoT no payload SSE
```

---

## 4. Banco de Dados — Supabase / asyncpg

- **Porta do Supabase**: Sempre `6543` (Transaction Pooler).
- **statement_cache_size=0**: Inviolável. Compatibilidade necessária com PgBouncer.
- **IDs**: Sempre `VARCHAR(255)`. Nunca `UUID` (Bug #11).
- **Bulk Insert**: Upsert em lote via `executemany` (Custo O(1)). Nunca loop de `execute`.
- **Multi-Tenant**: Cláusula `WHERE tenant_id = $x` em TODA query de dados do usuário.

---

## 5. Redis Streams — SSE e Cache

**Namespace Multi-Tenant**:
- ✅ `stream:{tenant_id}:planilha:{id_planilha}`
- ❌ `stream:planilha:{id_planilha}` (Bug #7 - Cross-tenant leak)

**Cache Anti-Zumbi (Validação)**:
Antes de servir um hit do Redis (TTL 15 dias, baseado no hash SHA256 do termo), **valide** se o `codigo_selecionado` retornado ainda faz parte do Top 10 atual do RRF. Se não existir, ignore o cache. Se alterar o schema de status (ex: "ACEITO"), exija um **Flush total do Redis**.

---

## 6. Deploy — Cloud Run (Configurações Críticas)

- **CPU Allocation**: Always Allocated (Baseada em instâncias). Nunca "baseada em solicitações", pois o Cloud Run congela o container e mata a conexão SSE do usuário.
- **Build Context**: `/backend/` (onde o Dockerfile está).
- **BACKEND_API_URL**: URL base pura (sem `/api`, sem barra final).

---

## 7. Novos Módulos — Checklist DDD

- `orcamento/` é o núcleo (não altere sem aprovação explícita).
- `sinapi/` e outras features nunca importam de `orcamento/` diretamente.
- Use `Depends(verify_proxy_secret)` e `Depends(get_current_tenant)` nas rotas.
