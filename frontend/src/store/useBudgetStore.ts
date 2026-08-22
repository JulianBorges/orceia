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
  isDirty: boolean;
  dirtyRowIds: string[];
  setIsDirty: (val: boolean) => void;
  addDirtyRow: (id: string) => void;
  clearDirtyRows: () => void;
  setTableData: (data: BudgetItem[] | ((prev: BudgetItem[]) => BudgetItem[])) => void;
  setBdi: (bdi: number) => void;
  setTitle: (title: string) => void;
  setIsProcessing: (isProcessing: boolean) => void;
  setUploadProgress: (progress: number | null) => void;
  setProcessingStatusText: (text: string) => void;
  setProcessedItemsCount: (count: number) => void;
  updateData: <K extends keyof BudgetItem>(rowIndex: number, columnId: K, value: BudgetItem[K]) => void;
  updateRow: (rowIndex: number, newRowData: Partial<BudgetItem>) => void;
  updateRowById: (id: string, newRowData: Partial<BudgetItem>) => void;
  updateItemPosition: (oldIndex: number, newNumberText: string) => void;
  clearBudget: () => void;
  memorizeHumanFeedback: (termoOriginal: string, codigoEscolhido: string, parecer: string) => Promise<void>;
  
  // Novos métodos de Integração Funcional e Upload
  planilhaId: string | null;
  setPlanilhaId: (id: string | null) => void;
  processarOrcamentoIA: () => Promise<void>;
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
      isDirty: false,
      dirtyRowIds: [],
      planilhaId: null,

      setPlanilhaId: (id) => set({ planilhaId: id }),
      setIsDirty: (isDirty) => set({ isDirty }),
      addDirtyRow: (id) => set((state) => ({ 
          dirtyRowIds: state.dirtyRowIds.includes(id) ? state.dirtyRowIds : [...state.dirtyRowIds, id],
          isDirty: true
      })),
      clearDirtyRows: () => set({ dirtyRowIds: [], isDirty: false }),

      setTableData: (data) => set((state) => {
        const newData = typeof data === 'function' ? data(state.tableData) : data;
        return {
          tableData: newData,
          dirtyRowIds: newData.map(r => r.id), // Tudo é dirty quando o data inteiro muda
          isDirty: true
        };
      }),

      setBdi: (bdi) => set({ bdi }),
      setTitle: (title) => set({ title }),
      setIsProcessing: (isProcessing) => set({ isProcessing }),
      setUploadProgress: (uploadProgress) => set({ uploadProgress }),
      setProcessingStatusText: (processingStatusText) => set({ processingStatusText }),
      setProcessedItemsCount: (processedItemsCount) => set({ processedItemsCount }),

      updateData: (rowIndex, columnId, value) => set((state) => {
        let modifiedId = "";
        const newData = state.tableData.map((row, index) => {
          if (index === rowIndex) {
            modifiedId = row.id;
            const newRow = { ...row, [columnId]: value };
            if (columnId === 'quant' || columnId === 'valorUnit') {
              newRow.total = Number(newRow.quant) * Number(newRow.valorUnit);
            }
            return newRow;
          }
          return row;
        });
        const newDirty = modifiedId && !state.dirtyRowIds.includes(modifiedId) ? [...state.dirtyRowIds, modifiedId] : state.dirtyRowIds;
        return { tableData: recalculateNumbers(newData), dirtyRowIds: newDirty, isDirty: true };
      }),

      updateRow: (rowIndex, newRowData) => set((state) => {
        let modifiedId = "";
        const newData = state.tableData.map((row, index) => {
          if (index === rowIndex) {
            modifiedId = row.id;
            const newRow = { ...row, ...newRowData };
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
        const newDirty = modifiedId && !state.dirtyRowIds.includes(modifiedId) ? [...state.dirtyRowIds, modifiedId] : state.dirtyRowIds;
        return { tableData: recalculateNumbers(newData), dirtyRowIds: newDirty, isDirty: true };
      }),

      updateRowById: (id, newRowData) => set((state) => {
        let wasModified = false;
        const newData = state.tableData.map((row) => {
          if (row.id === id) {
            wasModified = true;
            const newRow = { ...row, ...newRowData };
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
        const newDirty = !state.dirtyRowIds.includes(movedData[targetIndex].id) ? [...state.dirtyRowIds, movedData[targetIndex].id] : state.dirtyRowIds;
        return { tableData: movedData, dirtyRowIds: newDirty, isDirty: true };
      }),

      clearBudget: () => set({ tableData: [], title: 'Orçamento Base', bdi: 25.0, dirtyRowIds: [], isDirty: true }),

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
            console.log('[RLHF] Feedback humano (tenant_alfa) salvo com sucesso!');
        } catch (e) {
            console.error('[RLHF] Erro ao salvar feedback humano', e);
        }
      },

      processarOrcamentoIA: async () => {
        const { tableData, planilhaId } = get();
        if (!planilhaId) return;

        set({ isProcessing: true, processedItemsCount: 0, processingStatusText: 'Iniciando inteligência...' });

        // Extrai apenas os itens folha (não-macro) que têm descrição para a IA orçar e que ainda não foram processados
        const linhasParaProcessar = tableData
          .filter(row => !row.is_macro_item && row.descricao && row.descricao.trim() !== '' && (!row.ai_status || row.ai_status === 'PENDENTE' || row.ai_status === 'PROCESSANDO'))
          .map(row => ({
            id: row.id,
            id_planilha: planilhaId,
            descricao: row.descricao,
            unidade: row.und,
            quantidade: row.quant,
            preco_unitario: row.valorUnit
          }));

        if (linhasParaProcessar.length === 0) {
            set({ isProcessing: false, processingStatusText: 'Nenhum item válido para processar.' });
            return;
        }

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
    }),
    {
      name: 'orcamento_data',
      partialize: (state) => ({ tableData: state.tableData, bdi: state.bdi, title: state.title }),
    }
  )
);
