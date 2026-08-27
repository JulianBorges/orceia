---
trigger: always_on
---

# OrceIA V3 — Regras Universais de IA (Workspace Root)

> Lido automaticamente por qualquer agente (Antigravity, Cursor, etc.) antes de qualquer interação neste repositório.
> Fonte canônica:`AI_Onboarding.md` e `Master_Plan.md`.
> Para contexto específico de Frontend ou Backend, leia também as regras em `.agents/rules/`.

---

## 1. Identidade do Projeto

**OrceIA** é um Copiloto de Orçamento de Engenharia governamental de alta performance.
- Processa planilhas de **5.000+ linhas** sem bloquear a UI (virtualização `@tanstack/react-virtual`)
- Cruza dados com o banco SINAPI via **Busca Semântica Híbrida (RRF)** — não altere o algoritmo sem aprovação
- Devolve resultados em **tempo real via SSE** (Server-Sent Events) sobre Redis Streams

**Stack obrigatória — não substitua sem aprovação explícita do usuário:**

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, Zustand, `@tanstack/react-virtual`, `@dnd-kit` |
| Backend | FastAPI, `asyncio`, `asyncpg`, `pydantic v2`, `tenacity` |
| Dados | Supabase (PostgreSQL + `pg_trgm`), Pinecone (vetores) |
| Cache/SSE | Redis Streams (`XADD`/`XREAD`) |
| IA | `gpt-4o-mini` Structured Outputs + `text-embedding-3-small` |

---

## 2. Princípios Invioláveis de Código

### KISS — Funções Nativas Primeiro
- ✅ `setTimeout` nativo para debounce
- ❌ Jamais instalar `use-debounce` ou equivalentes sem aprovação

### IDs de Banco — NUNCA UUID
- ✅ Colunas `id` e `id_planilha` sempre `VARCHAR(255)` no PostgreSQL
- ❌ `UUID` quebra o `asyncpg` com `invalid input syntax for type uuid`
- O Frontend gera IDs no formato `serv_<Date.now()>` ou `macro_<Date.now()>`

### DDD — Isolamento de Domínio (Obrigatório)
Cada feature nova nasce em seu próprio módulo. **Nunca adicione lógica nova dentro de módulos existentes sem aprovação explícita:**
```
backend/modules/orcamento/   ← Motor SINAPI (CONGELADO — não mexa sem permissão)
backend/modules/sinapi/      ← Busca manual do usuário
backend/modules/auth/        ← Autenticação multi-tenant
backend/modules/shared/      ← Funções públicas compartilhadas entre módulos
backend/modules/auditoria/   ← Feature futura de PDFs (isolada)
```

### Raciocínio da IA (CoT) — Nunca Persiste
- ✅ `raciocinio_step_by_step` vai para logs efêmeros (Cloud Run) e cache temporário (Redis)
- ❌ **NUNCA** viaja no payload SSE
- ❌ **NUNCA** é persistido no Supabase (Storage Bloat de gigabytes)

### Exceções Assíncronas
- Sempre usar `return_exceptions=True` em `asyncio.gather()` para não interromper o fluxo SSE

### Nomeação Semântica (Anti-Regex)
- ❌ **NUNCA** limpe formatação da IA via Regex no pós-processamento
- ✅ Use schemas Pydantic fechados com `beta.chat.completions.parse` (Structured Outputs)

---

## 3. Arquitetura de Comunicação

```
Browser → Next.js Edge Proxy (/api/proxy) → FastAPI Backend → Supabase / Pinecone / Redis
```

- `API_SECRET_KEY` injetada **server-side** no proxy — jamais exposta ao browser
- `middleware.ts` valida Cookie `orceia_tenant_session` (HttpOnly) e injeta `X-Tenant-ID`
- FastAPI extrai o tenant via `Depends(get_current_tenant)` — **nunca** via payload JSON
- **`BACKEND_API_URL` sem prefixo `NEXT_PUBLIC_`** (variável server-side apenas)

---

## 4. Motor RRF — Algoritmo Congelado

```python
# 1. Busca paralela (asyncio.gather): Trigramas (Supabase) + Embeddings (Pinecone)
# 2. RRF fusion: score = 1 / (k + rank + 1)
# 3. Boost de consenso: +20% se ID aparece em ambas as listas
# 4. Top 10 → gpt-4o-mini via beta.chat.completions.parse (schema Pydantic estrito)
```

**PROIBIDO:** alterar pesos, desativar boost, usar parse de Markdown ou Regex.

---

## 5. Post-Mortem — 11 Bugs Conhecidos (Não Repita)

| # | Bug | Causa-Raiz | Solução Definitiva |
|---|-----|------------|---------------------|
| 1 | Campos vazios na resposta da IA | Fadiga de contexto, sem schema | `Literal["BAIXO","ALTO"]` no Pydantic |
| 2 | Preâmbulos na justificativa | Controle só por System Prompt | `beta.chat.completions.parse` com schema fechado |
| 3 | SSE quebrado na Vercel | Serverless corta funções longas | Cloud Run + Semáforos + Redis Streams |
| 4 | Código espaguete | Hotfixes em estado acoplado | Módulos isolados (DDD) |
| 5 | Auto-Save acionando a IA | Frontend apontava para `/upsert-linhas` | Separar `/save-linhas` (DB) de `/upsert-linhas` (IA) |
| 6 | SWC crash UTF-8 | `Set-Content` do PowerShell gera UTF-16LE | Usar `write_to_file` interno (UTF-8 puro) |
| 7 | Cross-tenant SSE | Chave Redis pública por planilha | Namespace `stream:{tenant_id}:planilha:{id}` |
| 8 | Erro 404 Frontend→Backend | `BACKEND_API_URL` com `/api` no sufixo | URL base pura, sem sufixos |
| 9 | Storage Bloat Supabase | CoT persistido no banco | Extrair `raciocinio_step_by_step` antes do DTO |
| 10 | "Processando" infinito | Cache zumbi da V2 no Redis | Flush total do Redis ao mudar schema de status |
| 11 | Erro 500 asyncpg UUID | Coluna `id` como UUID | Sempre `VARCHAR(255)` |
| 12 | Estado Sujo O(n) | `setTableData` marcava todas as rows sujas | Usar Diff Cirúrgico via Map O(1) no Zustand |
| 13 | SSE trava em queda de rede | `EventSource` nativo não suporta header | Usar SEMPRE `@microsoft/fetch-event-source` com `Last-Event-ID` |
| 14 | Duplicação de Autenticação | `verify_proxy_secret` repetido por módulo | Importar SEMPRE de `core.security` (Filosofia DRY) |
| 15 | Injeção SQL Dinâmica | Tabela injetada via f-string | Usar dicionários de Allowlist (ex: `TABELAS_VALIDAS`) |
