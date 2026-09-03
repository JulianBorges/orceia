import React, { useState, useEffect } from 'react';
import { useBudgetStore } from '../store/useBudgetStore';
import { X, FolderOpen, Loader2, Calendar, FileText } from 'lucide-react';

export function SavedBudgetsModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [loadingBudgetId, setLoadingBudgetId] = useState<string | null>(null);
  
  const { loadTableData, setTitle, setPlanilhaId } = useBudgetStore();

  const fetchBudgets = async () => {
    setIsLoading(true);
    setIsError(false);
    try {
      const res = await fetch('/api/proxy/orcamento/planilhas');
      if (!res.ok) throw new Error('Falha ao buscar orçamentos');
      const data = await res.json();
      setBudgets(data);
    } catch (err) {
      console.error(err);
      setIsError(true);
    } finally {
      setIsLoading(false);
    }
  };

  const loadBudget = async (id: string) => {
    setLoadingBudgetId(id);
    try {
      const res = await fetch(`/api/proxy/orcamento/planilhas/${id}/linhas`);
      if (!res.ok) throw new Error('Falha ao carregar orçamento');
      const data = await res.json();
      
      const mappedRows = (data.linhas || []).map((row: any) => ({
        id: row.id,
        is_macro_item: !row.preco_unitario && !row.unidade,
        item: "-",
        codigo: row.codigo || "",
        base: "SINAPI",
        descricao: row.descricao || "",
        und: row.unidade || "",
        quant: row.quantidade || 0,
        valorUnit: row.preco_unitario || 0,
        total: (row.quantidade || 0) * (row.preco_unitario || 0),
        ai_status: row.codigo ? "ACEITO" : "PENDENTE",
        ai_parecer_tecnico: ""
      }));
      
      // Update store
      setPlanilhaId(id);
      setTitle(data.titulo || 'Orçamento Recuperado');
      loadTableData(mappedRows);
      
      setIsOpen(false);
    } catch (err) {
      console.error(err);
      alert('Erro ao carregar orçamento.');
    } finally {
      setLoadingBudgetId(null);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchBudgets();
    }
  }, [isOpen]);

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
      >
        <FolderOpen className="w-4 h-4" />
        Meus Orçamentos
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-zinc-900 w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden border border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center justify-between px-6 py-5 border-b border-zinc-100 dark:border-zinc-800 shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-purple-100 dark:bg-purple-500/20 text-purple-600 dark:text-purple-400 rounded-xl flex items-center justify-center">
                  <FolderOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Meus Orçamentos Salvos</h3>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Restaurar projetos anteriores</p>
                </div>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors bg-zinc-50 hover:bg-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-700 p-2 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 bg-zinc-50 dark:bg-black/20">
              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-purple-600 animate-spin mb-4" />
                  <span className="text-zinc-500">Carregando orçamentos...</span>
                </div>
              ) : isError ? (
                <div className="text-center py-12 text-red-500">
                  Falha ao buscar orçamentos salvos.
                </div>
              ) : budgets.length === 0 ? (
                <div className="text-center py-12 flex flex-col items-center gap-3">
                  <FileText className="w-12 h-12 text-zinc-300 dark:text-zinc-700" />
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium text-lg">Nenhum orçamento encontrado</span>
                  <p className="text-sm text-zinc-400 dark:text-zinc-500">
                    Seus orçamentos salvos automaticamente aparecerão aqui.
                  </p>
                </div>
              ) : (
                <div className="grid gap-3">
                  {budgets.map((b) => (
                    <div 
                      key={b.id} 
                      className="flex items-center justify-between p-4 bg-white dark:bg-zinc-800 rounded-xl border border-zinc-200 dark:border-zinc-700 hover:border-purple-300 dark:hover:border-purple-500/50 transition-colors shadow-sm"
                    >
                      <div className="flex flex-col gap-1">
                        <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-[15px]">
                          {b.titulo || 'Orçamento sem título'}
                        </span>
                        <div className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
                          <span className="flex items-center gap-1.5 font-medium bg-zinc-100 dark:bg-zinc-900 px-2 py-0.5 rounded-md">
                            <Calendar className="w-3.5 h-3.5" />
                            {new Date(b.updated_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => loadBudget(b.id)}
                        disabled={loadingBudgetId === b.id}
                        className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-5 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 shadow-sm"
                      >
                        {loadingBudgetId === b.id ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" /> Carregando...
                          </>
                        ) : (
                          'Abrir'
                        )}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
