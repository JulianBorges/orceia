# Manual Definitivo de Construção: OrceIA (Do Zero à Produção)

> **Instrução para a IA Leitora:** Este documento é o blueprint (planta baixa) arquitetural do OrceIA. Se você recebeu a missão de recriar, manter ou escalar esta aplicação, siga estritamente as fases abaixo. Não utilize "jeitinhos", não invente bibliotecas desnecessárias e priorize a performance e o isolamento (Feature-Sliced Design) em todas as camadas.

## 0. Stack Tecnológica Obrigatória
- **Frontend:** Next.js (React), Tailwind CSS, Zustand, `@tanstack/react-virtual`.
- **Backend:** FastAPI (Python), `asyncio`, `asyncpg`, `pydantic`.
- **Infraestrutura/Dados:** Supabase (PostgreSQL para dados relacionais e trigramas), Pinecone (Busca Vetorial), Redis (Cache Global e Mensageria), Docker.
- **Inteligência:** OpenAI API (modelos `gpt-4o-mini` para processamento rápido estruturado e `text-embedding-3-small` para vetores).

---

## Fase 1: Setup de Banco de Dados e Cache Estratégico

### 1.1 Supabase (PostgreSQL)
Você precisa de uma tabela principal (`sinapi_composicoes`) e uma secundária (`sinapi_insumos`).
**Obrigatório:** Ativar a extensão `pg_trgm` no PostgreSQL. A busca lexical rápida não deve usar indexação comum (LIKE), mas sim métricas de similaridade de texto (`word_similarity()`), tolerando erros de ortografia do legado.

### 1.2 Pinecone (Banco Vetorial)
**Obrigatório:** O índice deve ter dimensão `1536` e métrica `cosine`.
*   **Namespaces:** Nunca misture dados. Os embeddings de composições (`composicoes_sinapi`) devem viver em namespaces separados dos insumos (`insumos_sinapi`). Em futuras features (como PDFs de projetos), crie namespaces dinâmicos (ex: `projeto_123`).
*   **Metadados Ricos:** Guarde o `preço`, a `unidade` e o `json` bruto nos metadados do Pinecone. O Frontend usará isso para não precisar fazer requisições extras ao consultar detalhes.

### 1.3 Redis (Cache e Mensageria)
*   **Cache SHA-256:** Crie uma função que faça um Hash criptográfico do termo pesquisado e armazene a resposta da IA com TTL de 15 dias. Isso reduz em mais de 70% o custo da OpenAI, já que itens padrão da engenharia se repetem constantemente em várias planilhas.

---

## Fase 2: O Motor Híbrido RAG (Backend Core)

A Inteligência Artificial NÃO "chuta" preços no OrceIA. Ela atua através do algoritmo **Reciprocal Rank Fusion (RRF)**.

1.  **Busca Paralela:** Ao receber um termo, dispare duas buscas assíncronas usando `asyncio.gather`. Uma para o Supabase (Trigramas) e outra para o Pinecone (Embeddings).
2.  **O Algoritmo RRF:** Funda as duas listas usando a fórmula matemática `1 / (k + rank + 1)`.
3.  **Boost de Consenso:** Se a busca Lexical E a Semântica encontrarem o mesmo ID, adicione um bônus de 20% no "Score" matemático. Retorne apenas as Top 10 opções perfeitamente ordenadas.

---

## Fase 3: Inteligência e Agentes (Structured Outputs)

É terminantemente proibido jogar todo o contexto em um único prompt. Use a abordagem **Multi-Agentes**.
*   O fluxo DEVE utilizar a função nativa `beta.chat.completions.parse` da OpenAI mapeada para schemas rigorosos do `Pydantic` (ex: `AnaliseItem`, `LoteCorrigido`). Isso extirpa a necessidade de limpezas sujas via Regex.
*   **Agente Corretor:** Limpa a string original suja. Remove dimensões (ex: "100mm") da string core antes de enviar ao Pinecone (pois bancos vetoriais são ruins com números), mas as salva em uma chave `caracteristicas_extras` para análise lógica posterior.
*   **Agente Mapeador:** Recebe o Top 10 do RRF. Segue a "Matriz de Rigor Dinâmico" (Rigor ALTO para elétrica/hidráulica, BAIXO para itens provisórios). Possui tolerância dimensional de limite de 15%.
*   **Agente Engenheiro e Revisor:** Trabalham em cascata na geração de Composições. O Engenheiro cria a estrutura, e o Revisor audita cada casa decimal das multiplicações.

---

## Fase 4: Resiliência Assíncrona e Fluxo Contínuo (SSE)

Para sobreviver a planilhas de 5.000 linhas em nuvens com Timeout (ex: Vercel):
1.  **Semáforos (Rate Limiting):** Abrace todo o processamento de OpenAI com um `asyncio.Semaphore(25)`. Acompanhe com *Exponential Backoff e Jitter* para caso a OpenAI retorne erro `429 (Too Many Requests)`. Nunca derrube a requisição inteira.
2.  **Fatiamento (Chunks):** O backend fatia as linhas em lotes menores e envia uma por uma para background tasks (`asyncio.create_task`).
3.  **SSE Blindado:** As atualizações são enviadas em tempo real ao front via Server-Sent Events (SSE). Use **Redis Streams** (`XADD` e `XREAD`) como barramento de memória. Monitore o cabeçalho `Last-Event-ID`; se o navegador do usuário perder o sinal de internet, ele reconectará e o Redis deverá injetar apenas os pacotes perdidos.

---

## Fase 5: O Frontend de Fricção Zero (Next.js)

O FrontEnd B2B precisa ter a velocidade utilitária de um software de Desktop.
1.  **Segurança (O Proxy Invasivo):** O navegador nunca fala com o Backend. O fluxo é `Client (React) -> /api/proxy (Next.js Server-Side) -> Backend (FastAPI)`. A chave `API_SECRET_KEY` é secretamente inserida nos headers na rota do proxy do Next.js.
2.  **A Morte dos Renders em Cascata (Zustand):** NUNCA use `React Context`. Centralize o estado da planilha no Zustand. 
3.  **Auto-Save Inteligente O(1):** Crie um *Dirty Checking*. Ao alterar uma linha, adicione o ID dela a um Array `dirtyRowIds`. Um hook *debounced* monitora a flag genérica `isDirty`. Não faça parse e não compare JSON gigantes. O Auto-Save deve apontar obrigatoriamente para a rota estrutural `/save-linhas` (Persistência B2B), e NUNCA para `/upsert-linhas` (que é o gatilho exclusivo da Inteligência OpenAI).
4.  **DOM Virtual (`@tanstack/react-virtual`):** Em uma tabela infinita, renderize estritamente o que está visível no *viewport* (Viewport Virtualization). Use bibliotecas como `@dnd-kit` para ordenação inteligente vinculada à virtualização.
5.  **Memória de Cálculo Empacotada (UX/UI):** Ao receber uma resposta da IA via SSE, o pacote JSON já deve conter as 5 opções do RRF e o status técnico. Quando o usuário clica na linha, um *Drawer Lateral* exibe isso estaticamente, garantindo tempo de resposta de 0ms (Zero requisições extras de rede).

---

## Fase 6: Deploy e Imutabilidade (Infraestrutura)
*   **Docker Obrigatório:** O Backend Python e todas as suas dependências (Numpy, Pandas, FastAPI) devem viver dentro de um `Dockerfile`. Isso extirpa o problema de versões que quebram ao alternar entre macOS/Windows para Linux (Google Cloud).
*   **Isolamento de Domínio (DDD):** Ao escalar para ler PDFs e novas lógicas multimodais, os módulos devem viver em pastas como `backend/modules/orcamento/` e `backend/modules/auditoria/`. Eles não compartilham pastas de rotas sem que haja uma interface clara de fronteira. Nenhuma nova dependência de processamento visual deve quebrar o core do motor de orçamento (Regressão Zero).

---

## Anexo A: Post-Mortem e Lições Aprendidas (Histórico de Bugs)
Durante a construção iterativa da V1 e V2, enfrentamos problemas arquiteturais clássicos. Se você é uma IA recriando este sistema, preste atenção aos erros documentados abaixo para não repeti-los:

1. **Bug dos "Campos Vazios (None, N/A)" na Resposta da IA:**
   - **Sintoma:** A IA retornava campos de justificativa vazios ou ignorava o mapeamento de itens complexos.
   - **Causa:** Fadiga de contexto no prompt e ausência de tipagem estrita para forçar um raciocínio lógico.
   - **Solução Definitiva:** Implementação da **Matriz de Rigor Dinâmico** no Pydantic (`categoria_rigor: Literal["BAIXO", "ALTO"]`). A IA foi obrigada (via schema) a classificar a rigidez do item *antes* de tentar mapeá-lo (ativando *Chain of Thought* condicional), o que eliminou os vazios.

2. **Bug da Injeção de Texto (Ex: "Incompatibilidade técnica:..."):**
   - **Sintoma:** A IA injetava preâmbulos não solicitados no início das justificativas que quebravam a legibilidade no frontend.
   - **Causa:** Tentativa de controlar o formato de saída apenas com pedidos no System Prompt (ex: "Não use preâmbulos").
   - **Solução Definitiva:** Adoção estrita de `beta.chat.completions.parse` e tipagem do retorno. A LLM foi restringida a preencher uma chave estrita, proibindo respostas conversacionais.

3. **Timeouts na Vercel e SSE Quebrado:**
   - **Sintoma:** O deploy travava, ou planilhas com mais de 300 linhas paravam em "processando" infinitamente. A Vercel pedia "upgrade de conta" devido ao tempo de execução.
   - **Causa:** O Serverless da Vercel corta funções demoradas em 10-60 segundos. O Event Loop do Python também estava sendo bloqueado por milhares de requisições soltas.
   - **Solução Definitiva:** Migração do Backend para o **Google Cloud Run** via Docker, onde containers são persistentes. Implementação de *Semáforos de Concorrência*, *Exponential Backoff* e Redis Streams (`XREAD`/`XADD`) para garantir a entrega resiliente dos eventos SSE.

4. **Código Espaguete de Commits (Remendos sobre Remendos):**
   - **Sintoma:** O histórico de Git virou uma confusão de merges e a ferramenta ficou instável após múltiplos agentes tentarem consertar problemas em cima de resquícios de código legado.
   - **Causa:** A IA sofre alucinação quando tenta fazer cirurgias pontuais em arquivos de estado distribuído (Zustand + SSE) contendo variáveis antigas.
   - **Solução Definitiva:** Ao atingir alta complexidade técnica com código 100% gerado por IA, não faça *hotfixes* em arquivos acoplados. Congele o repositório legado e levante uma **V3 Limpa do Zero** baseada estritamente na arquitetura deste manual.

5. **Bug do Auto-Save Acionando IA (Conflito de Gatilhos):**
   - **Sintoma:** Ao alterar um código manualmente na tabela, o Auto-Save salvava o item, mas em seguida a IA rodava de novo e sobrescrevia a escolha humana (além de falsamente reportar erro na memória RLHF).
   - **Causa:** O Frontend atirava para o endpoint `/upsert-linhas` (que delegava para a OpenAI) em vez de uma rota passiva de Banco de Dados.
   - **Solução Definitiva:** Desacoplamento de Rotas. O Backend passou a ter o `/save-linhas` (Stub de DB B2B) exclusivo para salvar, garantindo que `/upsert-linhas` só é disparado explicitamente ao iniciar a Inteligência.

6. **Falha de Encoding do PowerShell (Next.js SWC Crash):**
   - **Sintoma:** `next dev` parava de compilar relatando *Error: stream did not contain valid UTF-8* no arquivo `middleware.ts`.
   - **Causa:** O uso do utilitário `Set-Content` do Windows PowerShell para gerar arquivos TypeScript, o qual adicionava codificação ANSI ou UTF-16LE, incompatível com o SWC (Rust) do Next.js.
   - **Solução Definitiva:** Deleção do arquivo e regravação usando a ferramenta interna (`write_to_file`) em UTF-8 puro, sem comandos Shell intermediários.

7. **Vazamento B2B e Espionagem SSE (Brecha de Segurança):**
   - **Sintoma:** Qualquer pessoa sabendo o ID da planilha poderia engatar no EventSource `/stream/123` e escutar a IA processando orçamentos alheios.
   - **Causa:** A chave de barramento do Redis Streams era pública por planilha (`stream:planilha:{id}`).
   - **Solução Definitiva (Multi-Tenancy SaaS):** Implementação de **Middleware Next.js**. Um *Cookie HttpOnly* valida a sessão, o Next.js injeta um *Header Seguro* `X-Tenant-ID`, e o FastAPI altera a chave do barramento para `stream:{tenant_id}:planilha:{id}`, fechando a interceptação hermeticamente.

8. **Armadilhas Clássicas de Deploy (V3 Production Gotchas):**
   - **Sintoma 1 (Erro 404 / Sem Conexão):** O Frontend na Vercel não encontra o Backend. **Causa:** A variável `BACKEND_API_URL` foi copiada como `localhost` do `.env.local` ou inserida com sufixo `/api`. **Solução:** Usar apenas a URL base pública do Cloud Run sem sufixos (o Proxy do Next já monta a rota dinamicamente).
   - **Sintoma 2 (Prepared Statement Error no DB):** O backend dispara "prepared statement does not exist". **Causa:** Uso do pooler do Supabase (porta 6543 / PgBouncer transacional) combinado com o cache nativo do `asyncpg`. **Solução:** Adicionar `statement_cache_size=0` no `asyncpg.create_pool`.
   - **Sintoma 3 (SSE / BackgroundTasks Morrendo):** O Cloud Run desliga o processamento no meio da planilha. **Causa:** Opção de CPU baseada em solicitações ativada. **Solução:** Mudar o faturamento para **"Com base em instâncias"** (CPU Always Allocated).
