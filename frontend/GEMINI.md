# OrceIA V3 — Regras de Frontend (Next.js / React / Zustand)

> Regras específicas do frontend. Lidas automaticamente ao editar qualquer arquivo em `frontend/`.
> Herdam e complementam as regras da raiz (`GEMINI.md`).

---

## 1. Estado Global — Zustand é a Lei (Sem Exceções)

- ✅ Use **exclusivamente** Zustand para estado compartilhado entre componentes
- ❌ **PROIBIDO** `React Context` para qualquer estado global — causa re-renders em cascata e destrói os 60 FPS
- ❌ **PROIBIDO** Redux, Jotai ou qualquer outra lib de estado sem aprovação explícita

### Mutações O(1) — Obrigatórias

**NUNCA** sobrescreva a tabela inteira para fazer edições:
- ❌ `setTableData([...tableData, novaLinha])` — suja 100% das linhas no Auto-Save
- ✅ `addRow(novaLinha)` — adiciona cirurgicamente
- ✅ `deleteRow(id)` — remove cirurgicamente
- ✅ `updateRow(id, campos)` — atualiza cirurgicamente

Dentro da Store, `recalculateNumbers` deve fazer **Shallow Compare** entre a array antiga e a nova para capturar apenas os IDs alterados (inclusive pais afetados) e adicioná-los cirurgicamente no `dirtyRowIds`.

---

## 2. Auto-Save — Rota Correta é Inviolável

| Rota | Propósito | Aciona IA? |
|------|-----------|------------|
| `/save-linhas` | Persistência B2B no Supabase | ❌ Nunca |
| `/upsert-linhas` | Gatilho da IA (OpenAI) | ✅ Sempre |

- ✅ **Auto-Save (`useAutoSave.ts`) aponta SOMENTE para `/save-linhas`**
- ❌ **JAMAIS direcionar o Auto-Save para `/upsert-linhas`** — isso reativaria a IA e sobrescreveria escolhas manuais do usuário

### Race Condition — Fila Cirúrgica
Após receber HTTP 200 do Auto-Save, **nunca limpe a fila inteira**:
- ❌ `set({ dirtyRowIds: [] })` — apaga edições feitas durante o request
- ✅ Filtrar apenas os IDs confirmados: `set({ dirtyRowIds: prev.filter(id => !confirmedIds.includes(id)) })`

---

## 3. DOM Virtualization (`@tanstack/react-virtual`) — Regras de CSS

A tabela usa virtualização de DOM. Apenas linhas no viewport existem no DOM.

- ✅ Use `transform: translateY(${start}px)` e `position: absolute` para posicionar linhas virtualizadas
- ❌ Nunca use `margin-top` ou `padding-top` para compensar o scroll — quebra a virtualização

### Dropdowns e Componentes Flutuantes — Portal Obrigatório

O container do `@tanstack/react-virtual` usa `overflow: hidden`. Dropdowns renderizados dentro do fluxo da célula serão **cortados**.

- ✅ Envolva **sempre** com `createPortal(..., document.body)` para flutuar por cima da tabela
- ❌ Nunca renderize Autocomplete, Tooltip ou Dropdown diretamente no fluxo da célula virtualizada

### Modais Pesados — Fora do Motor de Renderização

- ✅ Modais como `MemoryModal`, `CompositionDetailsModal` devem ser componentes **isolados fora** da árvore de renderização da tabela
- ❌ Nunca importe e renderize modais pesados dentro de componentes de célula (`BudgetTableCells.tsx`)

---

## 4. Segurança — Variáveis de Ambiente e Proxy

### Regra do `BACKEND_API_URL`
```
# ✅ CORRETO
BACKEND_API_URL=https://meu-backend.run.app

# ❌ ERRADO — prefixo NEXT_PUBLIC_ expõe a URL no bundle do cliente
NEXT_PUBLIC_BACKEND_API_URL=...

# ❌ ERRADO — sufixo /api quebra o roteamento dinâmico do proxy
BACKEND_API_URL=https://meu-backend.run.app/api
```

### Fluxo de Comunicação (Imutável)
```
Client (React) → /api/proxy (Next.js Server-Side) → Backend FastAPI
```
- A chave `API_SECRET_KEY` é inserida nos headers **dentro do proxy** — nunca no client
- O `X-Tenant-ID` vem do `middleware.ts` via Cookie HttpOnly — **nunca** trafegue IDs de tenant em payloads JSON

---

## 5. Performance — Função Acima da Forma (Anti-Gambiarras Visuais)

- ❌ **Nunca** sacrifique 60 FPS por efeitos visuais: sem animações de entrada lentas, sem efeitos dominó, sem renderizações em cascata
- ✅ A UI deve ser utilitária, instantânea e suportar 5.000+ itens sem engasgos
- ✅ Matemática de preço, BDI e quantidades rodam **100% no cliente via Zustand** — nenhum endpoint backend para somar/multiplicar valores de interface

---

## 6. TypeScript — Pragmatismo Controlado

- A compilação tolera erros de tipagem (`any`) para velocidade de MVP
- **Exceção de Ouro:** Para injetar dependências complexas (como métodos na `TableMeta` do TanStack Table), use **Module Augmentation** (`declare module`) no topo do arquivo — **nunca** `(info as any)`. Isso mantém o IntelliSense intacto.
