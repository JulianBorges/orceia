# OrceIA V3 — Arquitetura Core (Regras Invioláveis)

> Lido automaticamente quando a IA analisa ou modifica qualquer arquivo do repositório.
> Regras específicas de Frontend → `02_frontend.md`. De Backend → `03_backend.md`.

---

## 1. Módulos e Responsabilidades (DDD)

```
backend/modules/
├── orcamento/      ← CONGELADO. Motor SINAPI completo. Não adicione lógica sem aprovação.
│   ├── routes.py      Endpoints: /upsert-linhas, /save-linhas, /linhas (DELETE), /stream/{id}
│   ├── services.py    Orquestrador: semáforo, cache Redis, gather paralelo
│   ├── search_engine.py  RRF: Trigrama + Pinecone → Top 10
│   ├── ai_agents.py   Agente GPT-4o-mini com Structured Outputs
│   └── schemas.py     Contratos Pydantic: LinhaOrcamentoUpsert, AnaliseIA, DeleteLinhasRequest
├── sinapi/         ← Busca manual do usuário (autocomplete). Usa shared/sinapi_search.py.
├── auth/           ← Autenticação: valida tenant_id contra tabela `tenants` no Supabase.
├── shared/         ← Funções PÚBLICAS compartilhadas entre módulos.
│   └── sinapi_search.py  Busca Trigrama reutilizável (pg_trgm).
└── auditoria/      ← Feature futura (Sprint 5). Não implementar sem aprovação.
```

**Regra de Ouro:** `sinapi/` pode importar de `shared/`. `orcamento/` pode importar de `shared/`.
**PROIBIDO:** `sinapi/` importar de `orcamento/` ou vice-versa diretamente.

---

## 2. Separação Crítica de Endpoints

| Endpoint | Propósito | Aciona IA? |
|---|---|---|
| `POST /orcamento/upsert-linhas` | Processa lote com IA (RRF + GPT) | ✅ SIM |
| `POST /orcamento/save-linhas` | Auto-save de edições manuais (DB only) | ❌ NÃO |
| `DELETE /orcamento/linhas` | Remove linhas do banco (cross-tenant safe) | ❌ NÃO |
| `GET /orcamento/stream/{id}` | Canal SSE do tenant | ❌ NÃO |
| `GET /sinapi/search` | Autocomplete manual | ❌ NÃO |
| `GET /auth/validate-tenant` | Validação de tenant no login | ❌ NÃO |

**Nunca conecte o auto-save ao endpoint `/upsert-linhas`.** Este é o Bug #5 do Post-Mortem.

---

## 3. Fluxo SSE (Server-Sent Events)

```
Frontend (EventSource) → GET /orcamento/stream/{id_planilha}
                                    ↓
                         FastAPI publica no Redis Stream
                         Key: stream:{tenant_id}:planilha:{id_planilha}
                                    ↑
                     ai_agents.py → publish_sse_event()
```

- **Namespace obrigatório por tenant** no Redis: `stream:{tenant_id}:planilha:{id}` — Bug #7
- O worker FastAPI DEVE rodar com `--workers 1` (semáforo Python não é distribuído)
- Para escala horizontal: adicionar réplicas do container, não workers dentro do container

---

## 4. Multi-Tenancy

O sistema é **completamente isolado por tenant** em todas as camadas:

| Camada | Como funciona |
|---|---|
| Cookie | `orceia_tenant_session` HttpOnly setado após `/auth/validate-tenant` |
| Next.js Middleware | Injeta `X-Tenant-ID` em toda requisição |
| FastAPI | `Depends(get_current_tenant)` extrai o header — nunca do payload JSON |
| Supabase | Cláusula `WHERE tenant_id = $x` em todas as queries — nunca omitir |
| Redis | Namespace `stream:{tenant_id}:...` em todas as chaves |
| Pinecone | Filtro por namespace `tenant_{id}` em todas as buscas vetoriais |

---

## 5. Cache Redis (Estrutura de Chaves)

```
stream:{tenant_id}:planilha:{id_planilha}   → Redis Stream (SSE payload)
cache:ai:{sha256_do_termo}                   → Cache da resposta da IA (15 dias TTL)
```

- O cache de IA usa **SHA-256 do termo** como chave — independente do tenant (a SINAPI é global)
- **NUNCA** use chaves sem namespace de tenant para dados do usuário

---

## 6. Banco de Dados (Supabase / asyncpg)

- `statement_cache_size=0` obrigatório na conexão asyncpg (compatibilidade PgBouncer)
- IDs sempre `VARCHAR(255)` — jamais `UUID` (Bug #11)
- Upsert em lote via `executemany` — custo O(1) de viagens ao banco
- RLS habilitado em todas as tabelas, mas a segurança principal é a cláusula `WHERE tenant_id`

**Tabelas existentes:**
```
tenants                → Source of truth para autenticação
planilhas              → Metadados das planilhas (id, tenant_id, titulo)
planilhas_linhas       → Linhas do orçamento (FK para planilhas com CASCADE DELETE)
memoria_organizacional → RLHF: preferências do engenheiro por termo
```
