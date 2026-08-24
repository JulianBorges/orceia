# Master Plan V3: O Renascimento (Clean Architecture & Enterprise Scale)

**Documento Oficial de Roadmap e Arquitetura de Produto para a V3 do OrceIA**

Este roadmap reflete a decisão arquitetural de abandonarmos a base de código legada (V2) para reerguermos a ferramenta a partir de uma fundação 100% limpa, segura e performática, aplicando as lições do nosso Post-Mortem.

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

- [ ] **2.3 Persistência de Planilhas:**
  - [ ] Criar Migração SQL (DDL) para instanciar a tabela física `planilhas_linhas` no Supabase para suportar o Auto-Save B2B da rota `/save-linhas`.

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

## 📈 SPRINT 4: Inteligência Comercial B2B (Novas Features)
*Objetivo: Evoluir de uma ferramenta interna para um Produto SaaS de alto valor e inteligência adaptativa.*

- [x] **4.1 Aprendizado por Feedback Humano (RLHF Local):**
  - [x] Criar tabela de `memoria_organizacional`. Quando o usuário alterar o insumo escolhido pela IA manualmente no Drawer e salvar, o sistema memorizará a preferência.
  - [x] Nos próximos orçamentos da mesma empresa, o sistema contornará a OpenAI e preencherá o item idêntico a custo zero de API.

- [ ] **4.2 Foco na Curva ABC Preditiva:**
  - [ ] O Backend deve calcular a Curva ABC *antes* da IA terminar. Agentes revisarão com tokens extras os "Itens Classe A" (os 20% que custam 80% da obra), gerando alertas de risco vermelhos no Dashboard.

- [x] **4.3 Multi-Tenancy (Preparação SaaS):**
  - [x] Implementação de Login Passwordless com segurança via Cookies HTTP-Only, Middleware e Headers `X-Tenant-ID`.
  - [x] Isolamento perimetral do tráfego SSE via Redis Streams (`stream:{tenant_id}:planilha:{id_planilha}`) e injeção de dependência estrita (`Depends(get_current_tenant)`) no FastAPI.

---

## 🔮 SPRINT 5: Multimodalidade e Auditoria Documental (AuditorIA)
*Objetivo: Cruzar planilhas financeiras com cadernos de encargos e memoriais descritivos em PDF.*

- [ ] **5.1 Ingestão Multimodal:**
  - [ ] Pipeline para leitura de PDFs com LlamaParse ou Claude 3.5 Sonnet Vision em `backend/modules/auditoria/`.
  
- [ ] **5.2 Agente Inspetor de Conformidade:**
  - [ ] IA capaz de validar se o item de excel reflete exatamente as exigências do Caderno de Encargos em PDF, identificando downgrades de material com citação de página exata.
