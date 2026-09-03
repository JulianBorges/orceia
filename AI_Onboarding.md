# OrceIA â€” Contexto Arquitetural do Projeto

> **Nota:** Este arquivo contÃ©m o contexto narrativo e as decisÃµes arquiteturais do projeto.
> As **regras de cÃ³digo ativas** (guidelines, proibiÃ§Ãµes e padrÃµes) agora vivem nos arquivos `GEMINI.md`
> hierÃ¡rquicos, lidos automaticamente pela IA:
> - Regras universais â†’ `/GEMINI.md`
> - Regras de Frontend â†’ `/frontend/GEMINI.md`
> - Regras de Backend â†’ `/backend/GEMINI.md`

---

## 1. VisÃ£o Geral do Produto

O **OrceIA** Ã© um Copiloto de OrÃ§amento de Engenharia de alta performance. Recebe planilhas massivas (5.000+ linhas) do usuÃ¡rio, normaliza os dados, cruza com bancos oficiais (SINAPI) via Busca SemÃ¢ntica HÃ­brida (RRF) e devolve o orÃ§amento preenchido em tempo real via SSE.

**PÃºblico-alvo:** Engenheiros e gestores de obras em ambientes governamentais e corporativos que precisam orÃ§ar insumos e composiÃ§Ãµes com rastreabilidade e conformidade ao SINAPI.

---

## 2. Stack TecnolÃ³gica

| Camada | Tecnologia | Motivo da Escolha |
|--------|------------|-------------------|
| Frontend | Next.js 14 + Tailwind CSS | SSR, App Router e ecossistema maduro |
| Estado | Zustand | MutaÃ§Ãµes atÃ´micas O(1) sem re-renders globais |
| VirtualizaÃ§Ã£o | `@tanstack/react-virtual` | 60 FPS com 5.000+ linhas no DOM |
| DnD | `@dnd-kit` | CompatÃ­vel com listas virtualizadas |
| Backend | FastAPI + asyncio | 100% assÃ­ncrono, ideal para SSE de longa duraÃ§Ã£o |
| DB Relacional | Supabase (PostgreSQL + `pg_trgm`) | Busca lexical por trigramas sem ElasticSearch |
| DB Vetorial | Pinecone | Busca semÃ¢ntica por namespace isolado |
| Cache/Mensageria | Redis Streams | SSE resiliente com `Last-Event-ID` e cache SHA-256 |
| IA | OpenAI `gpt-4o-mini` + `text-embedding-3-small` | Structured Outputs + custo controlado |

---

## 3. DecisÃµes Arquiteturais e seus PorquÃªs

### 3.1. Por que NÃ£o Usamos Serverless para o Backend?

A Vercel corta funÃ§Ãµes serverless em 10â€“60 segundos. Uma planilha de 5.000 linhas leva vÃ¡rios minutos para ser processada pela OpenAI. SoluÃ§Ã£o: **Google Cloud Run** com CPU Always Allocated (`--no-cpu-throttling`), onde o container persiste durante toda a sessÃ£o de processamento.

### 3.2. Por que Redis Streams e NÃ£o WebSockets?

WebSockets exigem conexÃ£o bidirecional persistente â€” cara e complexa de escalar horizontalmente. O SSE com Redis Streams (`XADD`/`XREAD`) Ã© unidirecional (servidor â†’ cliente), stateless no servidor e resiliente: o `Last-Event-ID` permite que o cliente reconecte e receba apenas os pacotes perdidos sem reprocessamento.

### 3.3. Por que RRF em Vez de Busca Puramente Vetorial?

Busca vetorial (Pinecone) Ã© excelente para semÃ¢ntica, mas falha em nomes tÃ©cnicos exatos como `"CONCRETO FCK 30 MPa"`. Busca por trigramas (PostgreSQL `pg_trgm`) Ã© rÃ¡pida em exatos, mas falha em sinÃ´nimos. O **Reciprocal Rank Fusion** une os dois mundos matematicamente, sem precisar de um LLM extra para fazer o merge â€” economizando latÃªncia e custo.

### 3.4. Por que Structured Outputs em Vez de Prompt Engineering Puro?

System Prompts "gentis" falham sob fadiga de contexto e em modelos menores. `beta.chat.completions.parse` com schema Pydantic Ã© determinÃ­stico: a OpenAI garante que o JSON retornado serÃ¡ vÃ¡lido e aderente ao schema â€” eliminando a necessidade de parse por Regex ou tentativas de correÃ§Ã£o no pÃ³s-processamento.

### 3.5. Por que Zero-Shot Chain of Thought no Schema?

Ao forÃ§ar o modelo a preencher `raciocinio_step_by_step` *antes* do veredito final, ativamos o raciocÃ­nio lÃ³gico interno da LLM (como um "rascunho mental") antes de ela "commitar" a resposta. Isso reduz drasticamente alucinaÃ§Ãµes em itens ambÃ­guos como materiais com especificaÃ§Ãµes dimensionais.

### 3.6. Por que o Cache SHA-256 no Redis?

Itens de engenharia se repetem entre planilhas de clientes diferentes (ex: `"ALVENARIA DE TIJOLO CERÃ‚MICO"` aparece em 80%+ das obras). Um hash criptogrÃ¡fico do termo pesquisado permite reutilizar o veredito da IA por 15 dias, reduzindo em 70%+ os custos da OpenAI sem comprometer a qualidade.

### 3.7. Por que Multi-Tenancy via Header e NÃ£o via Payload?

Trafegar `tenant_id` no body JSON abre vetor de ataque: qualquer client pode forjar o campo. O `middleware.ts` do Next.js lÃª o Cookie HttpOnly (nÃ£o acessÃ­vel por JavaScript), extrai o tenant e o injeta como header `X-Tenant-ID` â€” inforjÃ¡vel pelo browser. O FastAPI consome apenas via `Depends(get_current_tenant)`.

---

## 4. Mapa do CÃ³digo

```
orceia_v3/
â”œâ”€â”€ GEMINI.md                   â†� Regras universais de IA (auto-injetadas)
â”œâ”€â”€ Master_Plan.md              â†� Roadmap de Sprints (fonte de verdade de produto)
â”œâ”€â”€ Manual_OrceIA.md            â†� Blueprint completo de construÃ§Ã£o (referÃªncia humana)
â”œâ”€â”€ Plano_AuditorIA.md          â†� Spec da Sprint 5 (feature futura de PDFs)
â”‚
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ GEMINI.md               â†� Regras de IA para backend (auto-injetadas)
â”‚   â”œâ”€â”€ main.py                 â†� Entry point FastAPI (lifespan, CORS, routers)
â”‚   â”œâ”€â”€ core/
â”‚   â”‚   â”œâ”€â”€ config.py           â† Settings via pydantic-settings
â”‚   â”‚   â”œâ”€â”€ db.py               â† Pool asyncpg (statement_cache_size=0)
â”‚   â”‚   â”œâ”€â”€ security.py         â† DependÃªncias centrais de seguranÃ§a (DRY)
â”‚   â”‚   â”œâ”€â”€ ai_client.py        â† Singleton OpenAI c/ Timeout global (30.0s)
â”‚   â”‚   â””â”€â”€ redis_client.py     â† Cliente Redis (streams + cache)
â”‚   â””â”€â”€ modules/
â”‚       â”œâ”€â”€ orcamento/          â† Motor SINAPI: RRF, OpenAI, SSE (NÃšCLEO â€” nÃ£o mexa)
â”‚       â”‚   â”œâ”€â”€ preprocessor.py â† Agente Corretor (normaliza termos prÃ©-Pinecone)
â”‚       â”‚   â”œâ”€â”€ routes.py       â† Endpoints: /upsert-linhas, /save-linhas, /stream
â”‚       â”‚   â”œâ”€â”€ services.py     â† OrquestraÃ§Ã£o: chunks, semÃ¡foro, SSE
â”‚       â”‚   â”œâ”€â”€ search_engine.pyâ† Algoritmo RRF (Pinecone + Supabase)
â”‚       â”‚   â”œâ”€â”€ ai_agents.py    â† Structured Outputs com Pydantic
â”‚       â”‚   â””â”€â”€ schemas.py      â† DTOs Pydantic v2
â”‚       â”œâ”€â”€ eap/                â† Agente de EstruturaÃ§Ã£o (Lista Plana -> EAP)
â”‚       â”‚   â”œâ”€â”€ routes.py
â”‚       â”‚   â”œâ”€â”€ ai_agent.py
â”‚       â”‚   â””â”€â”€ schemas.py
â”‚       â””â”€â”€ sinapi/             â† Busca manual do usuÃ¡rio (autocomplete)
â”‚           â””â”€â”€ routes.py
â”‚
â””â”€â”€ frontend/
    â”œâ”€â”€ GEMINI.md               â† Regras de IA para frontend (auto-injetadas)
    â””â”€â”€ src/
        â”œâ”€â”€ middleware.ts       â† Intercepta req, valida cookie, injeta X-Tenant-ID
        â”œâ”€â”€ app/
        â”‚   â”œâ”€â”€ page.tsx        â†� PÃ¡gina principal (tabela + upload)
        â”‚   â””â”€â”€ api/proxy/      â†� Proxy server-side (mascara API_SECRET_KEY)
        â”œâ”€â”€ components/
        â”‚   â”œâ”€â”€ BudgetTable.tsx         â†� Tabela virtualizada (60 FPS)
        â”‚   â”œâ”€â”€ BudgetTableCells.tsx    â†� CÃ©lulas editÃ¡veis
        â”‚   â”œâ”€â”€ SortableRow.tsx         â†� DnD com @dnd-kit
        â”‚   â”œâ”€â”€ MemoryModal.tsx         â†� MemÃ³ria de cÃ¡lculo da IA (0 req extras)
        â”‚   â”œâ”€â”€ CompositionDetailsModal.tsx
        â”‚   â””â”€â”€ CompositionCreatorModal.tsx
        â”œâ”€â”€ store/
        â”‚   â””â”€â”€ useBudgetStore.ts       â†� Zustand: mutaÃ§Ãµes O(1), diff cirÃºrgico
        â””â”€â”€ hooks/
            â”œâ”€â”€ useAutoSave.ts          â†� Debounce + /save-linhas (nunca /upsert-linhas)
            â””â”€â”€ useSseListener.ts       â†� Consome SSE via fetch-event-source (Last-Event-ID)
```

---

## 5. Como Navegar no Projeto

- **PrÃ³xima feature a implementar?** â†’ Consulte `Master_Plan.md` (roadmap de Sprints 1-5).
- **Próxima feature a implementar?** → Consulte `Master_Plan.md` (roadmap de Sprints 1-5).
- **Refatoração e correção de bugs auditados?** → Consulte `Refactor_Plan.md` (Sprints 6-9).
- **Dúvida de construção do zero?** → Consulte `Manual_OrceIA.md` (blueprint completo).
- **AuditorIA (PDFs)?** → Consulte `Plano_AuditorIA.md`.
- **Regra de código específica?** → Os `GEMINI.md` e `.agents/rules/` são a fonte de verdade ativa.

### Atualizações Arquiteturais Recentes (Auditoria Motor IA)
1. **Pinecone**: Utiliza Lazy Initialization para no derrubar instncias serverless no boot, e agora suporta *Filtro Rígido de Unidades* com Fallback nativo.
2. **Concorrncia**: Semforo assncrono limitado a 3 por worker para evitar Rate Limit 429 da OpenAI durante auto-scaling.
3. **Curva ABC e Tolerância**: Totalmente desconectadas do LLM. O clculo matemático de Tolerância Dimensional (15%) é feito em Python de forma determinística antes da IA atuar.
4. **UX do SSE**: O Redis entrega pacotes de 2 em 2 (no mais 10 em 10) para uma UI fluida.
5. **Dicionário de Canteiro e Estratificação**: Interceptador léxico estático em `vocabulario_obra.py` e Orçamentista Virtual (`reformulador.py`) para expandir queries quando o RRF score é menor que 40%.
6. **Contexto de Hierarquia**: A UI envia o `macro_item_context` nos itens folha, orientando a IA de forma precisa.
7. **Detecção de Lista Plana e Estruturação EAP**: Novo módulo isolado `backend/modules/eap/` usa GPT-4o-mini (Structured Outputs + Positional Indexing) para gerar Macro Itens inteligentemente a partir de uma lista plana, fundindo no Frontend antes de rodar o motor RRF.
