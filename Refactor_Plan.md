# Refactor Plan V3 — Plano de Execução para LLMs

> **Instrução de Leitura Obrigatória:** Antes de executar qualquer Sprint, leia:
> 1. `AI_Onboarding.md` — contexto arquitetural e decisões de design
> 2. `.agents/rules/GEMINI.md` — regras universais invioláveis
> 3. `.agents/rules/01_core_architecture.md` — DDD e separação de módulos
> 4. `.agents/rules/02_frontend.md` — regras de estado Zustand
> 5. `.agents/rules/03_backend.md` — regras de backend FastAPI
>
> **Princípio de Execução:** Cada Sprint é **atômico** — execute do início ao fim sem interromper.
> Cada task dentro do Sprint é **cirúrgica** — edite apenas os arquivos listados.
> **NUNCA** altere `Master_Plan.md`, `Manual_OrceIA.md` ou arquivos em `supabase/` sem aprovação.

---

## Status dos Sprints

| Sprint | Escopo | Severidade | Status |
|--------|--------|-----------|--------|
| [S6] Sprint 6 — Correções Críticas de Motor | Backend Core | 🔴 Crítico | `[X] Concluído` |
| [S7] Sprint 7 — Precisão de Engenharia Civil | IA + Schema | 🟡 Alto | `[X] Concluído` |
| [S8] Sprint 8 — Resiliência de Estado Frontend | Frontend | 🟡 Alto | `[ ] Pendente` |
| [S9] Sprint 9 — Hardening e Qualidade | Backend + Frontend | 🟠 Médio | `[ ] Pendente` |

---

## 🔴 [S6] Sprint 6 — Correções Críticas de Motor

**Objetivo:** Corrigir os 5 achados críticos que comprometem a precisão da busca, a integridade da deleção de dados e a saúde do servidor em produção.

**Arquivos tocados neste sprint:**
- `backend/modules/orcamento/preprocessor.py` ← **NOVO**
- `backend/modules/orcamento/search_engine.py`
- `backend/modules/orcamento/services.py`
- `backend/modules/orcamento/routes.py`
- `frontend/src/app/api/proxy/[...path]/route.ts`

**Arquivos PROIBIDOS de alterar neste sprint:** `schemas.py`, `ai_agents.py`, `useBudgetStore.ts`, `main.py`

---

### S6.T1 — Criar o Agente Corretor de Termos (Normalização Pré-Embedding)

**Por quê:** O Pinecone recebe strings brutas como `"CONCRETO FCK 30 MPa ESPESSURA 15CM"`. Modelos de embedding não separam semântica de especificação dimensional — os números contaminam o espaço vetorial e degradam a busca exatamente para os itens mais críticos da engenharia estrutural.

**O Manual (Manual_OrceIA.md, Fase 3)** define este agente como obrigatório. Ele não existe no código.

**Criar o arquivo** `backend/modules/orcamento/preprocessor.py`:

```python
# backend/modules/orcamento/preprocessor.py
"""
Agente Corretor de Termos — Pré-processamento para o Motor RRF.

Extrai especificações dimensionais/numéricas do núcleo semântico da descrição
antes de gerar o embedding vetorial (Pinecone). As características são preservadas
para análise lógica posterior pelo Agente Mapeador no prompt do GPT.

Exemplos de transformação:
  "CONCRETO FCK 30 MPA ESPESSURA 15CM" -> termo_limpo: "CONCRETO USINADO BOMBEADO"
                                           caracteristicas: "FCK 30 MPA ESPESSURA 15CM"
  "TUBO PVC 100MM JE"                  -> termo_limpo: "TUBO PVC JE"
                                           caracteristicas: "100MM"
  "ALVENARIA DE TIJOLO"                -> termo_limpo: "ALVENARIA DE TIJOLO"
                                           caracteristicas: ""
"""
import re
from pydantic import BaseModel


class TermoNormalizado(BaseModel):
    termo_limpo: str
    """Nucleo semantico sem dimensoes — otimizado para embedding vetorial."""
    caracteristicas_extras: str
    """Especificacoes dimensionais/numericas extraidas — contexto para o Agente Mapeador."""


# Padrao: numeros seguidos (ou nao) por unidades de engenharia
_PADRAO_DIMENSIONAL = re.compile(
    r'\b\d+[\.,]?\d*\s*'
    r'(mm|cm|dm|m2|m3|m|kg|kn|kpa|mpa|fck|kgf|psi|mca|kva|kw|kwh|hp|l|lt)?\b',
    re.IGNORECASE
)


def normalizar_termo_busca(descricao: str) -> TermoNormalizado:
    """
    Separa o nucleo semantico da descricao de suas especificacoes numericas.

    Args:
        descricao: Descricao original do item da planilha.

    Returns:
        TermoNormalizado com `termo_limpo` (para embedding) e
        `caracteristicas_extras` (para contexto do agente IA).
    """
    descricao = descricao.strip()
    if not descricao:
        return TermoNormalizado(termo_limpo="", caracteristicas_extras="")

    raw_specs = _PADRAO_DIMENSIONAL.findall(descricao)

    # Remove as especificacoes do nucleo
    termo_limpo = _PADRAO_DIMENSIONAL.sub(' ', descricao)
    # Limpa espacos duplos resultantes da remocao
    termo_limpo = ' '.join(termo_limpo.split()).strip()

    # Fallback: se o termo ficou vazio (era tudo numero), usa o original
    if not termo_limpo:
        return TermoNormalizado(termo_limpo=descricao, caracteristicas_extras="")

    # Preserva a descricao original como contexto dimensional compacto
    caracteristicas = descricao[:150] if raw_specs else ""

    return TermoNormalizado(
        termo_limpo=termo_limpo,
        caracteristicas_extras=caracteristicas
    )
```

---

### S6.T2 — Integrar o Agente Corretor ao `search_engine.py`

**Editar** `backend/modules/orcamento/search_engine.py`.

**Adicionar import no topo:**
```python
from modules.orcamento.preprocessor import normalizar_termo_busca
```

**Modificar a assinatura de retorno:**
```python
async def realizar_busca_hibrida(termo_busca: str, id_planilha: str, tenant_id: str) -> tuple[list[dict], str]:
```

**Localizar no corpo da funcao:**
```python
    pg_task = asyncio.create_task(_postgres_search(termo_busca, "composicoes"))
    pc_task = asyncio.create_task(_pinecone_search(termo_busca, tenant_id, "composicoes"))
```

**Substituir por:**
```python
    # Agente Corretor: normaliza o termo antes do embedding (nao afeta busca lexical)
    termo_normalizado = normalizar_termo_busca(termo_busca)
    print(f"[Preprocessor] '{termo_busca}' -> Limpo: '{termo_normalizado.termo_limpo}'")

    # Busca lexical usa o termo ORIGINAL (trigramas funcionam melhor com texto completo)
    pg_task = asyncio.create_task(_postgres_search(termo_busca, "composicoes"))
    # Busca vetorial usa o termo LIMPO (embedding sem ruido dimensional)
    pc_task = asyncio.create_task(_pinecone_search(termo_normalizado.termo_limpo, tenant_id, "composicoes"))
```

**Localizar o `return top_items` ao final da funcao e substituir por:**
```python
    return top_items, termo_normalizado.caracteristicas_extras
```

---

### S6.T3 — Corrigir o Boost RRF (Distorcao Matematica)

**Editar** `backend/modules/orcamento/search_engine.py`.

Localizar o bloco do loop Pinecone:
```python
    for rank, item in enumerate(pc_results):
        cod = item["codigo"]
        if cod in scores_rrf:
            # HUB MAGICO: Encontrado em ambos! Boost matematico de 20%
            scores_rrf[cod] += (1.0 / (k + rank + 1))
            scores_rrf[cod] *= 1.20
        else:
            scores_rrf[cod] = (1.0 / (k + rank + 1))
            master_dict[cod] = item
```

Substituir por:
```python
    for rank, item in enumerate(pc_results):
        cod = item["codigo"]
        score_pc = 1.0 / (k + rank + 1)
        if cod in scores_rrf:
            # BOOST DE CONSENSO: aplica +20% APENAS sobre o score incremental do Pinecone.
            # Nao multiplica o total acumulado — evita distorcao matematica em edge cases.
            scores_rrf[cod] += score_pc * 1.20
        else:
            scores_rrf[cod] = score_pc
            master_dict[cod] = item
```

**Remover a linha de `score_rrf_interno`** (dado morto no payload SSE):
```python
        item["score_rrf_interno"] = round(score * 100, 2)
```
Substituir por:
```python
        print(f"[RRF] {cod}: score={round(score * 100, 2)}")
```

---

### S6.T4 — Propagar `caracteristicas_extras` ao Agente IA

**Editar** `backend/modules/orcamento/services.py`.

Localizar:
```python
    opcoes_rrf = await realizar_busca_hibrida(linha.descricao, id_planilha, linha.tenant_id)
```

Substituir por:
```python
    opcoes_rrf, caracteristicas_extras = await realizar_busca_hibrida(linha.descricao, id_planilha, linha.tenant_id)
```

Localizar:
```python
    analise = await consultar_agente_engenheiro(linha.descricao, opcoes_rrf, valor_financeiro_total)
```

Substituir por:
```python
    # Injeta caracteristicas dimensionais como contexto para o Agente Mapeador avaliar tolerancias
    termo_com_contexto = linha.descricao
    if caracteristicas_extras:
        termo_com_contexto = f"{linha.descricao} [Specs extraidas: {caracteristicas_extras}]"
    analise = await consultar_agente_engenheiro(termo_com_contexto, opcoes_rrf, valor_financeiro_total)
```

---

### S6.T5 — Restringir `tenacity` a Excecoes Recuperaveis

**Editar** `backend/modules/orcamento/services.py`.

Adicionar import da OpenAI:
```python
from openai import RateLimitError, APITimeoutError, APIConnectionError
```

Substituir o decorator `@retry`:
```python
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    # Retenta APENAS erros de infra recuperaveis. ValueError e ValidationError NAO devem ser retentados.
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError, ConnectionError)),
    reraise=True
)
```

---

### S6.T6 — Adicionar Timeout de Stream Zumbi no SSE

**Editar** `backend/modules/orcamento/routes.py`.

Substituir o corpo da funcao `event_generator` (dentro de `sse_stream`):

```python
    async def event_generator():
        stream_key = f"stream:{tenant_id}:planilha:{id_planilha}"
        last_id = last_event_id
        MAX_IDLE_PINGS_POS_CONCLUSAO = 12  # 12 x 5s = 60s apos lote_concluido
        idle_count = 0
        lote_concluido = False

        try:
            while True:
                if rc.redis_client is None:
                    break

                streams = await rc.redis_client.xread({stream_key: last_id}, block=5000, count=10)

                if streams:
                    idle_count = 0
                    for stream_name, messages in streams:
                        for message_id, message_data in messages:
                            last_id = message_id
                            payload = message_data.get("payload", "{}")
                            yield f"id: {message_id}\ndata: {payload}\n\n"

                            try:
                                data = json.loads(payload)
                                if data.get("status") == "lote_concluido":
                                    lote_concluido = True
                            except (json.JSONDecodeError, AttributeError):
                                pass
                else:
                    idle_count += 1
                    if lote_concluido and idle_count >= MAX_IDLE_PINGS_POS_CONCLUSAO:
                        print(f"[SSE] Stream encerrado por idle timeout (planilha: {id_planilha})")
                        break
                    yield ": ping\n\n"

        except asyncio.CancelledError:
            print(f"SSE Streaming desconectado pelo cliente para a planilha {id_planilha}.")
        except Exception as e:
            print(f"Erro fatal no SSE: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'status': 'erro', 'id': 'fatal', 'mensagem': f'ERRO INTERNO REDIS: {str(e)}'})}\n\n"
```

---

### S6.T7 — Exportar DELETE, PATCH e PUT no Proxy

**Editar** `frontend/src/app/api/proxy/[...path]/route.ts`.

Adicionar APOS a funcao `POST` exportada e ANTES da funcao `handleProxy`:

```typescript
export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return handleProxy(request, params.path);
}
```

---

### S6 — Checklist de Verificacao

- `[x]` `preprocessor.py` criado em `backend/modules/orcamento/`
- `[x]` `search_engine.py` retorna `tuple[list[dict], str]`
- `[x]` `services.py` desempacota `opcoes_rrf, caracteristicas_extras`
- `[x]` Boost RRF usa `score_pc * 1.20` (delta), nao `scores_rrf[cod] *= 1.20` (total)
- `[x]` `@retry` usa `retry_if_exception_type((RateLimitError, ...))`
- `[x]` SSE generator tem logica de timeout apos `lote_concluido`
- `[x]` `route.ts` exporta `DELETE`, `PATCH` e `PUT`
- `[x]` Servidor backend inicia sem erros
- `[x]` Frontend compila sem erros

---

## 🟡 [S7] Sprint 7 — Precisao de Engenharia Civil (IA + Schema)

**Objetivo:** Implementar as regras de conformidade SINAPI declaradas no Manual mas ausentes no codigo: tolerancia dimensional, invalidacao de cache pos-RLHF e separacao de dados pereciveis no Redis.

**Arquivos tocados neste sprint:**
- `backend/modules/orcamento/schemas.py`
- `backend/modules/orcamento/ai_agents.py`
- `backend/modules/orcamento/services.py`
- `backend/modules/orcamento/routes.py`
- `backend/core/redis_client.py`

**Arquivos PROIBIDOS de alterar neste sprint:** `search_engine.py`, `preprocessor.py`, `main.py`, qualquer arquivo de frontend.

---

### S7.T1 — Adicionar Tolerancia Dimensional ao Schema `AnaliseIA`

**Editar** `backend/modules/orcamento/schemas.py`.

Adicionar o campo `aceito_com_tolerancia` na classe `AnaliseIA`, ANTES de `codigo_selecionado`:

```python
    aceito_com_tolerancia: bool = Field(
        default=False,
        description="True SOMENTE se nao houver equivalente exato e a diferenca dimensional for <=15% em atributo NAO estrutural. Implica status RESSALVA obrigatorio. False para rejeicao ou aceitacao exata."
    )
```

---

### S7.T2 — Incorporar Tolerancia Dimensional no Prompt do Agente

**Editar** `backend/modules/orcamento/ai_agents.py`.

Substituir o valor da variavel `prompt_sistema` por:

```python
    prompt_sistema = """Voce e um Engenheiro de Orcamentos Senior (Copiloto OrceIA), especialista em tabelas SINAPI.
Sua missao e auditar o "item original da planilha" e encontrar a correspondencia exata entre as "opcoes do SINAPI" fornecidas.

REGRAS DE OURO (ANTI-ALUCINACAO):
1. RACIOCINIO EXPLICITO: Utilize a variavel 'raciocinio_step_by_step' para registrar sua analise estrutural e comparativa ANTES de definir o codigo ou o rigor.
2. DISCIPLINA CONSTRUTIVA: Nunca selecione uma composicao apenas porque as dimensoes (ex: "20 cm", "5 mm") ou unidades batem. A natureza do servico (ex: Terraplenagem vs Alvenaria vs Hidraulica) DEVE ser compativel.
3. REJEICAO OBRIGATORIA: Se nenhuma opcao for tecnicamente correspondente ao servico original, voce DEVE retornar `codigo_selecionado` como null. E preferivel deixar o item sem codigo do que aprovar um falso positivo que arruinara o orcamento.
4. CURVA ABC E RIGOR: Classifique a 'categoria_rigor' como ALTO se o item for estruturalmente critico (fundacao, estrutura, eletrica, hidraulica, impermeabilizacao) ou se o percentual financeiro indicar ser um item Classe A da obra.
5. TOLERANCIA DIMENSIONAL (<=15%): Se nao existir equivalente exato no SINAPI, voce PODE aceitar uma composicao com diferenca dimensional <=15% em atributos NAO estruturais (ex: bitola de tubo acessorio, espessura de revestimento nao estrutural). Neste caso: marque aceito_com_tolerancia=True. O status sera automaticamente RESSALVA. Para diferenca >15% ou atributo estrutural (ex: fck do concreto, seccao de aco): REJEITAR.
6. PROIBIDO: Nunca aceite composicao de familia de servico diferente (ex: alvenaria no lugar de estrutura metalica), independente de qualquer dimensao coincidir.

Sua saida deve ser estritamente o JSON definido no schema."""
```

---

### S7.T3 — Usar `aceito_com_tolerancia` na Logica de Status

**Editar** `backend/modules/orcamento/services.py`.

Localizar:
```python
    status_ia = "ACEITO"
    if not analise.codigo_selecionado:
        status_ia = "REJEITADO"
    elif analise.categoria_rigor == "ALTO":
        status_ia = "RESSALVA"
```

Substituir por:
```python
    status_ia = "ACEITO"
    if not analise.codigo_selecionado:
        status_ia = "REJEITADO"
    elif analise.aceito_com_tolerancia:
        # Tolerancia dimensional <=15% aceita — sempre RESSALVA para rastreabilidade SINAPI
        status_ia = "RESSALVA"
    elif analise.categoria_rigor == "ALTO":
        # Item critico ou Classe A da Curva ABC — sempre RESSALVA para auditoria
        status_ia = "RESSALVA"
```

---

### S7.T4 — Separar Cache Cacheavel dos Precos Pereciveis

**Por que:** O SINAPI e atualizado mensalmente pela CEF. Cache de 15 dias com precos incluidos entrega valores desatualizados silenciosamente.

**Editar** `backend/modules/orcamento/services.py`.

**Passo 1 — Substituir o bloco de construcao do resultado e cache (linhas ~78-91):**

Localizar:
```python
    resultado = {
        "id": linha.id,
        "codigo_novo": analise.codigo_selecionado,
        "status_ia": status_ia,
        "parecer": analise.parecer_tecnico,
        "rigor": analise.categoria_rigor,
        "memoria_calculo": [op.model_dump() for op in analise.composicoes_analisadas]
    }
    
    # 5. Salva o veredito no Redis para nao gastar API nas proximas vezes
    await set_ai_cache(linha.descricao, resultado)
    resultado["origem"] = "OPENAI"
    
    return resultado
```

Substituir por:
```python
    # Cache armazena APENAS o veredito logico — precos sao pereciveis (SINAPI mensal)
    resultado_cacheavel = {
        "codigo_novo": analise.codigo_selecionado,
        "status_ia": status_ia,
        "parecer": analise.parecer_tecnico,
        "rigor": analise.categoria_rigor,
        "aceito_com_tolerancia": analise.aceito_com_tolerancia,
    }

    # 5. Salva APENAS o veredito no Redis (sem memoria_calculo — precos nao sao cacheados)
    await set_ai_cache(linha.descricao, resultado_cacheavel)

    # Monta resultado completo com memoria_calculo frescos do RRF atual
    resultado = {
        "id": linha.id,
        **resultado_cacheavel,
        "memoria_calculo": [op.model_dump() for op in analise.composicoes_analisadas],
        "origem": "OPENAI",
    }

    return resultado
```

**Passo 2 — Atualizar o bloco de cache hit para incluir memoria_calculo frescos:**

Localizar:
```python
    cache = await get_ai_cache(linha.descricao)
    if cache:
        codigos_validos_rrf = [op["codigo"] for op in opcoes_rrf]
        if cache.get("codigo_novo") in codigos_validos_rrf or not cache.get("codigo_novo"):
            cache["origem"] = "CACHE_REDIS"
            cache["id"] = linha.id # Sobrescreve a ID velha do cache com a ID atual da requisicao!
            return cache
        else:
            # O item foi removido do SINAPI ou Pinecone recentemente! Cache invalidado.
            print(f"[CACHE] Invalidacao por Seguranca! Codigo {cache.get('codigo_novo')} nao esta mais no Top 15.")
```

Substituir por:
```python
    cache = await get_ai_cache(linha.descricao)
    if cache:
        codigos_validos_rrf = [op["codigo"] for op in opcoes_rrf]
        if cache.get("codigo_novo") in codigos_validos_rrf or not cache.get("codigo_novo"):
            # Enriquece o veredito cacheado com memoria_calculo frescos do RRF atual
            memoria_fresca = [op for op in opcoes_rrf if op["codigo"] == cache.get("codigo_novo")]
            return {
                "id": linha.id,
                **cache,
                "memoria_calculo": memoria_fresca,
                "origem": "CACHE_REDIS",
            }
        else:
            print(f"[CACHE] Invalidacao por Seguranca! Codigo {cache.get('codigo_novo')} nao esta mais no Top 15.")
```

---

### S7.T5 — Adicionar `delete_ai_cache` ao `redis_client.py`

**Editar** `backend/core/redis_client.py`. Adicionar ao final do arquivo:

```python
async def delete_ai_cache(texto_busca: str) -> bool:
    """
    Invalida o cache da IA para um termo especifico.
    Chamado pelo endpoint /feedback apos o engenheiro corrigir o veredito (RLHF).

    Returns:
        True se a chave existia e foi deletada, False caso contrario.
    """
    if redis_client is None:
        return False
    chave_hash = hashlib.sha256(texto_busca.strip().lower().encode()).hexdigest()
    deleted = await redis_client.delete(f"cache_ia:{chave_hash}")
    return deleted > 0
```

---

### S7.T6 — Invalidar Cache Redis ao Salvar Feedback RLHF

**Editar** `backend/modules/orcamento/routes.py`.

Adicionar import:
```python
from core.redis_client import delete_ai_cache
```

No endpoint `/feedback`, apos o `conn.execute` e antes do `return`:
```python
        # Invalida o cache Redis para o termo corrigido pelo humano
        await delete_ai_cache(feedback.termo_original)
        print(f"[RLHF] Cache invalidado para: '{feedback.termo_original[:50]}'")
        return {"status": "success", "message": "Feedback memorizado para o Tenant"}
```

---

### S7 — Checklist de Verificacao

- `[x]` `schemas.py` tem campo `aceito_com_tolerancia: bool` em `AnaliseIA`
- `[x]` `ai_agents.py` tem Regra 5 (Tolerancia Dimensional) no prompt
- `[x]` `services.py` usa `aceito_com_tolerancia` na logica de status
- `[x]` Cache Redis salva apenas `resultado_cacheavel` (sem `memoria_calculo`)
- `[x]` Cache hit retorna `memoria_calculo` frescos do RRF
- `[x]` `redis_client.py` tem `delete_ai_cache`
- `[x]` Endpoint `/feedback` chama `delete_ai_cache` apos salvar no banco
- `[x]` Servidor backend inicia e `POST /orcamento/feedback` retorna 200

---

## 🟡 [S8] Sprint 8 — Resiliencia de Estado Frontend

**Objetivo:** Corrigir dirty tracking cirurgico, comportamento de `clearBudget`, prevencao de duplo processamento e reconexao SSE resiliente.

**Arquivos tocados neste sprint:**
- `frontend/src/store/useBudgetStore.ts`
- `frontend/src/hooks/useSseListener.ts`

**Arquivos PROIBIDOS de alterar neste sprint:** `useAutoSave.ts`, `BudgetTable.tsx`, qualquer arquivo de backend.

**Dependencia de package — executar ANTES das edicoes:**
```bash
cd frontend && npm install @microsoft/fetch-event-source
```

---

### S8.T1 — Corrigir `setTableData` para Diff Real

**Contexto:** O metodo atual marca TODAS as 5.000 rows como dirty em qualquer chamada. Em uma planilha de 5.000 itens, isso dispara 25 chunks de auto-save desnecessariamente.

**Editar** `frontend/src/store/useBudgetStore.ts`.

Localizar:
```typescript
      setTableData: (data) => set((state) => {
        const newData = typeof data === 'function' ? data(state.tableData) : data;
        return {
          tableData: newData,
          dirtyRowIds: newData.map(r => r.id),
          isDirty: true
        };
      }),
```

Substituir por:
```typescript
      setTableData: (data) => set((state) => {
        const newData = typeof data === 'function' ? data(state.tableData) : data;
        // Diff cirurgico: mapeia rows antigas por ID para comparacao O(1)
        const oldMap = new Map(state.tableData.map(r => [r.id, r]));
        // Identifica apenas as rows que MUDARAM (novas ou modificadas)
        const changedIds = newData
          .filter(r => !oldMap.has(r.id) || oldMap.get(r.id) !== r)
          .map(r => r.id);
        const newDirty = Array.from(new Set([...state.dirtyRowIds, ...changedIds]));
        return {
          tableData: newData,
          dirtyRowIds: newDirty,
          isDirty: newDirty.length > 0,
        };
      }),
```

---

### S8.T2 — Corrigir `clearBudget`

**Editar** `frontend/src/store/useBudgetStore.ts`.

Localizar:
```typescript
      clearBudget: () => set({ tableData: [], title: 'Orçamento Base', bdi: 25.0, dirtyRowIds: [], isDirty: true }),
```

Substituir por:
```typescript
      clearBudget: () => set({
        tableData: [],
        title: 'Orçamento Base',
        bdi: 25.0,
        dirtyRowIds: [],
        isDirty: false,    // Nao ha nada para salvar — nao aciona o auto-save
        planilhaId: null,  // Remove o ID para evitar erro de FK em planilha inexistente
      }),
```

---

### S8.T3 — Remover `PROCESSANDO` do Filtro de Reprocessamento

**Editar** `frontend/src/store/useBudgetStore.ts`.

Localizar (dentro de `processarOrcamentoIA`):
```typescript
          .filter(row => !row.is_macro_item && row.descricao && row.descricao.trim() !== '' && (!row.ai_status || row.ai_status === 'PENDENTE' || row.ai_status === 'PROCESSANDO'))
```

Substituir por:
```typescript
          .filter(row =>
            !row.is_macro_item &&
            row.descricao &&
            row.descricao.trim() !== '' &&
            // Nao reenvia itens em voo — prevencao de processamento duplo
            (!row.ai_status || row.ai_status === 'PENDENTE')
          )
```

---

### S8.T4 — Migrar SSE Listener para `fetch-event-source`

**Editar** `frontend/src/hooks/useSseListener.ts`. Substituir o conteudo completo:

```typescript
import { useEffect, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { useBudgetStore } from '../store/useBudgetStore';

/**
 * Consome o canal SSE do backend via fetch-event-source.
 * Vantagem sobre EventSource nativo: suporta Last-Event-ID para reconexao resiliente.
 */
export function useSseListener(planilhaId: string | null) {
  const updateRowById = useBudgetStore((state) => state.updateRowById);
  const lastEventIdRef = useRef<string>('0-0');
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!planilhaId) return;

    console.log(`[SSE] Conectando ao barramento de Eventos da Planilha: ${planilhaId}`);
    abortControllerRef.current = new AbortController();

    fetchEventSource(`/api/proxy/orcamento/stream/${planilhaId}`, {
      signal: abortControllerRef.current.signal,
      headers: {
        'Last-Event-ID': lastEventIdRef.current,
      },

      onopen: async (response) => {
        if (!response.ok) {
          console.error(`[SSE] Falha ao abrir conexao: HTTP ${response.status}`);
        }
      },

      onmessage: (event) => {
        if (event.id) {
          lastEventIdRef.current = event.id;
        }

        try {
          const payload = JSON.parse(event.data);

          if (payload.status === 'sucesso' && payload.dados_ia) {
            const { id, status_ia, parecer, codigo_novo, memoria_calculo } = payload.dados_ia;
            console.log(`[SSE] Linha processada pela IA (ID: ${id})`);

            const updatePayload: Record<string, unknown> = {
              ai_status: status_ia,
              ai_parecer_tecnico: parecer,
              codigo: codigo_novo,
              memoria_calculo: memoria_calculo || [],
            };

            if (codigo_novo && memoria_calculo) {
              const match = memoria_calculo.find((m: { codigo: string; preco?: number; unidade?: string; descricao?: string }) => m.codigo === codigo_novo);
              if (match) {
                updatePayload.valorUnit = Number(match.preco) || 0;
                updatePayload.und = match.unidade || '-';
                if (match.descricao) updatePayload.descricao = match.descricao;
                updatePayload.base = 'SINAPI';
              }
            }

            updateRowById(id, updatePayload);

          } else if (payload.status === 'erro') {
            console.error(`[SSE] Erro no item ${payload.id}: ${payload.mensagem}`);
            updateRowById(payload.id, {
              ai_status: 'ERRO DE PROCESSAMENTO',
              ai_parecer_tecnico: payload.mensagem,
            });

          } else if (payload.status === 'lote_concluido') {
            useBudgetStore.getState().setIsProcessing(false);
            useBudgetStore.getState().setProcessingStatusText('Analise Completa!');
            console.log(`[SSE] Lote de ${payload.total} itens processado!`);
          }

        } catch (e) {
          console.error('[SSE] Erro ao traduzir os pacotes do Redis:', e);
        }
      },

      onerror: () => {
        console.warn('[SSE] Desconexao/Erro. fetch-event-source fara retry automatico...');
      },
    });

    return () => {
      console.log(`[SSE] Encerrando conexao (Planilha: ${planilhaId})`);
      abortControllerRef.current?.abort();
    };
  }, [planilhaId, updateRowById]);
}
```

---

### S8 — Checklist de Verificacao

- `[ ]` `npm install @microsoft/fetch-event-source` executado
- `[ ]` `setTableData` faz diff real — editar 1 row nao marca todas as 5.000 como dirty
- `[ ]` `clearBudget` seta `isDirty: false` e `planilhaId: null`
- `[ ]` Filtro de `processarOrcamentoIA` nao inclui `PROCESSANDO`
- `[ ]` `useSseListener.ts` usa `fetchEventSource` com `Last-Event-ID` e AbortController
- `[ ]` Frontend compila sem erros TypeScript
- `[ ]` Editar 1 celula em planilha de 100 linhas -> apenas 1 linha vai ao `/save-linhas`
- `[ ]` Clicar em "Limpar Orcamento" -> nenhuma requisicao ao `/save-linhas`

---

## 🟠 [S9] Sprint 9 — Hardening e Qualidade

**Objetivo:** Eliminar achados medios e baixos: guard de deploy, allowlist SQL, consolidacao de seguranca e timeout no cliente OpenAI.

**Arquivos tocados neste sprint:**
- `backend/main.py`
- `backend/core/security.py` ← **NOVO**
- `backend/core/ai_client.py`
- `backend/modules/shared/sinapi_search.py`
- `backend/modules/auth/routes.py`
- `backend/modules/orcamento/routes.py`

---

### S9.T1 — Criar `core/security.py` (DRY para autenticacao)

**Criar** `backend/core/security.py`:

```python
# backend/core/security.py
"""
Dependencias de seguranca compartilhadas entre todos os modulos FastAPI.
Elimina duplicacao de verify_proxy_secret entre auth/routes.py e orcamento/routes.py.
"""
from fastapi import Header, HTTPException
from core.config import settings


async def verify_proxy_secret(x_api_secret: str = Header(...)):
    """Verifica que a requisicao vem do Proxy Next.js interno (nao do browser)."""
    if x_api_secret != settings.API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Acesso nao autorizado")
    return x_api_secret


async def get_current_tenant(x_tenant_id: str = Header(None)):
    """Extrai o Tenant ID do header injetado pelo middleware Next.js."""
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail="Sessao Expirada ou Tenant Nao Encontrado")
    return x_tenant_id
```

**Editar** `backend/modules/auth/routes.py`:
- Adicionar `from core.security import verify_proxy_secret, get_current_tenant`
- Remover as definicoes locais de `verify_proxy_secret` e `get_current_tenant`

**Editar** `backend/modules/orcamento/routes.py`:
- Adicionar `from core.security import verify_proxy_secret, get_current_tenant`
- Remover as definicoes locais de `verify_proxy_secret` e `get_current_tenant`

---

### S9.T2 — Guard de `WEB_CONCURRENCY` no Lifespan

**Editar** `backend/main.py`. Adicionar `import os` no topo se ausente.

Adicionar NO INICIO do `lifespan`, antes de `await init_db_pool()`:

```python
    # Guard de deploy: semaforo asyncio nao e distribuido entre processos
    workers = int(os.environ.get("WEB_CONCURRENCY", 1))
    if workers > 1:
        raise RuntimeError(
            f"OrceIA detectou WEB_CONCURRENCY={workers}. "
            "Use WEB_CONCURRENCY=1 e escale via replicas de container (Cloud Run)."
        )
```

---

### S9.T3 — Allowlist de Tabela SQL em `sinapi_search.py`

**Editar** `backend/modules/shared/sinapi_search.py`.

Localizar:
```python
    tabela = "sinapi_composicoes" if tipo == "composicoes" else "sinapi_insumos"
```

Substituir por:
```python
    TABELAS_VALIDAS: dict[str, str] = {
        "composicoes": "sinapi_composicoes",
        "insumos": "sinapi_insumos",
    }
    tabela = TABELAS_VALIDAS.get(tipo)
    if tabela is None:
        raise ValueError(f"Tipo de busca SINAPI invalido: '{tipo}'. Aceitos: {list(TABELAS_VALIDAS.keys())}")
```

---

### S9.T4 — Adicionar Timeout ao Cliente OpenAI

**Editar** `backend/core/ai_client.py`. Substituir o conteudo completo:

```python
# backend/core/ai_client.py
"""
Singleton do cliente OpenAI assincrono.
- timeout=30.0: Previne requests travados em falhas de rede.
- max_retries=0: Tenacity em services.py controla o retry com backoff configurado.
"""
from openai import AsyncOpenAI
from core.config import settings

openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=30.0,
    max_retries=0,
)
```

---

### S9 — Checklist de Verificacao

- `[ ]` `core/security.py` criado com `verify_proxy_secret` e `get_current_tenant`
- `[ ]` `auth/routes.py` importa de `core.security` (sem funcoes locais duplicadas)
- `[ ]` `orcamento/routes.py` importa de `core.security` (sem funcoes locais duplicadas)
- `[ ]` `main.py` tem guard de `WEB_CONCURRENCY` no lifespan
- `[ ]` `sinapi_search.py` usa dicionario `TABELAS_VALIDAS`
- `[ ]` `ai_client.py` tem `timeout=30.0` e `max_retries=0`
- `[ ]` Servidor inicia normalmente com `WEB_CONCURRENCY=1`
- `[ ]` Servidor lanca `RuntimeError` com `WEB_CONCURRENCY=2`
- `[ ]` Todos os endpoints respondem (`/orcamento/health`, `/sinapi/search?q=teste`)

---

## Regras de Nao-Regressao (Inviolaveis em Todos os Sprints)

> Derivadas do Post-Mortem em `Manual_OrceIA.md`. Qualquer violacao e um BLOQUEADOR.

| Regra | Verificacao |
|-------|-------------|
| IDs nunca sao UUID | Colunas `id` e `id_planilha` sempre `VARCHAR(255)` |
| CoT nunca persiste no Supabase | `raciocinio_step_by_step` apenas em `print()` ou log efemero |
| CoT nunca viaja no payload SSE | Dicionario `resultado` nao tem chave `raciocinio_step_by_step` |
| Auto-save aponta para `/save-linhas` | `useAutoSave.ts` usa `save-linhas`, nunca `upsert-linhas` |
| `statement_cache_size=0` na pool asyncpg | `db.py` mantem esta configuracao intacta |
| Namespace Redis multi-tenant | `stream:{tenant_id}:planilha:{id}` — nunca sem `tenant_id` |
| `BACKEND_API_URL` sem `NEXT_PUBLIC_` | Variavel server-side apenas |
| `return_exceptions=True` no `gather` | `asyncio.gather(*tasks, return_exceptions=True)` |
| Modulo `orcamento/` nao importa de `sinapi/` | Hierarquia DDD preservada |
| Proxy nao expoe `API_SECRET_KEY` | Apenas `process.env.API_SECRET_KEY` (sem `NEXT_PUBLIC_`) |

---

## Navegacao do Projeto (Atualizada)

- **Regras universais de IA:** `.agents/rules/GEMINI.md`
- **Regras de Frontend:** `.agents/rules/02_frontend.md`
- **Regras de Backend:** `.agents/rules/03_backend.md`
- **Contexto arquitetural:** `AI_Onboarding.md`
- **Blueprint de construcao:** `Manual_OrceIA.md`
- **Roadmap de produto (Sprints 1-5):** `Master_Plan.md`
- **Plano de refatoracao (Sprints 6-9):** `Refactor_Plan.md` <- **este arquivo**
- **Spec da Sprint 5 (PDFs):** `Plano_AuditorIA.md`
