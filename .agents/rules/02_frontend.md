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

// ❌ NUNCA faça isso (suja 100% das linhas no Auto-Save)
setTableData([...tableData, novaLinha])
setTableData(tableData.map(row => row.id === id ? {...row, campo: valor} : row))
```

### Estado de Sincronização (Dirty Tracking) e Race Conditions
- `isDirty: boolean` (true se há rows para salvar)
- `dirtyRowIds: string[]` (IDs das linhas modificadas pelo usuário)
- `deleteRow` **NÃO** adiciona o ID ao `dirtyRowIds` — deleções têm canal próprio.
- `loadTableData` zera `dirtyRowIds` e `isDirty` — upload não dispara auto-save.

**Race Condition (Fila Cirúrgica):**
Após receber HTTP 200 do Auto-Save, **nunca limpe a fila inteira**:
- ❌ `set({ dirtyRowIds: [] })` — apaga edições feitas durante o request.
- ✅ Filtrar apenas os IDs confirmados: `set({ dirtyRowIds: prev.filter(id => !confirmedIds.includes(id)) })`

---

## 2. Auto-Save — Regras Críticas

O auto-save deve ser disparado **somente** pelos métodos que marcam `isDirty = true` (ex: `updateData`, `addRow`, `setTableData`). Nunca pelo `loadTableData` ou `deleteRow`.

```typescript
// ✅ CORRETO: Auto-save aponta para /save-linhas (apenas DB, sem IA)
fetch('/api/proxy/orcamento/save-linhas', ...)

// ❌ PROIBIDO: Auto-save NUNCA aponta para /upsert-linhas (aciona IA)
fetch('/api/proxy/orcamento/upsert-linhas', ...) // BUG #5
```

---

## 3. DOM Virtualization e UI — Desempenho (60 FPS)

A tabela usa `@tanstack/react-virtual` para 5.000+ linhas.
- ✅ Use `transform: translateY(${start}px)` e `position: absolute` para posicionar linhas.
- ❌ Nunca use `margin-top` ou `padding-top` para compensar o scroll.

### Dropdowns, Tooltips e Modais
O container virtualizado usa `overflow: hidden`.
- ✅ **Componentes Flutuantes**: Envolva **sempre** com `createPortal(<Dropdown />, document.body)` para flutuar por cima da tabela.
- ❌ Nunca renderize no fluxo da célula (serão cortados).
- ✅ **Modais Pesados** (`MemoryModal`, `CompositionDetailsModal`): Devem ficar isolados fora da árvore da tabela. Nunca importe modais dentro de `BudgetTableCells.tsx`.

### Anti-Gambiarras Visuais
- ❌ Nunca sacrifique 60 FPS por efeitos visuais (sem animações lentas/em cascata).
- ✅ Matemática (preço, BDI) roda 100% no cliente via Zustand — nenhum request ao backend para somar.

---

## 4. Segurança — Proxy Edge

```typescript
// ✅ CORRETO: variável server-side
const backendUrl = process.env.BACKEND_API_URL

// ❌ PROIBIDO: expõe URL ao browser
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL

// ❌ PROIBIDO: sufixo /api quebra o roteamento
const backendUrl = "https://backend.run.app/api" 

// ✅ CORRETO: falha rápida se env não configurada
const apiSecret = process.env.API_SECRET_KEY
if (!apiSecret) return NextResponse.json({ error: 'Config.' }, { status: 500 })
// ❌ PROIBIDO: fallback hardcoded
const apiSecret = process.env.API_SECRET_KEY || 'sk-123'
```

---

## 5. Tipagem e TypeScript — Pragmatismo

- ✅ `AIStatus` deve usar valores controlados (Union Type `ACEITO | REJEITADO | ...`), nunca `string` livre.
- ✅ `planilhaId` em `useSseListener` deve ser `string | null` e checado no `useEffect`.
- ✅ **IDs de Linha**: Gerados no frontend via `serv_${Date.now()}`. Nunca `UUID`.
- ✅ O TS tolera erros de tipagem (`any`) para agilidade, **exceto** na injeção de métodos na `TableMeta` do TanStack Table, onde você deve usar **Module Augmentation** (`declare module`) no topo do arquivo. Nunca use `(info as any)`.
