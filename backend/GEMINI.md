# OrceIA V3 — Regras de Backend (FastAPI / asyncio / asyncpg)

> Regras específicas do backend. Lidas automaticamente ao editar qualquer arquivo em `backend/`.
> Herdam e complementam as regras da raiz (`GEMINI.md`).

---

## 1. Concorrência — Semáforo é Obrigatório (Sem Exceções)

**Toda** chamada à OpenAI **deve** estar envolvida por `asyncio.Semaphore`.

```python
# ✅ CORRETO
semaphore = asyncio.Semaphore(25)
async with semaphore:
    resultado = await openai_client.beta.chat.completions.parse(...)

# ❌ PROIBIDO — risco de Rate Limit (erro 429) e suspensão de conta
resultados = await asyncio.gather(*[processar(item) for item in lote])
```

- Limite: `asyncio.Semaphore(25)` — nunca aumente sem análise de Rate Limit da OpenAI
- O Semáforo **deve ser compartilhado** entre todos os fluxos do mesmo processo (orçamento + curva ABC futura). Dois semáforos independentes dobram o limite efetivo.
- Sempre use `return_exceptions=True` no `gather()` para não quebrar o Event Loop

---

## 2. Retry com Exponential Backoff + Jitter (Obrigatório)

Toda chamada à OpenAI usa `tenacity` (já no `requirements.txt`) com backoff exponencial:

```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=30)
)
async def chamar_openai(...):
    ...
```

- ❌ **NUNCA** derrubar a requisição inteira em caso de erro 429 — sempre retentar com backoff
- ❌ **NUNCA** usar `time.sleep()` em código assíncrono — bloqueia o Event Loop

---

## 3. Banco de Dados — Supabase / asyncpg

### Pooler e statement_cache_size (Inviolável)
```python
# ✅ CORRETO — Transaction Pooler (porta 6543) com cache desativado
pool = await asyncpg.create_pool(
    dsn=settings.SUPABASE_DATABASE_URL,  # porta 6543
    statement_cache_size=0               # OBRIGATÓRIO com PgBouncer transacional
)

# ❌ ERRADO — porta 5432 (conexão direta) esgota conexões no auto-scaling
# ❌ ERRADO — sem statement_cache_size=0 → erro "prepared statement does not exist"
```

- **Porta do pooler:** Sempre `6543` (Transaction Pooler), nunca `5432` (conexão direta)
- **`statement_cache_size=0`**: Obrigatório. O PgBouncer em modo transacional é incompatível com prepared statements do asyncpg.

### IDs — Nunca UUID no Postgres
- ✅ Colunas `id` e `id_planilha` sempre `VARCHAR(255)`
- ❌ Nunca `UUID` — o Frontend gera strings como `macro_17000...` que quebram o cast `$1::uuid`

---

## 4. Redis Streams — SSE e Cache

### Namespace de Streams (Segurança Multi-Tenant)
```python
# ✅ CORRETO — namespace isolado por tenant
stream_key = f"stream:{tenant_id}:planilha:{id_planilha}"

# ❌ ERRADO — qualquer pessoa sabendo o ID da planilha pode interceptar
stream_key = f"stream:planilha:{id_planilha}"
```

### Cache Anti-Zumbi (Validação Obrigatória)
Antes de servir resultado do cache Redis, **sempre** validar se o `codigo_selecionado` ainda existe no Dossiê (Top 5) atual do Pinecone. Se não existir, invalidar o cache e reprocessar.

```python
# ✅ CORRETO
cache_hit = await redis.get(cache_key)
if cache_hit:
    codigo_cache = json.loads(cache_hit)["codigo_selecionado"]
    ids_atuais = [r["id"] for r in pinecone_results]
    if codigo_cache not in ids_atuais:
        cache_hit = None  # invalida cache zumbi
```

### TTL e Flush
- Cache semântico: TTL de 15 dias (reduz 70%+ do custo OpenAI)
- Ao mudar schema de status (`"ACEITO"`, `"RESSALVA"`, etc.): **Flush total do Redis** — nunca remendar cache com código

---

## 5. Structured Outputs — Schema Pydantic (Obrigatório)

```python
# ✅ CORRETO
resultado = await client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[...],
    response_format=AnaliseItem  # schema Pydantic
)

# ❌ PROIBIDO — parse de Markdown, JSON via regex ou string manipulation
resposta = client.chat.completions.create(...)
dados = json.loads(resposta.choices[0].message.content)
```

### Chain of Thought — Não Persiste (Inviolável)
```python
# ✅ CORRETO — extrair CoT antes de montar o DTO
resultado_pydantic = response.choices[0].message.parsed
logger.info(f"CoT: {resultado_pydantic.raciocinio_step_by_step}")  # apenas log
dto = {
    "codigo_selecionado": resultado_pydantic.codigo_selecionado,
    "justificativa": resultado_pydantic.justificativa,
    # raciocinio_step_by_step NÃO vai no DTO
}
```

---

## 6. Processamento em Chunks (Planilhas Massivas)

- Lotes processados de **50 em 50 linhas** — nunca a planilha inteira de uma vez
- Usar `asyncio.create_task()` para background tasks não bloqueantes
- Resultados escritos no Redis Stream (`XADD`) conforme chegam — nunca aguardar fim do lote inteiro

---

## 7. Deploy — Cloud Run (Configurações Críticas)

| Configuração | Valor Correto | Valor Errado |
|---|---|---|
| CPU Allocation | Com base em instâncias (Always Allocated) | Baseada em solicitações (throttling) |
| Build Context | `/backend/` (Dockerfile está aqui) | `/` (raiz do monorepo) |
| `BACKEND_API_URL` | URL base pura (sem `/api`, sem barra final) | Com sufixos ou `localhost` |
| Supabase porta | `6543` (Transaction Pooler) | `5432` (conexão direta) |

> **Por que CPU Always Allocated é crítico:** O Cloud Run congela o container entre requisições no modo "baseada em solicitações". Isso mata a entrega de dados via SSE no meio da planilha — o container é suspenso antes de terminar o processamento.

---

## 8. Isolamento de Domínio — Regra de Ouro

```
modules/orcamento/    ← Motor SINAPI + RRF + OpenAI (NÚCLEO — não mexa)
modules/sinapi/       ← Busca manual do usuário (autocomplete)
modules/auditoria/    ← Feature futura de PDFs (isolada — não compartilha lógica)
```

- Features novas **nunca** importam de módulos irmãos diretamente — criam interface de fronteira explícita
- Nenhuma dependência de `auditoria/` pode afetar `orcamento/` (Regressão Zero)
