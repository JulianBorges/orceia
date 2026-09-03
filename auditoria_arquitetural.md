# Relatório de Auditoria Arquitetural — OrceIA V3
**Sessão:** 2026-09-02 | **Auditado por:** Antigravity (análise profunda de código)

> Este relatório é baseado na leitura direta do código-fonte real da V3 (não da documentação) e nas ideias discutidas nesta sessão. Cada recomendação aponta **onde e como mexer**, sem tocar em nada agora.

---

## Legenda de Impacto

| Símbolo | Significado |
|---|---|
| 🔴 | Risco Ativo / Bug Latente — compromete a precisão ou experiência hoje |
| 🟡 | Lacuna de Qualidade — funciona, mas com margem de erro desnecessária |
| 🟢 | Evolução de Produto — nova feature de alto valor, sem urgência crítica |

---

## FASE 1 — Crítico (Motor de IA e Precisão do Resultado)

> **Princípio:** Um orçamento errado não é apenas uma experiência ruim — é um risco jurídico para o órgão público. Erros aqui causam prejuízo real.

---

### 1.1 ✅ Tolerância Dimensional (Implementado via lógica determinística)

**O Problema (fundamentado no código):**
Em [`schemas.py`](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/schemas.py#L49-L58), o campo `aceito_com_tolerancia` instrui a IA a verificar: *"a diferença dimensional é de no máximo 15%"*. Essa verificação matemática está **inteiramente dentro do System Prompt** de [`ai_agents.py`](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/ai_agents.py#L30).

**Por que é grave:** LLMs são notoriamente imprecisos em aritmética de comparação. O GPT-4o-mini pode afirmar que a diferença entre 12mm e 15mm é "dentro dos 15%" quando na verdade é 25%. Isso produz falsos positivos silenciosos: a IA marca `aceito_com_tolerancia=True` com uma divergência real acima do limite técnico, gerando um `status_ia = "RESSALVA"` em vez de um `"REJEITADO"`. No orçamento governamental, aceitar um cano de 15mm onde se exige 12mm pode comprometer uma instalação hidráulica inteira.

**Veredicto: IMPLEMENTAR** — mas nunca como está na V2.

**A Versão Correta (V3 Limpa):**
A verificação deve ser **determinística em Python**, antes de qualquer chamada à OpenAI. O fluxo correto em [`services.py`](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py):

1. O [`preprocessor.py`](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/preprocessor.py) já extrai as `caracteristicas_extras` (ex: `"100MM"`). Ele precisa ser expandido para também retornar um dict estruturado com os valores dimensionais como float (ex: `{"diametro_mm": 100.0}`).
2. Em `services.py`, ao montar o Top 10 do RRF, o código Python compara a dimensão extraída do item do usuário com a dimensão no metadado do Pinecone de cada candidato: `abs(dim_usuario - dim_sinapi) / dim_sinapi <= 0.15`.
3. Essa flag boolean (`tolerancia_ok: True/False`) é **injetada no contexto enviado para a IA**, junto com a instrução: *"O código Python já verificou que a tolerância dimensional É/NÃO É aceitável. Você NÃO deve recalcular. Apenas justifique tecnicamente."*

**Onde mexer:** `preprocessor.py` (retornar dict estruturado) → `services.py` (adicionar lógica de comparação antes de `consultar_agente_engenheiro`) → `schemas.py` (simplificar o `Field` description do `aceito_com_tolerancia`, removendo a instrução matemática).

---

### 1.2 ✅ Contexto do Macro Item no Agente (Implementado)

**O Problema (fundamentado no código):**
Em [`services.py` L84-87](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py#L84-L87), o `termo_com_contexto` enviado para o Agente Engenheiro é montado como:
```
"{descricao do item} [Specs extraidas: {caracteristicas_extras}]"
```
O Agente **não sabe** a qual categoria da obra o item pertence. Um item `"Tubo PVC 100mm"` sem contexto é ambíguo entre: Água Fria, Esgoto, Pluvial e Eletroduto. O Agente é forçado a adivinhar, e frequentemente acerta a dimensão mas erra a família de serviço.

O `is_macro_item` já existe em [`schemas.py` do Zustand](file:///c:/Users/Julian/orceia_v3/frontend/src/components/UploadPlanilha.tsx#L85), mas essa informação **morre no frontend**. Ela nunca viaja para o backend.

**Veredicto: IMPLEMENTAR** — é a melhoria de maior ROI por linha de código escrita.

**A Versão Correta (V3 Limpa):**
1. No Zustand (frontend), ao disparar `processarOrcamentoIA`, o store deve enriquecer cada linha com o texto do seu Macro Item pai (percorrendo o array de cima para baixo, guardando o último `is_macro_item` encontrado).
2. Esse campo (`macro_item_context: string`) viaja no payload para o endpoint `/upsert-linhas`.
3. Em `schemas.py` (backend), adicionar o campo `macro_item_context: Optional[str]` ao `LinhaOrcamentoUpsert`.
4. Em `services.py`, montar o contexto como:
   ```
   "Etapa da Obra: {macro_item_context}\nItem: {descricao} [Specs: {extras}]"
   ```

**Onde mexer:** `useBudgetStore.ts` (enriquecimento contextual) → `LinhaOrcamentoUpsert` no `schemas.py` → montagem do `termo_com_contexto` em `services.py`.

---

### 1.3 🟡 Invalidação de Cache RLHF usa `descricao` Bruta como Chave

**O Problema (fundamentado no código):**
Em [`services.py` L48](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py#L48), a consulta RLHF usa `normalizar_chave(linha.descricao)`. Em [`routes.py` L35](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/routes.py#L35), o salvamento usa `normalizar_chave(feedback.termo_original)`. Isso é correto. 

Mas o **Cache Redis** em [`services.py` L57](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py#L57) usa `get_ai_cache(linha.descricao)` — **sem normalizar a chave**. A função de invalidação em [`routes.py` L37](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/routes.py#L37) também invalida com `feedback.termo_original` sem normalizar.

Isso significa que `"Tubo PVC 100mm"` e `"tubo pvc 100mm"` geram caches diferentes e o RLHF pode falhar em invalidar o cache correto dependendo da capitalização do texto da planilha.

**Veredicto: CORRIGIR** — é um bug silencioso que causa inconsistências de cache.

**Onde mexer:** `services.py` (envolver `linha.descricao` com `normalizar_chave()` antes de chamar `get_ai_cache` e `set_ai_cache`) e verificar se `redis_client.py` precisa do mesmo ajuste em `delete_ai_cache`.

---

## FASE 2 — Alta Importância (Qualidade da Busca e Entrada de Dados)

> **Princípio:** O melhor motor de IA vale pouco se os dados que entram são pobres ou se a busca não encontra os candidatos certos.

---

### 2.1 ✅ Detecção de Lista Plana e Estruturação de EAP (Implementado)

**O Problema (fundamentado no código):**
Em [`UploadPlanilha.tsx` L85](file:///c:/Users/Julian/orceia_v3/frontend/src/components/UploadPlanilha.tsx#L85), a heurística que define `is_macro_item` é: *"sem unidade ou com traço"*. Se 100% dos itens tiverem unidade (lista plana), o sistema processa tudo sem aviso, enviando itens sem contexto hierárquico para a IA (agravando o problema 1.2 acima). O usuário não recebe nenhum feedback.

**Veredicto: IMPLEMENTADO** — com arquitetura otimizada para tokens.

**A Versão Correta (V3 Limpa):**
A V2 oferecia o modal que você mostrou. A V3 deve fazer o mesmo, mas com uma diferença crucial: **a IA de estruturação da EAP deve ser um agente separado, em um endpoint isolado**, nunca acoplado ao motor RRF.

1. **Frontend (`UploadPlanilha.tsx`):** Após o parse, antes de chamar `processarOrcamentoIA`, calcular a porcentagem de `is_macro_item`. Se for 0%, exibir um Modal ("Lista Plana Detectada") com as duas opções da V2.
2. **Backend (novo `modules/eap/`):** Endpoint `POST /eap/estruturar` que recebe apenas as descrições brutas e retorna a lista intercalada com Macro Itens propostos pela IA, sem tocar no banco SINAPI. Um único Agente de Classificação, muito mais barato que o Agente Engenheiro.
3. **Integração:** O frontend exibe a proposta de EAP para o usuário confirmar ou editar antes de iniciar o orçamento.

**Onde mexer:** `UploadPlanilha.tsx` (lógica de detecção) → novo componente Modal → novo `backend/modules/eap/` (isolado, como manda o DDD).

---

### 2.2 ✅ Busca Estratificada — O Orçamentista Virtual (Implementado com GPT-4o-mini)

**O Problema:**
Atualmente, a busca RRF é sempre executada uma única vez, independente da qualidade dos resultados. Se o Top 1 do RRF tiver um score ínfimo (item exótico ou com nomenclatura muito regional), a IA recebe candidatos de baixíssima qualidade e é forçada a "rejeitar" ou, pior, a aceitar um falso positivo. Nenhuma reprocessamento é tentado.

**Veredicto: IMPLEMENTAR** — com arquitetura de custo zero quando a primeira tentativa é boa.

**A Versão Correta (V3 Limpa — Lazy Evaluation):**
Em [`search_engine.py`](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/search_engine.py#L75), após calcular o RRF:

1. **Calcular o Score Máximo Normalizado** do Top 1.
2. **Se score > limiar (ex: 0.85):** Seguir para a IA normalmente. Custo: zero adicional.
3. **Se score ≤ limiar (Fallback Ativado):** Acionar um micro-agente `reformular_query()` que pede ao GPT (prompt mínimo, barato) 3 variações de nomenclatura SINAPI para o item. Executar as 3 buscas em paralelo com `asyncio.gather`. Refundir tudo num RRF expandido. Custo: adicional apenas nos ~5-10% de itens difíceis.

**Onde mexer:** `search_engine.py` (adicionar cálculo de score máximo e lógica de fallback) → novo `reformulador.py` em `modules/orcamento/` (micro-agente de query expansion).

---

### 2.3 ✅ Dicionário de Canteiro (Implementado)

**O Problema:**
Não existe nenhuma camada de pré-normalização léxica. Termos como "Bobcat", "Betoneira", "Pó de pedra" entram diretamente no Pinecone, que é um banco vetorial treinado em linguagem técnica formal, não em jargão de canteiro.

**Veredicto: IMPLEMENTAR** — é uma das maiores razões de itens rejeitados desnecessariamente.

**A Versão Correta (V3 Limpa):**
Criar um arquivo `backend/core/vocabulario_obra.py` com um dicionário Python puro (sem dependências externas):
```python
SINONIMOS_CANTEIRO = {
    "bobcat": "minicarregadeira",
    "po de pedra": "pedrisco",
    "brita zero": "pedrisco",
    # ... ~200 entradas
}
```
Em [`preprocessor.py`](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/preprocessor.py), como **primeiro passo** antes do Regex dimensional, passar o texto pelo dicionário.

**Onde mexer:** Novo `backend/core/vocabulario_obra.py` → chamada no início de `normalizar_termo_busca()` em `preprocessor.py`.

---

### 2.4 ✅ Upload: Aba Fixa e Feedback Silencioso (Implementado)

**O Problema (fundamentado no código):**
Em [`UploadPlanilha.tsx` L27-28](file:///c:/Users/Julian/orceia_v3/frontend/src/components/UploadPlanilha.tsx#L27-L28), o código força `wb.SheetNames[0]` e nunca notifica o usuário em caso de falha de parse.

**Veredicto: IMPLEMENTAR (parcialmente).**

- **Feedback de Erro:** Simples e de alta prioridade. Se `parsedData.length === 0` após o loop, exibir um `toast` ou alerta explicando o problema (ex: "Nenhum item encontrado. Verifique se sua planilha possui colunas com 'Item' e 'Descrição'"). Custo de implementação: 5 linhas.
- **Seleção de Aba:** Implementar somente se for identificado como problema real por usuários. A complexidade de UI adicionada não justifica agora.

**Onde mexer:** `UploadPlanilha.tsx` (adicionar feedback de erro após o loop) → integrar com sistema de `toast` existente.

---

## FASE 3 — Médio Prazo (Inteligência de Contexto Documental)

> **Princípio:** Aqui saímos do território de "ferramenta de orçamento" e entramos no território de "Copiloto de Engenharia Governamental". Alta diferenciação de produto.

---

### 3.1 🟢 Pipeline Bidirecional de Memoriais Descritivos (AuditorIA + Geração)

**Análise:**
O `Plano_AuditorIA.md` prevê apenas o **Modo Auditoria** (PDF chega depois do orçamento). A discussão desta sessão revelou um segundo vetor igualmente poderoso: o **Modo Geração** (PDF chega antes, como guia de especificações). Ambos compartilham 100% do mesmo pipeline de ingestão.

**Veredicto: IMPLEMENTAR** — mas em etapas sequenciais, começando pela fundação compartilhada.

**Arquitetura Recomendada (V3 Limpa — 3 Etapas):**

**Etapa A (Fundação Compartilhada):** Construir `backend/modules/auditoria/` com o pipeline de ingestão de PDFs (LlamaParse ou Claude Vision → chunking semântico por parágrafo → Pinecone em namespace dinâmico `projeto_{id}_memorial`). Essa etapa não entrega valor ao usuário por si só, mas é a base das duas features.

**Etapa B (Modo Geração — o novo):** No frontend, adicionar um botão "Carregar Memorial" antes do upload da planilha. Ao ingerir o PDF, o Agente Mapeador em `ai_agents.py` recebe um terceiro bloco de contexto no prompt: o trecho mais similar do memorial ao item sendo orçado (buscado via Pinecone no namespace do memorial). Isso transforma a adivinhação em leitura direta da especificação.

**Etapa C (Modo Auditoria — planejado):** Com o memorial já vetorizado (Etapa A), o usuário pode carregar o orçamento de uma empresa e acionar uma rota `POST /auditoria/auditar-planilha`. Um Agente Auditor cruza cada linha do orçamento com os trechos do memorial e retorna um Laudo de Conformidade (via SSE) com: status por item (CONFORME / DIVERGENTE), trecho do memorial violado e página.

**Roteador de Intenção:** Um campo `modo: Literal["gerar", "auditar"]` no request determina qual agente e qual schema Pydantic de retorno são usados.

**Onde mexer:** Novo `backend/modules/auditoria/` (DDD rigoroso) → novo endpoint no frontend para upload de PDF → enriquecimento de contexto em `services.py` (Modo Geração) → novo Agente Auditor em `ai_agents.py` do módulo auditoria (Modo Auditoria).

---

### 3.2 ✅ Filtro de Metadados por Unidade (Implementado)

**O Problema:**
O Pinecone atual retorna os 20 vizinhos semânticos mais próximos sem levar em conta a unidade de medida do item. "Concreto Usinado" em `m³` e "Forma de Concreto" em `m²` são semanticamente próximos e podem aparecer misturados no Top 10.

**Veredicto: IMPLEMENTAR** — mas apenas após a implementação de 2.2 (Busca Estratificada), pois os dois interagem.

**A Versão Correta:**
O `LinhaOrcamentoUpsert` já carrega `unidade`. Em `search_engine.py`, ao chamar o Pinecone, injetar um filtro de metadata:
```python
filter={"unidade": {"$eq": unidade_do_usuario}}
```
Isso deve ser aplicado como **preferência ponderada**, não como hard block. Se o filtro retornar poucos resultados (< 3), relaxar o filtro e tentar sem ele (evitando quebrar itens onde o usuário digitou a unidade errada ou abreviada diferente).

**Onde mexer:** `search_engine.py` na função `_pinecone_search()`.

---

## FASE 4 — Fundação Técnica (Dívida Técnica e Robustez de SaaS)

> **Princípio:** São itens que não entregam features visíveis, mas evitam bugs graves em produção à medida que o produto escala.

---

### 4.1 🟡 CRUD de Orçamentos Salvos (Dívida Técnica do Master Plan)

**Status no Código:**
A tabela `planilhas` e `planilhas_linhas` já existem no Supabase e o Auto-Save já escreve nelas ([`services.py` L169-210](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py#L169-L210)). O dado persistido não tem tela de acesso.

**Veredicto: IMPLEMENTAR** — remove a dependência do LocalStorage do navegador (dado que se perde ao limpar o cache). É a Sprint 4.3 do Master Plan.

**Onde mexer:** Novo endpoint `GET /orcamento/planilhas` → Modal "Meus Orçamentos" no frontend.

---

### 4.2 🟡 Semáforo de Processo Único (Risco de Escalabilidade)

**O Problema (fundamentado no código):**
Em [`services.py` L12-16](file:///c:/Users/Julian/orceia_v3/backend/modules/orcamento/services.py#L12-L16), o comentário do próprio código avisa: *"O servidor DEVE rodar com 1 worker apenas"*. O semáforo Python (`asyncio.Semaphore`) é in-memory e não funciona em ambientes com múltiplos processos/replicas (Cloud Run auto-scaling).

**Veredicto: MIGRAR** — quando o produto atingir múltiplos tenants simultâneos exigindo auto-scaling.

**A Versão Correta:**
Substituir `asyncio.Semaphore` por um semáforo distribuído via Redis (usando `SET key NX EX` como lock). O comentário no código já aponta essa direção.

**Onde mexer:** `services.py` (substituir o semáforo local por um `RedisSemaphore` wrapper em `core/redis_client.py`).

---

## Síntese Executiva

| Fase | Item | Impacto | Dificuldade | Status Atual |
|---|---|---|---|---|
| **1 — Crítico** | 1.1 Tolerância dimensional determinística | 🔴 Alta precisão | ⭐⭐ Média | ✅ Concluído |
| **1 — Crítico** | 1.2 Contexto do Macro Item no Agente | 🔴 Maior ROI | ⭐ Baixa | ✅ Concluído |
| **1 — Crítico** | 1.3 Normalização de chave no Cache Redis | 🔴 Bug silencioso | ⭐ Baixa | ✅ Falso Positivo (Resolvido nativamente) |
| **2 — Alta** | 2.1 Detecção de Lista Plana + EAP | 🟡 UX + Precisão | ⭐⭐⭐ Alta | ✅ Concluído |
| **2 — Alta** | 2.2 Busca Estratificada com Fallback | 🟡 Qualidade busca | ⭐⭐ Média | ✅ Concluído |
| **2 — Alta** | 2.3 Dicionário de Canteiro | 🟡 Custo zero | ⭐ Baixa | ✅ Concluído |
| **2 — Alta** | 2.4 Feedback de upload silencioso | 🟡 UX básica | ⭐ Baixa | ✅ Concluído |
| **3 — Médio** | 3.1 Pipeline bidirecional Memoriais (PDF) | 🟢 Diferenciação máxima | ⭐⭐⭐⭐ Muito Alta | ⏳ Pendente |
| **3 — Médio** | 3.2 Filtro de unidade Pinecone | 🟢 Precisão busca | ⭐ Baixa | ✅ Concluído |
| **4 — Fundação** | 4.1 CRUD de Orçamentos Salvos | 🟡 Dívida técnica | ⭐⭐ Média | ⏳ Pendente |
| **4 — Fundação** | 4.2 Semáforo Distribuído (Redis) | 🟡 Escalabilidade | ⭐⭐ Média | ⏳ Pendente |

---

> **Próximos Passos Recomendados:** A Fase 1 e a Fase 2 já foram completamente refatoradas. O próximo alvo principal deve ser o Item 4.1 (CRUD de Orçamentos Salvos).
