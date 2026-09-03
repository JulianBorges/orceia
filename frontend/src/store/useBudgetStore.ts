import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { BudgetItem, recalculateNumbers, moveRowOrBlock } from '../utils/budgetUtils';

interface BudgetState {
  tableData: BudgetItem[];
  bdi: number;
  title: string;
  isProcessing: boolean;
  uploadProgress: number | null;
  processingStatusText: string;
  processedItemsCount: number;
  totalItemsToProcess: number;
  currentAnalyzingItemName: string;
  isDirty: boolean;
  dirtyRowIds: string[];
  setIsDirty: (val: boolean) => void;
  incrementProcessedItemsCount: () => void;
  addDirtyRow: (id: string) => void;
  clearDirtyRows: (idsToClear: string[]) => void;
  setTableData: (data: BudgetItem[] | ((prev: BudgetItem[]) => BudgetItem[])) => void;
  /** Carga inicial (upload). Não marca linhas como dirty — evita auto-save desnecessário. */
  loadTableData: (data: BudgetItem[]) => void;
  setBdi: (bdi: number) => void;
  setTitle: (title: string) => void;
  setIsProcessing: (isProcessing: boolean) => void;
  setUploadProgress: (progress: number | null) => void;
  setProcessingStatusText: (text: string) => void;
  setCurrentAnalyzingItemName: (name: string) => void;
  setProcessedItemsCount: (count: number) => void;
  updateData: <K extends keyof BudgetItem>(rowIndex: number, columnId: K, value: BudgetItem[K]) => void;
  updateRow: (rowIndex: number, newRowData: Partial<BudgetItem>) => void;
  updateRowById: (id: string, newRowData: Partial<BudgetItem>) => void;
  updateItemPosition: (oldIndex: number, newNumberText: string) => void;
  addRow: (index: number, newRow: BudgetItem) => void;
  deleteRow: (id: string) => void;
  clearBudget: () => void;
  memorizeHumanFeedback: (termoOriginal: string, codigoEscolhido: string, parecer: string) => Promise<void>;
  
  // Novos métodos de Integração Funcional e Upload
  planilhaId: string | null;
  setPlanilhaId: (id: string | null) => void;
  // Memorial Descritivo (Modo Geração / Modo Auditoria)
  memorialId: string | null;
  setMemorialId: (id: string | null) => void;
  processarOrcamentoIA: () => Promise<void>;
  estruturarEAP: (data: BudgetItem[], isAppend?: boolean) => Promise<BudgetItem[]>;
}

export const useBudgetStore = create<BudgetState>()(
  persist(
    (set, get) => ({
      tableData: [],
      bdi: 25.0,
      title: 'Orçamento Base',
      isProcessing: false,
      uploadProgress: null,
      processingStatusText: '',
      processedItemsCount: 0,
      totalItemsToProcess: 0,
      currentAnalyzingItemName: '',
      isDirty: false,
      dirtyRowIds: [],
      planilhaId: null,
      memorialId: null,

      setPlanilhaId: (id) => set({ planilhaId: id }),
      setMemorialId: (id) => set({ memorialId: id }),
      setIsDirty: (isDirty) => set({ isDirty }),
      incrementProcessedItemsCount: () => set((state) => ({ processedItemsCount: state.processedItemsCount + 1 })),
      setCurrentAnalyzingItemName: (name) => set({ currentAnalyzingItemName: name }),
      addDirtyRow: (id) => set((state) => ({ 
          dirtyRowIds: state.dirtyRowIds.includes(id) ? state.dirtyRowIds : [...state.dirtyRowIds, id],
          isDirty: true
      })),
      clearDirtyRows: (idsToClear) => set((state) => {
        const remainingIds = state.dirtyRowIds.filter(id => !idsToClear.includes(id));
        return { dirtyRowIds: remainingIds, isDirty: remainingIds.length > 0 };
      }),

      loadTableData: (data) => set({
        tableData: recalculateNumbers(data),
        dirtyRowIds: [],
        isDirty: false,
      }),

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

      setBdi: (bdi) => set({ bdi }),
      setTitle: (title) => set({ title }),
      setIsProcessing: (isProcessing) => set({ isProcessing }),
      setUploadProgress: (uploadProgress) => set({ uploadProgress }),
      setProcessingStatusText: (processingStatusText) => set({ processingStatusText }),
      setProcessedItemsCount: (processedItemsCount) => set({ processedItemsCount }),

      updateData: (rowIndex, columnId, value) => set((state) => {
        const newData = state.tableData.map((row, index) => {
          if (index === rowIndex) {
            const newRow = { ...row, [columnId]: value };
            if (columnId === 'descricao' && value !== row.descricao) {
                if (!row.descricao_legada) {
                    newRow.descricao_legada = row.descricao;
                }
            }
            if (columnId === 'quant' || columnId === 'valorUnit') {
              newRow.total = Number(newRow.quant) * Number(newRow.valorUnit);
            }
            return newRow;
          }
          return row;
        });
        const recalculatedData = recalculateNumbers(newData);
        const newlyModifiedIds = recalculatedData
            .filter((row, idx) => row !== state.tableData[idx])
            .map(row => row.id);
        const newDirty = Array.from(new Set([...state.dirtyRowIds, ...newlyModifiedIds]));
        return { tableData: recalculatedData, dirtyRowIds: newDirty, isDirty: true };
      }),

      updateRow: (rowIndex, newRowData) => set((state) => {
        const newData = state.tableData.map((row, index) => {
          if (index === rowIndex) {
            const newRow = { ...row, ...newRowData };
            if ('descricao' in newRowData && newRowData.descricao !== row.descricao) {
                if (!row.descricao_legada && !newRowData.descricao_legada) {
                    newRow.descricao_legada = row.descricao;
                }
            }
            if ('quant' in newRowData || 'valorUnit' in newRowData) {
              newRow.total = Number(newRow.quant) * Number(newRow.valorUnit);
            }
            if ('codigo' in newRowData && !('ai_status' in newRowData)) {
              newRow.ai_status = 'SUBSTITUIDO';
              newRow.ai_parecer_tecnico = 'Item substituído manualmente pelo usuário.';
            }
            return newRow;
          }
          return row;
        });
        const recalculatedData = recalculateNumbers(newData);
        const newlyModifiedIds = recalculatedData
            .filter((row, idx) => row !== state.tableData[idx])
            .map(row => row.id);
        const newDirty = Array.from(new Set([...state.dirtyRowIds, ...newlyModifiedIds]));
        return { tableData: recalculatedData, dirtyRowIds: newDirty, isDirty: true };
      }),

      updateRowById: (id, newRowData) => set((state) => {
        let wasModified = false;
        const newData = state.tableData.map((row) => {
          if (row.id === id) {
            wasModified = true;
            const newRow = { ...row, ...newRowData };
            if ('descricao' in newRowData && newRowData.descricao !== row.descricao) {
                if (!row.descricao_legada && !newRowData.descricao_legada) {
                    newRow.descricao_legada = row.descricao;
                }
            }
            if ('quant' in newRowData || 'valorUnit' in newRowData) {
              newRow.total = Number(newRow.quant) * Number(newRow.valorUnit);
            }
            return newRow;
          }
          return row;
        });
        
        // Atualizações que vêm do SSE (backend) não devem sujar a planilha para reenvio (loop infinito)
        return wasModified ? { tableData: recalculateNumbers(newData) } : {};
      }),

      updateItemPosition: (oldIndex, newNumberText) => set((state) => {
        const parts = String(newNumberText).split('.');
        const targetMacro = parseInt(parts[0], 10);
        const targetSub = parts.length > 1 ? parseInt(parts[1], 10) : 0;
        
        if (isNaN(targetMacro)) return state;
        
        let macroCounter = 0;
        let subCounter = 0;
        let targetIndex = -1;
        
        for (let i = 0; i < state.tableData.length; i++) {
            if (state.tableData[i].is_macro_item) {
                macroCounter++;
                subCounter = 0;
            } else {
                subCounter++;
            }
            
            if (macroCounter === targetMacro && subCounter === targetSub) {
                targetIndex = i;
                break;
            }
        }
        
        if (targetIndex === -1) {
            for (let i = state.tableData.length - 1; i >= 0; i--) {
                let mCount = state.tableData.slice(0, i + 1).filter((d: BudgetItem) => d.is_macro_item).length;
                if (mCount === targetMacro) {
                    targetIndex = i;
                    break;
                }
            }
        }
        
        if (targetIndex === -1) return state;
        
        const newData = [...state.tableData];
        if (targetSub === 0 && !newData[oldIndex].is_macro_item) {
            newData[oldIndex] = { ...newData[oldIndex], is_macro_item: true, quant: 0, valorUnit: 0, total: 0, und: "-" };
        } else if (targetSub !== 0 && newData[oldIndex].is_macro_item) {
            newData[oldIndex] = { ...newData[oldIndex], is_macro_item: false, quant: 1 };
        }
        
        const movedData = moveRowOrBlock(newData, oldIndex, targetIndex);
        const newlyModifiedIds = movedData
            .filter((row, idx) => row !== state.tableData[idx])
            .map(row => row.id);
        const newDirty = Array.from(new Set([...state.dirtyRowIds, ...newlyModifiedIds]));
        return { tableData: movedData, dirtyRowIds: newDirty, isDirty: true };
      }),

      addRow: (index, newRow) => set((state) => {
        const rowToAdd = { ...newRow, descricao_legada: newRow.descricao || '' };
        const newData = [...state.tableData];
        newData.splice(index, 0, rowToAdd);
        const recalculatedData = recalculateNumbers(newData);
        
        const newlyModifiedIds = recalculatedData
            .filter((row, idx) => row !== state.tableData[idx] || row.id === rowToAdd.id)
            .map(row => row.id);
            
        const newDirty = Array.from(new Set([...state.dirtyRowIds, ...newlyModifiedIds]));
        return { tableData: recalculatedData, dirtyRowIds: newDirty, isDirty: true };
      }),

      deleteRow: (id) => set((state) => {
        const newData = state.tableData.filter(row => row.id !== id);
        const recalculatedData = recalculateNumbers(newData);

        // Propaga a deleção ao banco (fire-and-forget com proteção de erro)
        const { planilhaId } = state;
        if (planilhaId) {
          fetch('/api/proxy/orcamento/linhas', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: [id], id_planilha: planilhaId }),
          }).catch(e => console.error('[DELETE] Falha ao propagar deleção ao banco:', e));
        }

        // Remove o ID deletado do dirtyRowIds (ele não deve ser salvo via auto-save)
        const newlyModifiedIds = recalculatedData
            .filter(row => {
                const oldRow = state.tableData.find(r => r.id === row.id);
                return !oldRow || row !== oldRow;
            })
            .map(row => row.id);

        // Não inclui o `id` deletado no dirty — tem canal próprio (DELETE endpoint)
        const remainingDirty = state.dirtyRowIds.filter(d => d !== id);
        const newDirty = Array.from(new Set([...remainingDirty, ...newlyModifiedIds]));
        return { tableData: recalculatedData, dirtyRowIds: newDirty, isDirty: newDirty.length > 0 };
      }),

      clearBudget: () => set({
        tableData: [],
        title: 'Orçamento Base',
        bdi: 25.0,
        dirtyRowIds: [],
        isDirty: false,    // Nao ha nada para salvar — nao aciona o auto-save
        planilhaId: null,  // Remove o ID para evitar erro de FK em planilha inexistente
      }),

      memorizeHumanFeedback: async (termoOriginal: string, codigoEscolhido: string, parecer: string) => {
        try {
            await fetch('/api/proxy/orcamento/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    termo_original: termoOriginal,
                    codigo_escolhido: codigoEscolhido,
                    parecer: parecer
                })
            });
            console.log('[RLHF] Feedback humano salvo com sucesso.');
        } catch (e) {
            console.error('[RLHF] Erro ao salvar feedback humano', e);
        }
      },

      processarOrcamentoIA: async () => {
        const { tableData, planilhaId, memorialId } = get();
        if (!planilhaId) return;

        // Extrai apenas os itens folha, injetando o contexto do macro item pai
        let currentMacroName = '';
        const linhasParaProcessar: any[] = [];
        
        for (const row of tableData) {
            if (row.is_macro_item) {
                currentMacroName = row.descricao || '';
            } else if (
                row.descricao &&
                row.descricao.trim() !== '' &&
                // Nao reenvia itens em voo — prevencao de processamento duplo
                (!row.ai_status || row.ai_status === 'PENDENTE')
            ) {
                linhasParaProcessar.push({
                    id: row.id,
                    id_planilha: planilhaId,
                    descricao: row.descricao,
                    unidade: row.und,
                    quantidade: row.quant,
                    preco_unitario: row.valorUnit,
                    macro_item_context: currentMacroName || undefined,
                    projeto_id: memorialId || undefined,
                });
            }
        }

        if (linhasParaProcessar.length === 0) {
            set({ isProcessing: false, processingStatusText: 'Nenhum item válido para processar.' });
            return;
        }

        set({ 
            isProcessing: true, 
            processedItemsCount: 0, 
            totalItemsToProcess: linhasParaProcessar.length,
            currentAnalyzingItemName: 'Iniciando lote...',
            processingStatusText: 'Iniciando inteligência...' 
        });

        const CHUNK_SIZE = 100;
        let successCount = 0;

        set({ processingStatusText: `Enviando ${linhasParaProcessar.length} itens (lotes de ${CHUNK_SIZE})...` });

        try {
            // Envio fragmentado para evitar 'Payload Too Large' na Vercel e pico de RAM no backend
            for (let i = 0; i < linhasParaProcessar.length; i += CHUNK_SIZE) {
                const chunk = linhasParaProcessar.slice(i, i + CHUNK_SIZE);
                const res = await fetch('/api/proxy/orcamento/upsert-linhas', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ linhas: chunk })
                });
                
                if (res.ok) {
                    successCount += chunk.length;
                    set({ processingStatusText: `Enviados ${successCount}/${linhasParaProcessar.length} para background...` });
                } else {
                    console.error(`[IA] Falha ao enviar lote começando no índice ${i}`);
                }
            }
            
            if (successCount > 0) {
                set({ processingStatusText: `Todos os ${successCount} itens foram enfileirados. Aguardando SSE...` });
            } else {
                set({ isProcessing: false, processingStatusText: 'Erro ao iniciar o motor de IA.' });
            }
        } catch (e) {
            console.error('[IA] Falha ao acionar endpoint', e);
            set({ isProcessing: false, processingStatusText: 'Exceção na comunicação com o backend.' });
        }
      },

      estruturarEAP: async (data: BudgetItem[], isAppend = false) => {
        try {
            const res = await fetch('/api/proxy/eap/estruturar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    linhas: data.map(d => ({ 
                        id: d.id, 
                        descricao: d.descricao
                    })) 
                })
            });

            if (!res.ok) {
                throw new Error('Falha ao estruturar EAP');
            }

            const responseData = await res.json();
            
            // Cria um mapa com os dados originais para restaurar unidade, quant, valorUnit, etc.
            const originalMap = new Map<string, BudgetItem>();
            data.forEach(d => originalMap.set(d.id, d));
            
            const newData: BudgetItem[] = responseData.linhas.map((row: any) => {
                const original = row.id ? originalMap.get(row.id) : null;
                return {
                    id: row.id || crypto.randomUUID(),
                    item: row.item || '',
                    descricao: row.descricao,
                    descricao_legada: original ? original.descricao_legada : row.descricao,
                    und: original ? original.und : '-',
                    quant: original ? original.quant : 0,
                    valorUnit: original ? original.valorUnit : 0,
                    total: original ? original.total : 0,
                    is_macro_item: row.is_macro_item,
                    base: original ? original.base : '',
                    codigo: original ? original.codigo : '',
                    level: row.item ? row.item.split('.').length - 1 : 0
                };
            });

            if (isAppend) {
                const state = get();
                // append using setTableData so it triggers dirty state for saving
                state.setTableData([...state.tableData, ...newData]);
            } else {
                get().loadTableData(newData);
            }
            return newData;
        } catch (e) {
            console.error('[EAP] Erro ao estruturar EAP', e);
            throw e;
        }
      },
    }),
    {
      name: 'orcamento_data',
      partialize: (state) => ({ tableData: state.tableData, bdi: state.bdi, title: state.title }),
    }
  )
);
