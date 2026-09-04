# AuditorIA — Pipeline Bidirecional de Memoriais Descritivos

> **Status: IMPLEMENTADO (Sprint 5 concluida em setembro/2026)**
> Este documento descreve a arquitetura real do modulo `backend/modules/auditoria/`.
> Para contexto de produto e historico de decisoes, veja `AI_Onboarding.md`.

---

## 1. O que o Modulo Faz

O modulo `auditoria/` viabiliza dois modos distintos de uso de Memoriais Descritivos em PDF:

| Modo | Trigger | Descricao |
|------|---------|-----------|
| **Geracao** | `projeto_id` presente no payload de cada linha | O trecho do memorial mais relevante e injetado no prompt do Agente Engenheiro como especificacao tecnica. Reduz alucinacoes de familia de servico. |
| **Auditoria** | Botao "Auditar Orcamento" (visivel quando memorialId existe) | Cruza cada linha do orcamento contra o memorial e emite um laudo CONFORME/DIVERGENTE/SEM_REFERENCIA via SSE. |

Os dois modos compartilham 100% do mesmo pipeline de ingestao (Etapa A abaixo).

---

## 2. Fluxo de Ingestao de PDF (Compartilhado)

```
POST /auditoria/ingerir-memorial (multipart/form-data)
  -> pypdf: extrai texto pagina por pagina
  -> chunking semantico: divide por paragrafos (separador: dois newlines)
  -> filtro: descarta chunks < 50 caracteres
  -> text-embedding-3-small: gera embeddings em lote (max 100 por chamada)
  -> Pinecone upsert: namespace memorial:{tenant_id}:{projeto_id}
     metadados: { texto: chunk, projeto_id, tenant_id }
  -> retorna { projeto_id, chunks_gerados, status: "ok" }
```

**Namespace isolado por tenant e projeto:** garante que o memorial de uma obra nao influencie outra.
**projeto_id:** gerado automaticamente como `str(uuid4())` se nao informado no request.

---

## 3. Modo Geracao (Injecao de Contexto)

Ativado automaticamente quando `projeto_id` esta presente na linha enviada ao `/upsert-linhas`.

```python
# Em orcamento/services.py
if linha.projeto_id:
    trechos = await buscar_contexto_memorial(linha.descricao, tenant_id, linha.projeto_id)
    if trechos:
        contexto_memorial = "\n".join(trechos)
        # Injetado no prompt antes do Agente Engenheiro
```

O Agente Engenheiro recebe o trecho no prompt como:
```
[Especificacao do Memorial Descritivo]
{trecho_relevante}
```

Fallback silencioso: se `score < 0.65` na busca Pinecone, o fluxo continua sem memorial.

---

## 4. Modo Auditoria (Laudo de Conformidade SSE)

```
POST /auditoria/auditar-planilha
  Body: { projeto_id, linhas: [{id, descricao, codigo?, status_ia?}] }
  -> asyncio.Semaphore(5): controla concorrencia, protege rate limit OpenAI
  -> para cada linha (em paralelo, controlado pelo semaforo):
       buscar_contexto_memorial(descricao, tenant_id, projeto_id)
       -> sem trechos: retorna SEM_REFERENCIA (sem custo de IA)
       -> com trechos: auditar_item_contra_memorial() [Structured Outputs]
            schema ResultadoConformidade:
              raciocinio_auditoria: str (EFEMERO - apenas log)
              status_conformidade: Literal["CONFORME","DIVERGENTE","SEM_REFERENCIA"]
              trecho_memorial: Optional[str]
              justificativa: str
  -> SSE: data: {"status":"sucesso","dados":{id,status_conformidade,justificativa,trecho_memorial}}
  -> SSE: data: {"status":"auditoria_concluida","total":N}
```

**Mapeamento de status no Frontend (useBudgetStore.ts):**
| status_conformidade | ai_status na tabela |
|---------------------|---------------------|
| CONFORME | ACEITO |
| DIVERGENTE | RESSALVA |
| SEM_REFERENCIA | PENDENTE |

---

## 5. Componentes de UI

- `MemorialUploadButton.tsx`: botao multiestado (idle/uploading/success/error). Em `success`, exibe "Memorial (N trechos)". Clique para substituir.
- `AuditorButton.tsx`: renderiza `null` se `memorialId` nao existe no Zustand. Aparece apenas quando memorial esta carregado.
- `memorialId` e `planilhaId` sao persistidos no Zustand `persist` — sobrevivem a refresh de pagina.

---

## 6. Evolucoes Futuras

- **Citacao de pagina exata:** adicionar campo `page_number` nos metadados Pinecone durante a ingestao.
- **Chunking robusto para PDFs mal formados:** fallback por sentencas quando o separador de dois newlines nao funcionar.
- **Suporte a DOCX:** adicionar `python-docx` como parser alternativo ao pypdf.
