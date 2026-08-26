# Plano Abrangente: OrceIA V3 — Blindagem Completa

Baseado na análise técnica de toda a conversa e da estrutura real do código, este plano cobre as **4 dimensões de risco e melhoria** identificadas. Cada fase é independente e pode ser executada separadamente.

---

## Dimensão 1 — Regras de IA Nativas (`.agents/rules/`)
**Prioridade: Alta | Esforço: ~1h | Executar: Aprovar este plano**

Transformar as diretrizes estáticas dos manuais em regras injetadas automaticamente pela IDE antes de cada prompt.

> [!IMPORTANT]
> Esta é a única dimensão que exige **apenas a sua aprovação** para eu executar imediatamente. As demais requerem decisões arquiteturais suas.

### O que será criado

#### [NEW] [GEMINI.md](file:///c:/Users/Julian/orceia_v3/.agents/rules/GEMINI.md) — Raiz do workspace
Regras universais que toda IA deve obedecer independente do contexto: KISS, sem alucinações de função, IDs como `VARCHAR(255)`, Post-Mortem resumido dos 11 bugs conhecidos. Lida automaticamente por qualquer agente no projeto.

#### [NEW] [01_core_architecture.md](file:///c:/Users/Julian/orceia_v3/.agents/rules/01_core_architecture.md)
Pilares invioláveis: DDD (módulos isolados), nenhuma feature nova dentro de `modules/orcamento/`, fluxo SSE via Redis Streams, Multi-Tenancy via `X-Tenant-ID`.

#### [NEW] [02_frontend.md](file:///c:/Users/Julian/orceia_v3/.agents/rules/02_frontend.md)
Regras específicas do Next.js: proibição de React Context, uso obrigatório de mutações cirúrgicas no Zustand (`addRow`, `deleteRow`, `updateRow`), `createPortal` para dropdowns em ambientes virtualizados, autosave **somente** em `/save-linhas` (jamais `/upsert-linhas`), `BACKEND_API_URL` sem prefixo `NEXT_PUBLIC_`.

#### [NEW] [03_backend.md](file:///c:/Users/Julian/orceia_v3/.agents/rules/03_backend.md)
Regras do FastAPI: `asyncio.Semaphore(25)` obrigatório, `statement_cache_size=0` no `asyncpg`, `return_exceptions=True` em `gather()`, `raciocinio_step_by_step` nunca persiste no Supabase nem no payload SSE, chave Redis sempre namespaced por tenant.

#### [NEW] [frontend/.cursorrules](file:///c:/Users/Julian/orceia_v3/frontend/.cursorrules) *(Opcional)*
Espelho condensado do `02_frontend.md` para compatibilidade com Cursor IDE.

#### [NEW] [backend/.cursorrules](file:///c:/Users/Julian/orceia_v3/backend/.cursorrules) *(Opcional)*
Espelho condensado do `03_backend.md` para compatibilidade com Cursor IDE.

---

## Dimensão 2 — Blindagem de Escala (Supabase + Sprint 4.2)
**Prioridade: Média | Esforço: ~1 dia | Executar: Quando iniciar Sprint 4.2**

Endereça os dois riscos arquiteturais silenciosos identificados na análise.

> [!WARNING]
> **Não iniciar a Sprint 4.2 (Curva ABC) sem antes executar esta dimensão.** A feature de "revisão por agentes com tokens extras" pode ultrapassar o `Semaphore(25)` e causar cascata de erros 429.

### 2.1 — Documentar o Teto do Supabase (Observabilidade)
Adicionar no `Master_Plan.md` e no `AI_Onboarding.md` um item explícito de risco:

> *"A busca Trigrama no Supabase suporta bem até ~50 tenants simultâneos. Acima disso, avaliar migração da busca lexical para ElasticSearch/OpenSearch ou ativar Read Replicas no Supabase."*

**Onde executar:** Editar `Master_Plan.md` e `AI_Onboarding.md` diretamente.

### 2.2 — Guardrail para Sprint 4.2 (Curva ABC)

#### [MODIFY] [services.py](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py)
Antes de implementar a Curva ABC, o `Semaphore` existente deve ser **compartilhado** entre o processamento regular e os agentes revisores de Itens Classe A. Os dois fluxos não podem ter semáforos independentes (isso dobraria o número de conexões simultâneas à OpenAI).

**Onde executar:** Eu implemento junto com a Sprint 4.2, quando aprovada.

---

## Dimensão 3 — Cobertura de Testes (Regressão Zero)
**Prioridade: Média-Alta | Esforço: ~2 dias | Executar: Antes da Sprint 5**

> [!IMPORTANT]
> **Este é o risco mais subestimado do projeto.** Sem testes, a implementação da AuditorIA (Sprint 5) pode quebrar silenciosamente o motor RRF existente sem que nenhum alerta seja disparado.

### 3.1 — Testes de Contrato do Backend (PyTest)
Garantem que as rotas do `modules/orcamento/` continuam respondendo com o schema correto após qualquer refatoração.

#### [NEW] [backend/tests/](file:///c:/Users/Julian/orceia_v3/backend/tests/) — Pasta de testes
#### [NEW] [test_rrf_engine.py](file:///c:/Users/Julian/orceia_v3/backend/tests/test_rrf_engine.py)
Testa a função de fusão RRF com listas mockadas (sem chamar Pinecone/Supabase). Valida: ordenação correta, boost de 20% de consenso, desempate por score.

#### [NEW] [test_orcamento_routes.py](file:///c:/Users/Julian/orceia_v3/backend/tests/test_orcamento_routes.py)
Testa as rotas `/save-linhas` e `/upsert-linhas` com um cliente HTTP de teste (`httpx.AsyncClient`). Valida que `/save-linhas` **nunca** aciona a OpenAI.

**Como executar:**
```powershell
# Na pasta backend/
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

### 3.2 — Testes de Unidade do Frontend (Vitest + Testing Library)
Garantem que as mutações O(1) do Zustand continuam funcionando após qualquer alteração na store.

#### [NEW] [frontend/tests/](file:///c:/Users/Julian/orceia_v3/frontend/tests/) — Pasta de testes
#### [NEW] [useBudgetStore.test.ts](file:///c:/Users/Julian/orceia_v3/frontend/tests/useBudgetStore.test.ts)
Testa: `addRow` não suja linhas não-relacionadas, `deleteRow` remove da fila `dirtyRowIds` apenas o ID confirmado, `isDirty` volta a `false` após confirmação HTTP 200.

**Como executar:**
```powershell
# Na pasta frontend/
npm install -D vitest @testing-library/react @testing-library/jest-dom
npx vitest run
```

---

## Dimensão 4 — AuditorIA: Fundação para Sprint 5
**Prioridade: Baixa (futura) | Esforço: ~1 semana | Executar: Após Dimensões 1, 2 e 3**

Cria a estrutura de pastas isolada (DDD) para a feature de análise de PDFs **sem tocar** no `modules/orcamento/`.

### 4.1 — Isolamento de Módulo (Backend)

#### [NEW] [backend/modules/auditoria/](file:///c:/Users/Julian/orceia_v3/backend/modules/auditoria/)
```
auditoria/
├── __init__.py
├── routes.py          # POST /auditoria/upload-pdf, GET /auditoria/stream/{id}
├── schemas.py         # AuditoriaItem, DivergenciaSchema (Pydantic)
├── ingestao_service.py # LlamaParse / GPT-4o Vision → Pinecone namespace dinâmico
└── agente_auditor.py  # Structured Outputs para cruzar linha da planilha vs PDF
```

### 4.2 — Isolamento de Feature (Frontend)

#### [NEW] [frontend/src/features/](file:///c:/Users/Julian/orceia_v3/frontend/src/features/)
```
features/
├── budget-copilot/    # Mover BudgetTable, store, hooks para cá (sem quebrar imports)
└── document-auditor/  # Nova view Split-Screen (PDF + Planilha)
    ├── useAuditStore.ts
    ├── PdfViewer.tsx
    └── AuditResultsPanel.tsx
```

> [!NOTE]
> A migração do `budget-copilot` para `features/` é **opcional e cosmética** na V3. Obrigatória apenas se a AuditorIA for ao ar, para evitar acoplamento de stores.

---

## Ordem de Execução Recomendada

```
Hoje          →  Dimensão 1 (Regras IA)         ~1h    ← Aprovar agora
Próxima semana →  Dimensão 3 (Testes)            ~2d    ← Antes de qualquer nova feature
Antes Sprint 4.2 → Dimensão 2 (Escala/Guardrail) ~1d
Sprint 5       →  Dimensão 4 (AuditorIA)         ~1sem
```

## Verificação Final

Após Dimensão 1, o critério de sucesso é simples: abra um novo chat e me peça para "alterar algo no frontend". Eu devo automaticamente mencionar as restrições do Zustand e do autosave **sem que você precise me pedir para ler o manual**.
