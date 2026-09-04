# OrceIA V3 — Contexto Arquitetural para IA

> **Leitura obrigatória antes de qualquer tarefa neste repositório.**
> As **regras de código ativas** (proibições, padrões invioláveis) vivem em `.agents/rules/GEMINI.md`.
> Este arquivo descreve o *que* o sistema é e *como* está estruturado hoje.

---

## 1. Visão Geral do Produto

O **OrceIA V3** é um Copiloto de Orçamento de Engenharia governamental de alta performance.

- Recebe planilhas de **5.000+ linhas** sem bloquear a UI (virtualização `@tanstack/react-virtual`)
- Detecta planilhas sem estrutura hierárquica ("Lista Plana") e oferece estruturação automática de EAP via IA
- Cruza dados com o banco SINAPI via **Busca Semântica Híbrida (RRF)** com Fallback Estratificado
- Devolve resultados em **tempo real via SSE** (Server-Sent Events) sobre Redis Streams
- Aceita Memoriais Descritivos em PDF para dois modos: **Geração** (guia de especificações) e **Auditoria** (conformidade)

---

## 2. Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 14, Tailwind CSS, Zustand, `@tanstack/react-virtual`, `@dnd-kit` |
| Backend | FastAPI, `asyncio`, `asyncpg`, `pydantic v2`, `tenacity` |
| Dados | Supabase (PostgreSQL + `pg_trgm`), Pinecone (vetores) |
| Cache/SSE | Redis Streams (`XADD`/`XREAD`), Semáforo Distribuído Redis |
| IA | `gpt-4o-mini` Structured Outputs + `text-embedding-3-small` |

---

## 3. Decisões Arquiteturais Fundamentais

**Por que Cloud Run e não Serverless?**
A Vercel corta funções em 10-60s. Uma planilha de 5.000 linhas leva minutos. Cloud Run com CPU Always Allocated mantém o container vivo durante todo o processamento SSE.

**Por que Redis Streams e não WebSockets?**
SSE com Redis Streams é stateless no servidor, resiliente a reconexões via `Last-Event-ID`, e unidirecional (servidor cliente) ideal para o fluxo de notificação de orçamento.

**Por que RRF e não busca puramente vetorial?**
Pinecone é excelente para semântica, falha em nomes técnicos exatos. pg_trgm é excelente em exatos, falha em sinônimos. O RRF une os dois matematicamente sem LLM extra.

**Por que Structured Outputs?**
`beta.chat.completions.parse` com schema Pydantic é determinístico — elimina parse de Regex, preâmbulos e campos vazios sob fadiga de contexto.

**Por que Semáforo Distribuído Redis?**
O `asyncio.Semaphore` é in-memory e quebra em multi-replica. A classe `RedisSemaphore` em `core/redis_client.py` usa `SET key NX EX 60` para distribuir locks entre workers com TTL anti-deadlock.

**Por que multi-tenancy via Header?**
Trafegar `tenant_id` no body abre vetor de ataque. O `middleware.ts` lê o Cookie HttpOnly, injeta `X-Tenant-ID` inforjável pelo browser. FastAPI consome via `Depends(get_current_tenant)`.

---

## 4. Mapa do Código (Estado Atual)

```
orceia_v3/
├── .agents/rules/GEMINI.md       <- Regras universais (lidas automaticamente - NUNCA ignore)
├── AI_Onboarding.md              <- Este arquivo (contexto e mapa)
├── Master_Plan.md                <- Status de Sprints (o que foi e nao foi implementado)
├── Manual_OrceIA.md              <- Blueprint completo de construcao + Post-Mortem
│
├── backend/
│   ├── main.py                   <- FastAPI entry point: lifespan, CORS, registro de routers
│   │                                WEB_CONCURRENCY > 1 emite aviso (RedisSemaphore ja suporta multi-worker)
│   ├── core/
│   │   ├── config.py             <- Settings via pydantic-settings (le .env)
│   │   ├── db.py                 <- Pool asyncpg (statement_cache_size=0 obrigatorio)
│   │   ├── security.py           <- verify_proxy_secret + get_current_tenant (DRY central)
│   │   ├── ai_client.py          <- Singleton AsyncOpenAI (timeout=30s, max_retries=0)
│   │   ├── redis_client.py       <- Streams SSE, Cache SHA-256, RedisSemaphore distribuido
│   │   ├── text_utils.py         <- normalizar_chave(): NFD + lower + colapso de espacos
│   │   └── vocabulario_obra.py   <- Dicionario de canteiro: jargoes -> terminologia SINAPI
│   │
│   └── modules/
│       ├── orcamento/            <- NUCLEO - nao mexa sem aprovacao explicita
│       │   ├── preprocessor.py   <- normalizar_termo_busca(): Dicionario -> Regex dimensional -> TermoNormalizado
│       │   │                        extrair_dimensoes_numericas(): tolerancia deterministica em Python
│       │   ├── reformulador.py   <- Agente de variacoes tecnicas (acionado pelo Fallback RRF)
│       │   ├── search_engine.py  <- RRF: Pinecone + pg_trgm, boost consenso 20%, Fallback Estratificado
│       │   │                        Threshold baseado em fonte unica (nao dupla) para evitar falsos positivos
│       │   ├── ai_agents.py      <- Agente Engenheiro (Structured Outputs, schema AnaliseIA)
│       │   ├── services.py       <- Orquestrador: RLHF -> RRF -> Cache -> Tolerancia -> Memorial -> IA -> SSE
│       │   ├── routes.py         <- /upsert-linhas, /save-linhas, /stream, /feedback, /planilhas (CRUD)
│       │   └── schemas.py        <- DTOs: LinhaOrcamentoBase (macro_item_context, projeto_id), AnaliseIA
│       │
│       ├── eap/                  <- Agente de Estruturacao (Lista Plana -> EAP hierarquica)
│       │   ├── routes.py         <- POST /eap/estruturar
│       │   ├── ai_agent.py       <- Agente EAP com indices posicionais (sem UUIDs, economiza tokens)
│       │   └── schemas.py
│       │
│       ├── auditoria/            <- Pipeline Bidirecional de Memoriais Descritivos (PDF)
│       │   ├── routes.py         <- POST /ingerir-memorial, GET /status/{id}, POST /auditar-planilha (SSE)
│       │   │                        /auditar-planilha usa asyncio.Semaphore(5) para proteger rate limit
│       │   ├── services.py       <- pypdf -> chunking semantico -> embeddings -> Pinecone
│       │   │                        buscar_contexto_memorial() usada pelo Modo Geracao em orcamento/services.py
│       │   ├── ai_agent.py       <- Agente Auditor: CONFORME/DIVERGENTE/SEM_REFERENCIA (Structured Outputs)
│       │   └── schemas.py
│       │
│       ├── sinapi/               <- Busca manual do usuario (autocomplete)
│       ├── auth/                 <- Autenticacao multi-tenant (Cookie HttpOnly)
│       └── shared/
│           └── sinapi_search.py  <- search_sinapi_por_trigrama() com allowlist de tabelas (injecao SQL bloqueada)
│
└── frontend/src/
    ├── middleware.ts              <- Valida Cookie orceia_tenant_session, injeta X-Tenant-ID
    ├── app/
    │   ├── page.tsx               <- Pagina principal: tabela + header com todos os botoes de acao
    │   └── api/proxy/[...path]/route.ts  <- Proxy server-side: injeta API_SECRET_KEY + X-Tenant-ID
    │
    ├── components/
    │   ├── BudgetTable.tsx         <- Tabela virtualizada 60 FPS
    │   ├── UploadPlanilha.tsx      <- Upload XLSX: deteccao de Lista Plana -> FlatListModal
    │   ├── FlatListModal.tsx       <- Modal: Lista Plana como esta OU estruturar EAP com IA
    │   ├── MemorialUploadButton.tsx <- Upload multipart PDF -> POST /auditoria/ingerir-memorial
    │   ├── AuditorButton.tsx       <- Aparece quando memorialId existe; aciona auditarPlanilha()
    │   ├── SavedBudgetsModal.tsx   <- Modal "Meus Orcamentos": lista e recupera planilhas salvas
    │   └── MemoryModal.tsx         <- Drawer lateral: memoria de calculo da IA (0 requests extras)
    │
    ├── store/
    │   └── useBudgetStore.ts       <- Zustand: diff cirurgico O(1)
    │                                  persist: tableData, bdi, title, planilhaId, memorialId
    │                                  processarOrcamentoIA(): injeta macro_item_context + projeto_id
    │                                  auditarPlanilha(): SSE via @microsoft/fetch-event-source
    │                                  estruturarEAP(): chama /eap/estruturar
    │
    ├── hooks/
    │   ├── useAutoSave.ts          <- Debounce nativo setTimeout -> /save-linhas (NUNCA /upsert-linhas)
    │   └── useSseListener.ts       <- fetch-event-source com Last-Event-ID e AbortController
    │
    └── utils/
        └── budgetUtils.ts          <- BudgetItem type, AIStatus union type (inclui ERRO), recalculateNumbers
```

---

## 5. Pipeline de Processamento de uma Linha (Fluxo Completo)

```
UploadPlanilha.tsx
  -> [0% macro itens?] -> FlatListModal -> estruturarEAP() -> POST /eap/estruturar
  -> processarOrcamentoIA()
       percorre tableData: guarda ultimo is_macro_item como currentMacroName
       monta payload com macro_item_context e projeto_id (se memorialId existir)
  -> POST /api/proxy/orcamento/upsert-linhas (chunks de 100)
  -> FastAPI: linha.tenant_id = tenant_id (server-side, nunca via payload)
  -> processar_linha_com_semaforo() [RedisSemaphore(3)]
       check_rlhf_memory() [normalizar_chave -> banco memoria_organizacional]
       realizar_busca_hibrida()
           normalizar_termo_busca() [Dicionario Canteiro -> Regex dimensional]
           asyncio.gather(pg_trgm, pinecone[filtro unidade com fallback])
           RRF fusion [boost consenso 20%]
           [score < 85% de fonte unica?] -> gerar_variacoes_tecnicas() -> RRF expandido
       get_ai_cache() [normalizar_chave -> SHA-256]
       extrair_dimensoes_numericas() -> injeta [TOLERANCIA: ACEITAVEL/INACEITAVEL] nos candidatos
       [projeto_id?] -> buscar_contexto_memorial() [Pinecone namespace memorial:{tenant}:{projeto}]
       consultar_agente_engenheiro() [Structured Outputs -> AnaliseIA]
       print(raciocinio_step_by_step) [EFEMERO - nunca persiste, nunca viaja no SSE]
       set_ai_cache() [apenas veredito logico, sem precos pereciveis]
  -> publish_sse_event(stream:{tenant_id}:planilha:{id})
  -> useSseListener -> updateRowById() [mutacao O(1), nao marca dirty - evita loop auto-save]
```

---

## 6. Namespaces Pinecone

| Namespace | Conteudo |
|-----------|----------|
| `composicoes_sinapi` | Base SINAPI global (composicoes) |
| `insumos_sinapi` | Base SINAPI global (insumos) |
| `{tenant_id}_composicoes_sinapi` | Embeddings customizados do tenant |
| `memorial:{tenant_id}:{projeto_id}` | Chunks do Memorial Descritivo (PDF) |

---

## 7. Rotas Backend Completas

| Metodo | Rota | Descricao |
|--------|------|-----------|
| POST | `/orcamento/upsert-linhas` | Aciona IA em background + SSE |
| POST | `/orcamento/save-linhas` | Persiste no banco (Auto-Save, sem IA) |
| GET | `/orcamento/stream/{id_planilha}` | Canal SSE (Redis XREAD) |
| POST | `/orcamento/feedback` | Salva decisao humana (RLHF) + invalida cache |
| DELETE | `/orcamento/linhas` | Remove linhas com protecao cross-tenant |
| GET | `/orcamento/planilhas` | Lista planilhas salvas do tenant |
| GET | `/orcamento/planilhas/{id}/linhas` | Recupera linhas de uma planilha |
| POST | `/eap/estruturar` | Estrutura Lista Plana em EAP hierarquica |
| POST | `/auditoria/ingerir-memorial` | PDF -> chunks -> Pinecone |
| GET | `/auditoria/status/{projeto_id}` | Verifica se memorial esta carregado |
| POST | `/auditoria/auditar-planilha` | SSE: cruza orcamento contra memorial |
| POST | `/sinapi/search` | Busca manual do usuario no SINAPI |
| POST | `/auth/login` | Autenticacao multi-tenant |

---

## 8. Regras Criticas de Banco de Dados

- **IDs: SEMPRE `VARCHAR(255)`** — nunca `UUID` no schema PostgreSQL
- O asyncpg retorna objetos `uuid.UUID` para colunas tipadas como UUID, quebrando o Pydantic v2
- Queries de leitura devem usar `CAST(id AS TEXT)` e `CAST(id_planilha AS TEXT)` explicitamente
- `statement_cache_size=0` obrigatorio na pool asyncpg (PgBouncer transacional do Supabase)

---

## 9. Como Navegar no Projeto

| Intencao | Arquivo |
|----------|---------|
| Regras inviolaveis de codigo | `.agents/rules/GEMINI.md` |
| Contexto arquitetural (este arquivo) | `AI_Onboarding.md` |
| Blueprint de construcao + Post-Mortem | `Manual_OrceIA.md` |
| Status de roadmap de produto | `Master_Plan.md` |
