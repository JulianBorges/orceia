# OrceIA - Guia de Contexto para Inteligência Artificial (System Prompt)

> **Instrução para a IA:** Se você está lendo este arquivo no início de um chat, use-o como base absoluta de contexto arquitetural antes de propor qualquer código ou refatoração.

## 1. Visão Geral do Projeto
O **OrceIA** é um Copiloto de Orçamento de Engenharia de alta performance. Ele recebe planilhas massivas (5.000+ linhas) do usuário, normaliza os dados, cruza com bancos oficiais (SINAPI) via Busca Semântica Híbrida e devolve o orçamento preenchido em tempo real.

## 2. Stack Tecnológica
- **Frontend:** Next.js (React), Tailwind CSS, Zustand (Gerenciamento de Estado Reativo).
- **Backend:** FastAPI (Python, 100% Assíncrono com `asyncio`).
- **Banco de Dados (Relacional):** Supabase (PostgreSQL) para persistência de orçamentos.
- **Banco de Dados (Vetorial):** Pinecone (Busca semântica e armazenamento em cache O(1)).
- **Mensageria / Tempo Real:** Redis Streams (`XADD`/`XREAD`) servindo dados via Server-Sent Events (SSE).
- **IA:** OpenAI API (Embeddings + Structured Outputs).

## 3. Pilares Arquiteturais Críticos (NÃO QUEBRE)

### 3.1. Performance do Frontend (60 FPS) e Segurança (Middleware)
A tabela principal (`BudgetTable.tsx`) renderiza milhares de linhas. Para isso, ela utiliza:
- **DOM Virtualization** (`@tanstack/react-virtual`): Apenas os itens na tela (viewport) existem no DOM. Alterações de CSS devem respeitar `transform: translateY` e `position: absolute`.
- **Debounced Auto-Save O(1):** O hook `useAutoSave.ts` utiliza uma flag booleana super-rápida (`isDirty`) acoplada ao Zustand, eliminando a lentidão do `JSON.stringify`. Ele faz um debounce nativo e atinge a rota `/save-linhas` (que é apenas persistência). JAMAIS direcione o autosave para `/upsert-linhas` (isso reativaria a IA acidentalmente).
- **Segurança Multi-Tenant:** O Next.js possui um `middleware.ts` na raiz do `src/` que intercepta requisições, verifica o Cookie de Sessão e injeta o header `X-Tenant-ID`. Nunca trafegue IDs de tenant abertos em payloads JSON no Frontend. O backend FastAPI (via `get_current_tenant`) extrai o `X-Tenant-ID` verificado pelo Next.js Proxy para isolar RLS no banco e SSE.

### 3.2. Infraestrutura Backend e SSE Resiliente
O ambiente de hospedagem (Vercel / Cloud Run) impõe timeouts rigorosos (ex: 60 segundos). O backend burla essa limitação através de uma arquitetura tolerante a falhas:
- **Processamento em Chunks:** Lotes do Excel são processados de 50 em 50 para evitar thundering herd.
- **Redis Streams (XADD):** Os resultados da IA são gravados na memória do Redis com um TTL de 1 hora.
- **Recuperação de SSE (XREAD):** O endpoint SSE (`routes.py`) lê o cabeçalho `Last-Event-ID`. Se a nuvem cortar a conexão, o navegador reconecta passando o último ID e o backend despeja os pacotes perdidos instantaneamente.
- **Proxy Next.js (Segurança):** Toda comunicação do frontend com a API de IA ou backend (POSTs e SSE) passa obrigatoriamente por uma rota server-side do Next.js (`/api/proxy`). Isso mascara as chaves de API (`x-api-key`) mantendo-as 100% invisíveis no lado do cliente (impedindo vazamentos no F12). A variável de ambiente com a URL do backend **DEVE** ser `BACKEND_API_URL` (sem o prefixo `NEXT_PUBLIC_` para encapsulamento, e **estritamente a URL base**, sem `/api` ou barras finais, para que o roteamento dinâmico do proxy funcione).
- **Google Cloud Build (Monorepo):** Ao configurar o CI/CD no Cloud Run, o "Build context directory" deve apontar explicitamente para a pasta `/backend/` para que o Dockerfile seja encontrado corretamente.
- **Configuração Crítica Cloud Run:** O serviço DEVE obrigatoriamente rodar com a CPU sempre ligada (`--no-cpu-throttling`). No painel atual do GCP, isso corresponde à opção de Faturamento **"Com base em instâncias"** (CPU sempre alocada). Se o estrangulamento ("Baseada em solicitações") estiver ativo, o Cloud Run congelará o container prematuramente e matará a entrega dos dados massivos via SSE.
- **Supabase Connection Pooling (asyncpg):** Para evitar que o auto-scaling do Cloud Run esgote as conexões do Postgres (Erro: *Too Many Clients*), a variável `SUPABASE_DATABASE_URL` deve SEMPRE utilizar o Transaction Pooler (porta `6543`), nunca a conexão direta (5432). **Obrigatório:** O pooler do `asyncpg` deve ser inicializado com `statement_cache_size=0`, caso contrário, o PgBouncer em modo transação falhará com erro de "prepared statement does not exist".
- **Trava de Cache Seguro:** O cache Semântico do Redis (que memoriza o veredito da IA) valida sempre se o `codigo_selecionado` retornado no cache passado ainda existe no Dossiê (Top 5) devolvido pelo Pinecone na rodada atual. Se não existir, o cache é invalidado. Isso previne "alucinações temporais" de IDs de orçamento antigos.
- **Concorrência Estrangulada (Proteção Rate Limit):** O processamento assíncrono em lote DEVE obrigatoriamente usar `asyncio.Semaphore` combinado com blocos de retentativa (Exponential Backoff com Jitter), conforme implementado em `upload_service.py`. É ESTRITAMENTE PROIBIDO realizar milhares de requisições de IA soltas com `asyncio.gather`, sob o risco de Timeout no Cloud Run e suspensão da conta da OpenAI (Erro 429).

### 3.3. Motor de Busca (Algoritmo RRF)
A IA não "chuta" preços. O processo no `ai_service.py` funciona assim:
1. **RRF (Reciprocal Rank Fusion):** O backend realiza uma busca lexical ultrarrápida (PostgreSQL via Trigramas) e uma vetorial (Pinecone). As posições são fundidas matematicamente para criar um Ranking final perfeito.
2. **Isolamento por Namespaces:** A segregação de Insumos e Composições é garantida via infraestrutura através dos Namespaces do Pinecone (`composicoes_sinapi` e `insumos_sinapi`).
3. O Top 10 vai para o LLM da OpenAI, que atua através de **Structured Outputs** (JSON Schema rigoroso). O modelo aplica obrigatoriamente **Zero-Shot Chain of Thought (Schema Engineering)**, sendo forçado a gerar seu raciocínio lógico no campo `raciocinio_step_by_step` *antes* de tentar eleger a melhor opção, erradicando alucinações cognitivas e classificando o peso da decisão na `categoria_rigor`.
4. **Custo Zero em Detalhes:** A "Memória de Cálculo" com os scores de similaridade já é empacotada durante o RAG inicial de Upload (SSE) e salva no `Zustand`. O clique em uma composição para ver seus detalhes apenas lê da memória do navegador, sem engatilhar nenhuma nova requisição para o backend ou para a OpenAI.

## 4. Como Navegar no Código
- O plano de voo e as prioridades oficiais de desenvolvimento sempre estarão no arquivo raiz **`Master_Plan.md`**.
- Sempre confira o `Master_Plan.md` antes de propor criação de novas features.

## 5. Regras de Código (Guidelines)
- **KISS (Keep It Simple, Stupid):** Prefira funções nativas do React/Python antes de instalar novas dependências (ex: usamos `setTimeout` em vez de `use-debounce`).
- **No Hallucinations / Semantic Naming:** Nunca invente funções. Além disso, evite limpar formatação da IA via Regex no pós-processamento. Confie no Semantic Naming (ex: renomear variáveis como `justificativa` para `parecer_tecnico` no Pydantic) e num System Prompt claro para induzir o formato nativo da LLM, economizando latência e recursos.
- **Tratamento Cauteloso de Exceções:** Tasks assíncronas do backend (como `gather`) devem usar `return_exceptions=True` para não quebrarem o Event Loop e interromperem o fluxo de SSE do usuário caso a API da OpenAI caia.
- **Pragmatismo no TypeScript (Vercel):** Para viabilizar a transição da V2, a compilação tolera erros de tipagem (`any`). O foco é MVP. **Exceção de Ouro:** Para injetar dependências complexas (como métodos na `TableMeta` do TanStack Table), prefira *Module Augmentation* (`declare module`) no topo do arquivo ao invés de usar `(info... as any)`. Isso mantém o IntelliSense intacto.
- **Mutações O(1) e Auto-Save (Zustand):** Componentes de UI **jamais** devem sobrescrever a tabela inteira (`setTableData`) para fazer exclusões, adições ou indentações, pois isso suja 100% da tabela e derruba o banco no Auto-Save. Use sempre mutations cirúrgicas (`addRow`, `deleteRow`, `updateRow`). Dentro da Store, ao usar `recalculateNumbers`, sempre faça *Shallow Compare* entre a array antiga e a nova para capturar 100% dos IDs alterados (inclusive pais afetados) e adicioná-los cirurgicamente no `dirtyRowIds`.
- **Portals em Virtualização (TanStack Virtual):** O container do `@tanstack/react-virtual` exige ocultar conteúdo excedente. Nunca renderize componentes flutuantes (como Dropdowns de Autocomplete) diretamente no fluxo da célula. Envolva-os sempre com `createPortal(..., document.body)` para flutuarem por cima da tabela sem serem cortados. E Modais pesados (como Memória de IA) devem sempre ser componentes isolados fora do motor de renderização da tabela.
- **Função acima da Forma (Anti-Gambiarras Visuais):** Jamais sacrifique a performance da aplicação (60 FPS) para adicionar efeitos visuais desnecessários (animações de entrada lentas, efeitos dominó ou renderizações em cascata). A UI deve ser utilitária, instantânea e suportar 5.000+ itens sem engasgos.
- **Matemática Offline:** Todo e qualquer recálculo de preço, BDI ou quantidades dentro de uma composição (Modal de Edição) deve rodar 100% no cliente via Zustand. Não crie endpoints no backend para somar ou multiplicar valores de interface.
- **Tipagem de IDs (Banco de Dados vs Frontend):** O Frontend utiliza strings pseudo-randômicas (ex: `macro_12345`, `serv_67890`) para as chaves primárias. Portanto, **nunca** crie colunas de `id` como `UUID` nas tabelas do Postgres. Use sempre `VARCHAR(255)` para preservar a compatibilidade retroativa e evitar crash fatal de Type Mismatch no `asyncpg`.
- **Race Conditions em Filas Assíncronas (Zustand):** Ao gerenciar filas de envio em background (como o Auto-Save com `dirtyRowIds`), **nunca limpe a fila inteira de forma cega** após o envio (`set({ fila: [] })`). Filtre sempre cirurgicamente apenas os IDs que o backend confirmou via HTTP 200 OK. Isso preserva as edições que o usuário continuou fazendo na interface enquanto o request original viajava pela rede.
- **Atue como Tech Lead Sênior:** Ao analisar um problema, não me entregue apenas o código. Explique brevemente o gargalo arquitetural, os riscos da sua abordagem e garanta que a solução proposta escala para ambientes governamentais massivos.