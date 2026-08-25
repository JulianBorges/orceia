# OrceIA V3 — Regras do Frontend (Next.js 14 + Zustand)

> Lido automaticamente quando a IA modifica arquivos em `frontend/`.
> Para regras globais: `GEMINI.md`. Para arquitetura: `01_core_architecture.md`.

---

## 1. Gerenciamento de Estado — Zustand (Obrigatório)

**❌ NUNCA use React Context** para estado global. O projeto usa **Zustand** exclusivamente.

### Mutações Cirúrgicas O(1) — Obrigatórias
Sempre use os métodos especializados da store. **NUNCA** recrie o array inteiro para uma operação pontual:

```typescript
// ✅ CORRETO — mutação cirúrgica O(1)
addRow(index, newRow)
deleteRow(id)           // Propaga DELETE ao banco + remove do dirtyRowIds
updateRow(index, data)
updateRowById(id, data) // Usado pelo SSE listener para atualizar células vindas da IA
updateData(rowIndex, columnId, value)

// ✅ Para carga inicial (upload de planilha) — NÃO marca dirty
loadTableData(data)     // Use este no UploadPlanilha.tsx — não dispara auto-save

// ✅ Para substituição total com dirty tracking
setTableData(data)      // Marca tudo como dirty — use apenas para operações do usuário

// ❌ NUNCA faça isso
setTableData(tableData.map(row => row.id === id ? {...row, campo: valor} : row))
```

### Estado de Sincronização (Dirty Tracking)
```typescript
isDirty: boolean          // true se há rows para salvar
dirtyRowIds: string[]     // IDs das linhas modificadas pelo usuário (não pelo upload)
```

- `deleteRow` **NÃO** adiciona o ID ao `dirtyRowIds` — deleções têm canal próprio (DELETE endpoint)
- `loadTableData` zera `dirtyRowIds` e `isDirty` — upload não dispara auto-save

---

## 2. Auto-Save — Regras Críticas

```typescript
// ✅ CORRETO: Auto-save aponta para /save-linhas (apenas DB, sem IA)
fetch('/api/proxy/orcamento/save-linhas', { method: 'POST', body: JSON.stringify({ linhas: dirtyRows }) })

// ❌ PROIBIDO: Auto-save NUNCA aponta para /upsert-linhas (aciona IA)
fetch('/api/proxy/orcamento/upsert-linhas', ...) // BUG #5 — não repita
```

O auto-save deve ser disparado **somente** pelos métodos que marcam `isDirty = true`:
- `updateData`, `updateRow`, `updateRowById`, `addRow`, `setTableData`

**Nunca** deve ser disparado por:
- `loadTableData` (upload inicial)
- `deleteRow` (tem canal próprio via DELETE endpoint)
- Atualizações vindas do SSE (que já foram processadas pelo backend)

---

## 3. Proxy Edge — Segurança

```typescript
// ✅ CORRETO: variável server-side
const backendUrl = process.env.BACKEND_API_URL

// ❌ PROIBIDO: expõe URL ao browser — BUG #8
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL

// ✅ CORRETO: falha rápida se env não configurada
const apiSecret = process.env.API_SECRET_KEY
if (!apiSecret) return NextResponse.json({ error: 'Configuração inválida' }, { status: 500 })

// ❌ PROIBIDO: fallback hardcoded — vulnerabilidade de segurança
const apiSecret = process.env.API_SECRET_KEY || 'sk-qualquer-coisa'
```

---

## 4. Tipagem — Union Types Obrigatórios

```typescript
// ✅ CORRETO: ai_status tem valores controlados
export type AIStatus =
  | 'ACEITO' | 'REJEITADO' | 'RESSALVA' | 'PENDENTE'
  | 'PROCESSANDO' | 'SUBSTITUIDO' | 'MEMÓRIA HUMANA'
  | 'CACHE_REDIS' | 'ERRO DE PROCESSAMENTO';

// ❌ PROIBIDO: string livre permite valores inválidos
ai_status?: string
```

---

## 5. Virtualização e Dropdowns

A tabela renderiza **5.000+ linhas** via `@tanstack/react-virtual`. Elementos de sobreposição como dropdowns e tooltips **não podem ser filhos DOM** da linha virtualizada (serão recortados pelo `overflow: hidden`).

```typescript
// ✅ CORRETO para dropdowns dentro da tabela virtualizada
import { createPortal } from 'react-dom'
createPortal(<Dropdown />, document.body)

// ❌ INCORRETO: dropdown fica invisível ou cortado dentro da célula
<TableCell>
  <Dropdown /> {/* Será cortado pelo container virtualizado */}
</TableCell>
```

---

## 6. SSE Listener

```typescript
// ✅ CORRETO: planilhaId pode ser null antes da planilha ser criada
export function useSseListener(planilhaId: string | null)

// O hook deve verificar antes de abrir o EventSource:
useEffect(() => {
  if (!planilhaId) return
  const es = new EventSource(`/api/proxy/orcamento/stream/${planilhaId}`)
  // ...
}, [planilhaId])
```

---

## 7. IDs de Linhas (Frontend)

```typescript
// ✅ CORRETO: ID gerado no frontend com Date.now()
const newRow: BudgetItem = {
  id: `serv_${Date.now()}`,
  // ...
}

// ❌ PROIBIDO: crypto.randomUUID() pode gerar conflito com o asyncpg se não for VARCHAR
// (Use Date.now() para garantir formato de string simples e legível)
```

---

## 8. Estrutura de Arquivos

```
frontend/src/
├── app/
│   ├── api/
│   │   ├── auth/login/route.ts    ← Valida tenant no backend ANTES de setar cookie
│   │   └── proxy/[...path]/route.ts ← Edge proxy server-side
│   ├── login/page.tsx
│   └── page.tsx                   ← Dashboard principal
├── components/
│   ├── BudgetTable.tsx            ← Tabela virtualizada principal
│   ├── UploadPlanilha.tsx         ← Usa loadTableData() (não setTableData)
│   └── ...
├── hooks/
│   └── useSseListener.ts          ← Escuta SSE, chama updateRowById
├── store/
│   └── useBudgetStore.ts          ← Store Zustand (única fonte de verdade)
└── utils/
    └── budgetUtils.ts             ← BudgetItem, AIStatus, recalculateNumbers
```
