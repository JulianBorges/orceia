# OrceIA — Contexto Arquitetural do Projeto

> **Nota:** Este arquivo contém o contexto narrativo e as decisões arquiteturais do projeto.
> As **regras de código ativas** (guidelines, proibições e padrões) agora vivem nos arquivos `GEMINI.md`
> hierárquicos, lidos automaticamente pela IA:
> - Regras universais → `/GEMINI.md`
> - Regras de Frontend → `/frontend/GEMINI.md`
> - Regras de Backend → `/backend/GEMINI.md`

---

## 1. Visão Geral do Produto

O **OrceIA** é um Copiloto de Orçamento de Engenharia de alta performance. Recebe planilhas massivas (5.000+ linhas) do usuário, normaliza os dados, cruza com bancos oficiais (SINAPI) via Busca Semântica Híbrida (RRF) e devolve o orçamento preenchido em tempo real via SSE.

**Público-alvo:** Engenheiros e gestores de obras em ambientes governamentais e corporativos que precisam orçar insumos e composições com rastreabilidade e conformidade ao SINAPI.

---

## 2. Stack Tecnológica

| Camada | Tecnologia | Motivo da Escolha |
|--------|------------|-------------------|
| Frontend | Next.js 14 + Tailwind CSS | SSR, App Router e ecossistema maduro |
| Estado | Zustand | Mutações atômicas O(1) sem re-renders globais |
| Virtualização | `@tanstack/react-virtual` | 60 FPS com 5.000+ linhas no DOM |
| DnD | `@dnd-kit` | Compatível com listas virtualizadas |
| Backend | FastAPI + asyncio | 100% assíncrono, ideal para SSE de longa duração |
| DB Relacional | Supabase (PostgreSQL + `pg_trgm`) | Busca lexical por trigramas sem ElasticSearch |
| DB Vetorial | Pinecone | Busca semântica por namespace isolado |
| Cache/Mensageria | Redis Streams | SSE resiliente com `Last-Event-ID` e cache SHA-256 |
| IA | OpenAI `gpt-4o-mini` + `text-embedding-3-small` | Structured Outputs + custo controlado |

---

## 3. Decisões Arquiteturais e seus Porquês

### 3.1. Por que Não Usamos Serverless para o Backend?

A Vercel corta funções serverless em 10–60 segundos. Uma planilha de 5.000 linhas leva vários minutos para ser processada pela OpenAI. Solução: **Google Cloud Run** com CPU Always Allocated (`--no-cpu-throttling`), onde o container persiste durante toda a sessão de processamento.

### 3.2. Por que Redis Streams e Não WebSockets?

WebSockets exigem conexão bidirecional persistente — cara e complexa de escalar horizontalmente. O SSE com Redis Streams (`XADD`/`XREAD`) é unidirecional (servidor → cliente), stateless no servidor e resiliente: o `Last-Event-ID` permite que o cliente reconecte e receba apenas os pacotes perdidos sem reprocessamento.

### 3.3. Por que RRF em Vez de Busca Puramente Vetorial?

Busca vetorial (Pinecone) é excelente para semântica, mas falha em nomes técnicos exatos como `"CONCRETO FCK 30 MPa"`. Busca por trigramas (PostgreSQL `pg_trgm`) é rápida em exatos, mas falha em sinônimos. O **Reciprocal Rank Fusion** une os dois mundos matematicamente, sem precisar de um LLM extra para fazer o merge — economizando latência e custo.

### 3.4. Por que Structured Outputs em Vez de Prompt Engineering Puro?

System Prompts "gentis" falham sob fadiga de contexto e em modelos menores. `beta.chat.completions.parse` com schema Pydantic é determinístico: a OpenAI garante que o JSON retornado será válido e aderente ao schema — eliminando a necessidade de parse por Regex ou tentativas de correção no pós-processamento.

### 3.5. Por que Zero-Shot Chain of Thought no Schema?

Ao forçar o modelo a preencher `raciocinio_step_by_step` *antes* do veredito final, ativamos o raciocínio lógico interno da LLM (como um "rascunho mental") antes de ela "commitar" a resposta. Isso reduz drasticamente alucinações em itens ambíguos como materiais com especificações dimensionais.

### 3.6. Por que o Cache SHA-256 no Redis?

Itens de engenharia se repetem entre planilhas de clientes diferentes (ex: `"ALVENARIA DE TIJOLO CERÂMICO"` aparece em 80%+ das obras). Um hash criptográfico do termo pesquisado permite reutilizar o veredito da IA por 15 dias, reduzindo em 70%+ os custos da OpenAI sem comprometer a qualidade.

### 3.7. Por que Multi-Tenancy via Header e Não via Payload?

Trafegar `tenant_id` no body JSON abre vetor de ataque: qualquer client pode forjar o campo. O `middleware.ts` do Next.js lê o Cookie HttpOnly (não acessível por JavaScript), extrai o tenant e o injeta como header `X-Tenant-ID` — inforjável pelo browser. O FastAPI consome apenas via `Depends(get_current_tenant)`.

---

## 4. Mapa do Código

```
orceia_v3/
├── GEMINI.md                   ← Regras universais de IA (auto-injetadas)
├── Master_Plan.md              ← Roadmap de Sprints (fonte de verdade de produto)
├── Manual_OrceIA.md            ← Blueprint completo de construção (referência humana)
├── Plano_AuditorIA.md          ← Spec da Sprint 5 (feature futura de PDFs)
│
├── backend/
│   ├── GEMINI.md               ← Regras de IA para backend (auto-injetadas)
│   ├── main.py                 ← Entry point FastAPI (lifespan, CORS, routers)
│   ├── core/
│   │   ├── config.py           ← Settings via pydantic-settings
│   │   ├── db.py               ← Pool asyncpg (statement_cache_size=0)
│   │   ├── security.py         ← Dependências centrais de segurança (DRY)
│   │   ├── ai_client.py        ← Singleton OpenAI c/ Timeout global (30.0s)
│   │   └── redis_client.py     ← Cliente Redis (streams + cache)
│   └── modules/
│       ├── orcamento/          ← Motor SINAPI: RRF, OpenAI, SSE (NÚCLEO — não mexa)
│       │   ├── preprocessor.py ← Agente Corretor (normaliza termos pré-Pinecone)
│       │   ├── routes.py       ← Endpoints: /upsert-linhas, /save-linhas, /stream
│       │   ├── services.py     ← Orquestração: chunks, semáforo, SSE
│       │   ├── search_engine.py← Algoritmo RRF (Pinecone + Supabase)
│       │   ├── ai_agents.py    ← Structured Outputs com Pydantic
│       │   └── schemas.py      ← DTOs Pydantic v2
│       └── sinapi/             ← Busca manual do usuário (autocomplete)
│           └── routes.py
│
└── frontend/
    ├── GEMINI.md               ← Regras de IA para frontend (auto-injetadas)
    └── src/
        ├── middleware.ts       ← Intercepta req, valida cookie, injeta X-Tenant-ID
        ├── app/
        │   ├── page.tsx        ← Página principal (tabela + upload)
        │   └── api/proxy/      ← Proxy server-side (mascara API_SECRET_KEY)
        ├── components/
        │   ├── BudgetTable.tsx         ← Tabela virtualizada (60 FPS)
        │   ├── BudgetTableCells.tsx    ← Células editáveis
        │   ├── SortableRow.tsx         ← DnD com @dnd-kit
        │   ├── MemoryModal.tsx         ← Memória de cálculo da IA (0 req extras)
        │   ├── CompositionDetailsModal.tsx
        │   └── CompositionCreatorModal.tsx
        ├── store/
        │   └── useBudgetStore.ts       ← Zustand: mutações O(1), diff cirúrgico
        └── hooks/
            ├── useAutoSave.ts          ← Debounce + /save-linhas (nunca /upsert-linhas)
            └── useSseListener.ts       ← Consome SSE via fetch-event-source (Last-Event-ID)
```

---

## 5. Como Navegar no Projeto

- **Próxima feature a implementar?** → Consulte `Master_Plan.md` (roadmap de Sprints 1-5).
- **Refatoração e correção de bugs auditados?** → Consulte `Refactor_Plan.md` (Sprints 6-9).
- **Dúvida de construção do zero?** → Consulte `Manual_OrceIA.md` (blueprint completo).
- **AuditorIA (PDFs)?** → Consulte `Plano_AuditorIA.md`.
- **Regra de código específica?** → Os `GEMINI.md` e `.agents/rules/` são a fonte de verdade ativa.