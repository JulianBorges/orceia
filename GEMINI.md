# OrceIA V3 — Regras Universais de IA

> Este arquivo é lido automaticamente pelo agente de IA (Antigravity/Cursor) antes de qualquer interação neste repositório.
> Fonte canônica: `AI_Onboarding.md` e `Manual_OrceIA.md`.

---

## 1. Identidade e Contexto do Projeto

**OrceIA** é um Copiloto de Orçamento de Engenharia de alta performance. Processa planilhas de 5.000+ linhas, normaliza os dados, cruza com o banco SINAPI via Busca Semântica Híbrida (RRF) e devolve o orçamento preenchido em tempo real via SSE.

**Stack obrigatória (não substitua sem aprovação explícita):**
- Frontend: Next.js 14, Tailwind CSS, Zustand, `@tanstack/react-virtual`, `@dnd-kit`
- Backend: FastAPI, `asyncio`, `asyncpg`, `pydantic v2`
- Dados: Supabase (PostgreSQL + `pg_trgm`), Pinecone (vetores), Redis (cache + SSE)
- IA: OpenAI `gpt-4o-mini` (Structured Outputs) + `text-embedding-3-small`

**Atue como Tech Lead Sênior:** Ao analisar um problema, explique o gargalo arquitetural, os riscos da abordagem e garanta que a solução escala para ambientes governamentais massivos.

---

## 2. Princípios Invioláveis de Código (Guidelines)

### KISS — Funções Nativas Primeiro
Prefira funções nativas do React/Python antes de instalar novas dependências.
- ✅ `setTimeout` para debounce nativo
- ❌ instalar `use-debounce` ou bibliotecas equivalentes

### Nomeação Semântica (Anti-Regex)
Nunca limpe formatação da IA via Regex no pós-processamento. Confie no Semantic Naming nos schemas Pydantic e num System Prompt claro para induzir o formato nativo da LLM.

### Isolamento de Domínio (DDD — Obrigatório)
Cada feature nova nasce em seu próprio módulo isolado. **Nenhuma lógica nova é adicionada dentro de módulos existentes sem aprovação explícita.**
```
backend/modules/orcamento/   ← Motor de preços SINAPI (não mexa sem permissão)
backend/modules/sinapi/      ← Busca manual do usuário
backend/modules/auditoria/   ← Feature futura de PDFs (isolada)
```

### IDs de Banco de Dados — Nunca UUID
O Frontend usa strings pseudo-randômicas (`macro_12345`, `serv_67890`) geradas via `Date.now()`.
- ✅ Colunas `id` e `id_planilha` sempre como `VARCHAR(255)` no PostgreSQL
- ❌ **NUNCA** `UUID` — quebra o `asyncpg` com `invalid input syntax for type uuid`

### Exceções Assíncronas (Proteção do Event Loop)
Tasks assíncronas do backend **sempre** usam `return_exceptions=True` no `asyncio.gather()` para não interromper o fluxo de SSE do usuário caso a API da OpenAI caia.

### Raciocínio da IA (Chain of Thought) — Não Persiste
O campo `raciocinio_step_by_step` do Pydantic é extraído **antes** de empacotar a resposta DTO. Ele:
- ✅ Vai para os logs efêmeros do Cloud Run (auditoria técnica)
- ✅ Fica temporariamente no cache Redis
- ❌ **NUNCA** viaja no payload SSE para o Frontend
- ❌ **NUNCA** é persistido no Supabase (causaria Storage Bloat de gigabytes)

---

## 3. Arquitetura de Comunicação (Segurança Multi-Tenant)

```
Cliente React → /api/proxy (Next.js Server-Side) → FastAPI Backend
```

- A chave `API_SECRET_KEY` é injetada **server-side** no proxy. Nunca exposta ao browser.
- O `middleware.ts` do Next.js intercepta toda requisição, valida o Cookie `orceia_tenant_session` (HttpOnly) e injeta o header `X-Tenant-ID`.
- O FastAPI extrai o tenant via `Depends(get_current_tenant)` — **nunca** via payload JSON aberto.

---

## 4. Motor de Busca RRF (Não Altere o Algoritmo Sem Aprovação)

O processo no `ai_service.py`:
1. **Busca paralela** (`asyncio.gather`): Supabase (Trigramas `word_similarity()`) + Pinecone (Embeddings cosine)
2. **RRF fusion**: `score = 1 / (k + rank + 1)` para cada lista
3. **Boost de consenso**: +20% se o mesmo ID aparece nos dois resultados
4. **Top 10** vai para `gpt-4o-mini` via `beta.chat.completions.parse` com schema Pydantic estrito
5. **Structured Outputs obrigatório** — `beta.chat.completions.parse` mapeado em Pydantic. **PROIBIDO** parse de Markdown ou Regex

---

## 5. Post-Mortem — Bugs Conhecidos (Não Repita)

| # | Bug | Causa | Solução Definitiva |
|---|-----|-------|--------------------|
| 1 | Campos vazios na resposta da IA | Fadiga de contexto, sem schema estrito | `categoria_rigor: Literal["BAIXO","ALTO"]` no Pydantic |
| 2 | Preâmbulos injetados na justificativa | Controle apenas por System Prompt | `beta.chat.completions.parse` com schema fechado |
| 3 | Timeouts na Vercel / SSE quebrado | Serverless corta funções longas | Cloud Run + Semáforos + Redis Streams |
| 4 | Código espaguete de commits | Hotfixes em arquivos de estado acoplado | Congelar repo e abrir V3 limpa |
| 5 | Auto-Save acionando a IA | Frontend apontava para `/upsert-linhas` | Separar `/save-linhas` (DB) de `/upsert-linhas` (IA) |
| 6 | SWC crash UTF-8 no Next.js | `Set-Content` do PowerShell gera UTF-16LE | Sempre usar `write_to_file` interno (UTF-8 puro) |
| 7 | Espionagem de SSE entre tenants | Chave Redis pública por planilha | Namespace `stream:{tenant_id}:planilha:{id}` |
| 8 | Erro 404 Frontend → Backend | `BACKEND_API_URL` com `/api` no sufixo | URL base pura, sem sufixos |
| 9 | Storage Bloat no Supabase | CoT da IA persistido no banco | Extrair `raciocinio_step_by_step` antes do DTO |
| 10 | "Processando" infinito (cache zumbi) | Status legado da V2 no Redis | Flush total do Redis ao mudar schema de status |
| 11 | Erro 500 Type Mismatch asyncpg | Coluna `id` como UUID no Postgres | Coluna `id` sempre `VARCHAR(255)` |
