/**
 * Testes unitários do useBudgetStore (Zustand)
 * Valida que as mutações cirúrgicas O(1) funcionam corretamente
 * e que o dirty tracking é preciso — especialmente após refatorações.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act } from '@testing-library/react';
import { useBudgetStore } from '@/store/useBudgetStore';
import { BudgetItem } from '@/utils/budgetUtils';

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

function makeItem(overrides: Partial<BudgetItem> = {}): BudgetItem {
  return {
    id: `serv_${Date.now()}_${Math.random()}`,
    item: '1.0',
    codigo: '',
    base: '',
    descricao: 'Serviço de teste',
    und: 'M2',
    quant: 10,
    valorUnit: 50,
    total: 500,
    is_macro_item: false,
    level: 1,
    ai_status: 'PENDENTE',
    ...overrides,
  };
}

// -----------------------------------------------------------------------
// Reset do store antes de cada teste
// -----------------------------------------------------------------------

beforeEach(() => {
  act(() => {
    useBudgetStore.setState({
      tableData: [],
      dirtyRowIds: [],
      isDirty: false,
      planilhaId: null,
      title: 'Orçamento Base',
      bdi: 25,
      isProcessing: false,
      uploadProgress: null,
      processingStatusText: '',
      processedItemsCount: 0,
    });
  });
  vi.restoreAllMocks();
});

// -----------------------------------------------------------------------
// loadTableData — Carga inicial sem dirty tracking
// -----------------------------------------------------------------------

describe('loadTableData', () => {
  it('carrega os dados sem marcar dirty', () => {
    const items = [makeItem(), makeItem(), makeItem()];

    act(() => {
      useBudgetStore.getState().loadTableData(items);
    });

    const state = useBudgetStore.getState();
    expect(state.tableData).toHaveLength(3);
    expect(state.isDirty).toBe(false);
    expect(state.dirtyRowIds).toHaveLength(0);
  });

  it('não deve disparar auto-save (dirtyRowIds vazio após upload)', () => {
    const items = [makeItem(), makeItem()];

    act(() => {
      useBudgetStore.getState().loadTableData(items);
    });

    // Nenhum ID sujo → auto-save não deve disparar
    expect(useBudgetStore.getState().dirtyRowIds).toEqual([]);
  });
});

// -----------------------------------------------------------------------
// setTableData — Substituição total marca dirty
// -----------------------------------------------------------------------

describe('setTableData', () => {
  it('marca todos os itens como dirty', () => {
    const items = [makeItem({ id: 'id_1' }), makeItem({ id: 'id_2' })];

    act(() => {
      useBudgetStore.getState().setTableData(items);
    });

    const state = useBudgetStore.getState();
    expect(state.isDirty).toBe(true);
    expect(state.dirtyRowIds).toContain('id_1');
    expect(state.dirtyRowIds).toContain('id_2');
  });
});

// -----------------------------------------------------------------------
// addRow — Adiciona sem sujar outras linhas
// -----------------------------------------------------------------------

describe('addRow', () => {
  it('adiciona a linha corretamente', () => {
    const existing = makeItem({ id: 'existing_1' });
    const newRow = makeItem({ id: 'new_row_1' });

    act(() => {
      useBudgetStore.getState().loadTableData([existing]);
      useBudgetStore.getState().addRow(0, newRow);
    });

    const state = useBudgetStore.getState();
    expect(state.tableData.some(r => r.id === 'new_row_1')).toBe(true);
  });
});

// -----------------------------------------------------------------------
// deleteRow — CONTRATO CRÍTICO
// -----------------------------------------------------------------------

describe('deleteRow', () => {
  it('remove o item da tableData', () => {
    const row1 = makeItem({ id: 'row_to_delete' });
    const row2 = makeItem({ id: 'row_to_keep' });

    act(() => {
      useBudgetStore.getState().loadTableData([row1, row2]);
      useBudgetStore.getState().deleteRow('row_to_delete');
    });

    const state = useBudgetStore.getState();
    expect(state.tableData.find(r => r.id === 'row_to_delete')).toBeUndefined();
    expect(state.tableData.find(r => r.id === 'row_to_keep')).toBeDefined();
  });

  it('NÃO adiciona o ID deletado ao dirtyRowIds', () => {
    /**
     * CONTRATO DE SEGURANÇA: A linha deletada não deve ir para o dirtyRowIds.
     * Se fosse, o auto-save tentaria fazer upsert de uma linha que não existe mais.
     * Deleções têm canal próprio: DELETE /orcamento/linhas.
     */
    const row = makeItem({ id: 'row_deleted' });

    act(() => {
      useBudgetStore.getState().loadTableData([row]);
      useBudgetStore.getState().deleteRow('row_deleted');
    });

    expect(useBudgetStore.getState().dirtyRowIds).not.toContain('row_deleted');
  });

  it('propaga DELETE para o banco se planilhaId estiver definido', () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'success', removidas: 1 }), { status: 200 })
    );

    const row = makeItem({ id: 'row_propagate' });

    act(() => {
      useBudgetStore.setState({ planilhaId: 'planilha_001' });
      useBudgetStore.getState().loadTableData([row]);
      useBudgetStore.getState().deleteRow('row_propagate');
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/proxy/orcamento/linhas',
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('NÃO propaga DELETE se planilhaId for null (planilha não salva ainda)', () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response('{}', { status: 200 })
    );

    const row = makeItem({ id: 'row_no_planilha' });

    act(() => {
      useBudgetStore.setState({ planilhaId: null });
      useBudgetStore.getState().loadTableData([row]);
      useBudgetStore.getState().deleteRow('row_no_planilha');
    });

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

// -----------------------------------------------------------------------
// updateRowById — Atualização cirúrgica do SSE
// -----------------------------------------------------------------------

describe('updateRowById', () => {
  it('atualiza apenas a linha correta sem tocar nas demais', () => {
    const row1 = makeItem({ id: 'row_a', ai_status: 'PENDENTE' });
    const row2 = makeItem({ id: 'row_b', ai_status: 'PENDENTE' });

    act(() => {
      useBudgetStore.getState().loadTableData([row1, row2]);
      useBudgetStore.getState().updateRowById('row_a', { ai_status: 'ACEITO' });
    });

    const state = useBudgetStore.getState();
    expect(state.tableData.find(r => r.id === 'row_a')?.ai_status).toBe('ACEITO');
    expect(state.tableData.find(r => r.id === 'row_b')?.ai_status).toBe('PENDENTE');
  });
});

// -----------------------------------------------------------------------
// clearDirtyRows — Confirmação de auto-save bem-sucedido
// -----------------------------------------------------------------------

describe('clearDirtyRows', () => {
  it('remove IDs confirmados do dirtyRowIds', () => {
    const row1 = makeItem({ id: 'id_saved_1' });
    const row2 = makeItem({ id: 'id_saved_2' });
    const row3 = makeItem({ id: 'id_not_saved' });

    act(() => {
      useBudgetStore.getState().setTableData([row1, row2, row3]);
      useBudgetStore.getState().clearDirtyRows(['id_saved_1', 'id_saved_2']);
    });

    const { dirtyRowIds, isDirty } = useBudgetStore.getState();
    expect(dirtyRowIds).not.toContain('id_saved_1');
    expect(dirtyRowIds).not.toContain('id_saved_2');
    expect(dirtyRowIds).toContain('id_not_saved');
    expect(isDirty).toBe(true); // Ainda tem 1 linha não salva
  });

  it('isDirty volta a false quando todos os IDs são confirmados', () => {
    const row = makeItem({ id: 'only_row' });

    act(() => {
      useBudgetStore.getState().setTableData([row]);
      useBudgetStore.getState().clearDirtyRows(['only_row']);
    });

    expect(useBudgetStore.getState().isDirty).toBe(false);
    expect(useBudgetStore.getState().dirtyRowIds).toHaveLength(0);
  });
});
