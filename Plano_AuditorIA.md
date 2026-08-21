# Resumo Arquitetural - Feature de Auditoria Documental (AuditorIA)

Este documento sumariza a visão técnica e arquitetural para a implementação da nova feature de análise de memoriais descritivos e projetos no OrceIA.

## 1. Visão Geral da Feature
O objetivo é criar uma ferramenta capaz de **auditar orçamentos terceirizados cruzando os itens da planilha com as especificações em PDF (Memoriais Descritivos)**. A IA não apenas apontará inconsistências (como downgrades de materiais), mas fornecerá **rastreabilidade absoluta**, citando a página e o trecho exato do PDF que embasa a crítica.

## 2. Relação com a Ferramenta Atual
A relação é **Complementar e Sequencial**:
- **Fase 1 (OrceIA Core):** Normaliza a planilha e checa os preços com o SINAPI (o que já fazemos hoje).
- **Fase 2 (AuditorIA):** Lê o PDF e cruza com a planilha da Fase 1 para garantir que a especificação técnica cobrada é exatamente a mesma exigida no edital.

## 3. Arquitetura Proposta: Feature-Sliced Design (DDD)
Para evitar que a complexidade do processamento de PDFs quebre o motor de cálculo do SINAPI (regressão), adotaremos a separação rigorosa de domínios em pastas isoladas.

### Backend (Python/FastAPI)
Isolamento em módulos:
```text
backend/
├── modules/
│   ├── orcamento/           # Lida com SINAPI, Busca Híbrida (RRF) e Preços
│   └── auditoria/           # Lida com LlamaParse/Vision, Pinecone isolado e Agente de Texto
```

### Frontend (React/Next.js)
Isolamento de Views e Estado:
```text
frontend/src/
├── features/
│   ├── budget-copilot/      # Tabela de preços a 60FPS, Zustand (useBudgetStore)
│   └── document-auditor/    # View Split-Screen, Leitor de PDF, Zustand (useAuditStore)
```

## 4. Infraestrutura e IA
- **Ingestão Multimodal:** Substituição de OCR básico por Modelos de Visão (Claude 3.5 Sonnet / GPT-4o) ou LlamaParse para extrair tabelas e textos estruturados.
- **Banco Vetorial (Pinecone):** Uso de **Namespaces Dinâmicos** (ex: `projeto_123`) para isolar o escopo de busca, garantindo que o memorial de uma obra não influencie outra.
- **Auditoria Linha a Linha (Map-Reduce):** Processamento assíncrono em lote. O Agente de IA lê o item da planilha, busca os trechos relevantes no Pinecone e retorna um JSON (Structured Outputs) acusando divergências.
- **Server-Sent Events (SSE):** O resultado da auditoria de cada linha é "cuspido" em tempo real para a interface, impedindo timeouts no Cloud Run.

## 5. Complexidade e Riscos
- **Grau de Complexidade: Alto.** Exige refino em engenharia de prompt, chunking semântico e manipulação de arquivos não estruturados (PDFs complexos).
- **Risco de Quebra (Regressão): Baixo.** A separação estrita de pastas (features independentes) e o uso de namespaces isolados no banco de dados blindam o sistema atual contra falhas da nova feature.

## 6. Próximos Passos Recomendados
A fundação de infraestrutura já foi validada (`audit_batch.py`). O próximo passo é focar na **Ingestão e Extração Multimodal**.
1. **Refatoração (DDD):** Executar a tarefa 5.0 do Master Plan para isolar o core de orçamento (`backend/modules/orcamento`).
2. **Script de PoC Isolado (`scripts/poc_ingestao_pdf.py`):**
   - Configurar LlamaParse (ou Claude 3.5 Sonnet Vision).
   - Ingerir 1 Caderno de Encargos em PDF de teste.
   - Criar um namespace dinâmico de teste (`projeto_poc`) no Pinecone e vetorizar o texto extraído.
3. **Auditoria Lexical:** Testar a busca semântica cruzando um item da planilha contra os embeddings do PDF e validar o custo de tokens/acurácia do Agente Auditor.
