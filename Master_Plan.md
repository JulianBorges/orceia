# Master Plan V3: O Renascimento (Clean Architecture & Enterprise Scale)

**Documento Oficial de Roadmap e Arquitetura de Produto para a V3 do OrceIA**

Este roadmap reflete a decisão arquitetural de abandonarmos a base de código legada (V2) para reerguermos a ferramenta a partir de uma fundação 100% limpa, segura e performática, aplicando as lições do nosso Post-Mortem.

---

> **Atualização de Status (Hardening Concluído):** A "Fase de Estabilização" (Sprints 6 a 9 do Refactor Plan) foi 100% concluída com sucesso. O motor e o frontend atingiram estabilidade e segurança máximas. O caminho está livre e blindado para prosseguirmos com a **Sprint 4.2 (Curva ABC)** e **Sprint 5 (AuditorIA)**.

---

## 🏗️ SPRINT 1: Fundação Limpa e Cherry-Picking de UX (Prioridade Zero)
*Objetivo: Criar um ambiente isolado, conectar aos bancos maduros da V2 e portar estritamente o código visual validado.*

- [x] **1.1 Setup do Novo Repositório:**
  - [x] Inicializar projeto Next.js e FastAPI em pastas novas e limpas (`OrceIA_V3`).
  - [x] Aplicar isolamento de domínio (DDD), criando estruturas como `backend/modules/orcamento`.
  - [x] Copiar o arquivo `.env` da V2 para reaproveitar os bancos Supabase, Pinecone e Redis.

- [x] **1.2 Cherry-Picking da Interface Matemática:**
  - [x] Portar os arquivos `utils/budgetUtils.ts` (lógica de macroitens) e `store/useBudgetStore.ts` (Zustand com flag `isDirty` O(1)). *(Setup base do Zustand recém-criado)*
  - [x] Portar a pasta de componentes `components/BudgetTable` (Virtualização de DOM a 60 FPS) e o `globals.css` intactos.
  - [x] Restabelecimento do módulo `/sinapi` isolado (DDD) no backend para suportar a busca manual (Autocomplete) do usuário.

---

## 🚀 SPRINT 2: Resiliência de Nuvem e Streaming SSE (Infraestrutura)
*Objetivo: Construir o motor de processamento em massa blindado contra travamentos (Timeouts) e Rate Limits da OpenAI.*

- [x] **2.1 O Novo Motor Assíncrono (Proteção Rate Limit):**
  - [x] Criar o controlador de lotes usando `asyncio.Semaphore` e *Exponential Backoff com Jitter* obrigatórios (Evitar Erro 429).
  - [x] Configurar fatiamento de planilhas gigantes em chunks de processamento seguro em background.

- [x] **2.2 Barramento SSE e Segurança Proxy:**
  - [x] Escrever o fluxo de Server-Sent Events (SSE) amparado por Redis Streams (`XADD`/`XREAD`) e controle de `Last-Event-ID` para reconexões resilientes de usuários com internet oscilante.
  - [x] Reestabelecer o `/api/proxy` (Next.js Server-Side) mascarando 100% das chaves (`API_SECRET_KEY`) contra o Client-Side.

- [x] **2.3 Persistência de Planilhas:**
  - [x] Criar Migração SQL (DDL) para instanciar a tabela física `planilhas_linhas` e tabela mãe `planilhas` (Integridade Referencial) no Supabase para suportar o Auto-Save B2B da rota `/save-linhas`.

---

## 🧠 SPRINT 3: Inteligência Determinística e Multi-Agentes (IA Core)
*Objetivo: Reativar os prompts e algoritmos de ponta, substituindo "achismos" de LLM por matemática e schemas estritos.*

- [x] **3.1 Híbrido RRF e Cache Global (Redis):**
  - [x] Recodificar a busca RRF (Pinecone Embeddings + Postgres Trigramas) com boost matemático de consenso de 20%.
  - [x] Substituir o `TTLCache` local por um Cluster de Cache Centralizado no Redis (usando Hash SHA-256 das strings originais) para escala horizontal sem custos repetidos na OpenAI.

- [x] **3.2 Adoção Estrita de Structured Outputs & CoT:**
  - [x] Eliminar parse de Markdown/Regex. Toda comunicação com a OpenAI na V3 deve usar `beta.chat.completions.parse` mapeada diretamente nos schemas do Pydantic (`categoria_rigor`).
  - [x] Incorporar o *Zero-Shot Chain of Thought* (`raciocinio_step_by_step`) como primeiro campo do schema para curar alucinações, limitando o log ao backend para isolar o peso do payload SSE.

---

## 🎯 SPRINT 3.5: Auditoria e Qualidade de Busca (Refatoração Fases 1 e 2)
*Objetivo: Blindar matematicamente a IA, traduzir jargões de canteiro de obras e maximizar a recuperação de itens difíceis (Implementado).*

- [x] **Contexto e Tolerância Matemática:**
  - [x] Injeção de Hierarquia (Macro Item / EAP) no prompt da IA para itens folha, curando desvios de família de serviço.
  - [x] Tolerância dimensional (15%) calculada deterministicamente em Python antes do LLM interagir, impedindo falsos positivos matemáticos na IA.
- [x] **Orçamentista Virtual e Léxico:**
  - [x] Criação de um Dicionário de Canteiro em memória (`vocabulario_obra.py`) para traduzir jargões regionais antes da busca vetorial (ex: "bobcat" -> "minicarregadeira").
  - [x] Fallback Estratificado: Expansão de queries com GPT-4o-mini sempre que a confiança do motor RRF for menor que 40%, multiplicando as rotas de busca de forma inteligente.
  - [x] Filtro rígido (com fallback nativo) no Pinecone para casar a unidade de medida do item da planilha.

- [x] **Lista Plana e Estruturação EAP:**
  - [x] Detecção no Frontend de planilhas 100% planas (sem macro itens) alertando o usuário.
  - [x] Agente de IA EAP Isolado: Utiliza índices posicionais em vez de UUIDs para estruturação inteligente (Structured Outputs) de listas massivas sem estourar limites de tokens da OpenAI.
  - [x] Integração automática: A lista intercalada pela IA alimenta o frontend e engatilha o motor RRF automaticamente logo em seguida.

---

## 📈 SPRINT 4: Inteligência Comercial B2B (Novas Features)
*Objetivo: Evoluir de uma ferramenta interna para um Produto SaaS de alto valor e inteligência adaptativa.*

- [x] **4.1 Aprendizado por Feedback Humano (RLHF Local):**
  - [x] Criar tabela de `memoria_organizacional`. Quando o usuário alterar o insumo escolhido pela IA manualmente no Drawer e salvar, o sistema memorizará a preferência.
  - [x] Nos próximos orçamentos da mesma empresa, o sistema contornará a OpenAI e preencherá o item idêntico a custo zero de API.

- [x] **4.2 Multi-Tenancy (Preparação SaaS):**
  - [x] Implementação de Login Passwordless com segurança via Cookies HTTP-Only, Middleware e Headers `X-Tenant-ID`.
  - [x] Isolamento perimetral do tráfego SSE via Redis Streams (`stream:{tenant_id}:planilha:{id_planilha}`) e injeção de dependência estrita (`Depends(get_current_tenant)`) no FastAPI.

- [x] **4.3 Gestão de Orçamentos Salvos (CRUD):**
  - [x] Rotas `GET /orcamento/planilhas` e `GET /orcamento/planilhas/{id}/linhas` implementadas em `services.py` + `routes.py`.
  - [x] Modal `SavedBudgetsModal.tsx` implementado com listagem, loading state e recuperação de planilha completa.
  - [x] Mapeamento correto inclui `descricao_legada`, `is_macro_item` baseado em unidade (não em preço) e `base` condicional.
  - [x] Queries SQL usam `CAST(id AS TEXT)` para evitar incompatibilidade asyncpg → Pydantic v2.
  - [x] `planilhaId` e `memorialId` persistidos no Zustand `persist` para sobreviver ao refresh de página.

---

## 🔮 SPRINT 5: Pipeline Bidirecional de Memoriais Descritivos (AuditorIA) — CONCLUÍDA

- [x] **5.1 Ingestão de Memoriais (PDF):**
  - [x] `backend/modules/auditoria/services.py`: pipeline PDF → pypdf → chunking semântico por parágrafo → embeddings (`text-embedding-3-small`) → Pinecone em lote.
  - [x] Namespace isolado por tenant e projeto: `memorial:{tenant_id}:{projeto_id}`.
  - [x] Endpoint `POST /auditoria/ingerir-memorial` (multipart/form-data) com validação de PDF e geração automática de `projeto_id`.
  - [x] Endpoint `GET /auditoria/status/{projeto_id}` consulta `describe_index_stats()` do Pinecone.
  - [x] `MemorialUploadButton.tsx`: estados idle/uploading/success/error com feedback visual de chunks gerados.

- [x] **5.2 Modo Geração (Memorial como guia de especificações):**
  - [x] `processarOrcamentoIA()` no Zustand envia `projeto_id: memorialId` no payload de cada linha.
  - [x] Em `orcamento/services.py`: se `projeto_id` presente, chama `buscar_contexto_memorial()` e injeta o trecho relevante no prompt do Agente Engenheiro como `[Especificação do Memorial Descritivo]`.
  - [x] Fallback silencioso: se memorial sem trecho relevante (score < 0.65), fluxo continua normalmente sem erro.

- [x] **5.3 Modo Auditoria (Conformidade linha a linha):**
  - [x] `backend/modules/auditoria/ai_agent.py`: Agente Auditor com schema `ResultadoConformidade` (CONFORME/DIVERGENTE/SEM_REFERENCIA) via Structured Outputs.
  - [x] Endpoint `POST /auditoria/auditar-planilha` (SSE): semáforo `asyncio.Semaphore(5)` protege rate limit. Tasks criadas em paralelo, resultados entregues via SSE conforme concluídas.
  - [x] `auditarPlanilha()` no Zustand: consome SSE via `fetchEventSource`, mapeia status de conformidade para `AIStatus` e atualiza cada linha em tempo real.
  - [x] `AuditorButton.tsx`: aparece condicionalmente quando `memorialId` existe; desativado durante processamento.
