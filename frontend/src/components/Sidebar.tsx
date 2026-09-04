import React, { useEffect, useState } from 'react';
import { useBudgetStore } from '../store/useBudgetStore';
import { FolderOpen, Loader2, FileText, Calendar, Plus, ChevronLeft, ChevronRight, Menu } from 'lucide-react';
import { ThemeToggle } from './ThemeToggle';

export function Sidebar() {
  const [budgets, setBudgets] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [loadingBudgetId, setLoadingBudgetId] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  
  const { loadTableData, setTitle, setPlanilhaId, planilhaId } = useBudgetStore();

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
        is_macro_item: !row.unidade || row.unidade.trim() === '' || row.unidade.trim() === '-',
        item: "-",
        codigo: row.codigo || "",
        base: row.codigo ? "SINAPI" : "",
        descricao: row.descricao || "",
        descricao_legada: row.descricao || "",
        und: row.unidade || "",
        quant: row.quantidade || 0,
        valorUnit: row.preco_unitario || 0,
        total: (row.quantidade || 0) * (row.preco_unitario || 0),
        ai_status: row.codigo ? "ACEITO" : "PENDENTE",
        ai_parecer_tecnico: ""
      }));
      
      setPlanilhaId(id);
      setTitle(data.titulo || 'Orçamento Recuperado');
      loadTableData(mappedRows);
    } catch (err) {
      console.error(err);
      alert('Erro ao carregar orçamento.');
    } finally {
      setLoadingBudgetId(null);
    }
  };

  useEffect(() => {
    fetchBudgets();
  }, []);

  const handleNewBudget = () => {
    setPlanilhaId(null);
    setTitle('Novo Orçamento');
    loadTableData([]);
  };

  return (
    <aside className={`${isCollapsed ? 'w-10' : 'w-64'} h-full bg-zinc-50 dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 flex flex-col shrink-0 transition-all duration-300 ease-in-out`}>
      {/* Header / Logo */}
      <div className={`h-16 flex items-center border-b border-zinc-200 dark:border-zinc-800 shrink-0 ${isCollapsed ? 'justify-center px-0' : 'justify-between px-4'}`}>
        {!isCollapsed && (
          <h1 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 overflow-hidden whitespace-nowrap">
            <FolderOpen className="w-5 h-5 shrink-0 text-zinc-500" />
            <span>Orçamentos</span>
          </h1>
        )}
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={`p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors`}
        >
          {isCollapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>

      {/* Conteúdo oculto quando recolhido */}
      {!isCollapsed ? (
        <>
          {/* New Budget Button */}
          <div className="p-3 shrink-0">
            <button
              onClick={handleNewBudget}
              className="flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-lg text-sm font-semibold transition-colors shadow-sm w-full px-4"
            >
              <Plus className="w-4 h-4 shrink-0" />
              <span>Novo Orçamento</span>
            </button>
          </div>

          <div className="px-4 pb-2 shrink-0">
            <h2 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">Histórico</h2>
          </div>

          {/* Budget List */}
          <div className="flex-1 overflow-y-auto px-2 overflow-x-hidden">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-8">
                <Loader2 className="w-5 h-5 text-purple-600 animate-spin mb-2" />
              </div>
            ) : isError ? (
              <div className="text-center py-8 text-xs text-red-500">
                Falha ao carregar.
              </div>
            ) : budgets.length === 0 ? (
              <div className="text-center py-8 flex flex-col items-center gap-2">
                <FileText className="w-6 h-6 text-zinc-300 dark:text-zinc-700" />
                <p className="text-xs text-zinc-400 dark:text-zinc-500 px-2">
                  Nenhum orçamento salvo.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-1 items-center">
                {budgets.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => loadBudget(b.id)}
                    disabled={loadingBudgetId === b.id}
                    className={`flex flex-col gap-1 p-2.5 rounded-xl transition-colors text-left w-full items-start
                      ${planilhaId === b.id 
                        ? 'bg-purple-100 dark:bg-purple-500/20 border border-purple-200 dark:border-purple-500/30' 
                        : 'hover:bg-zinc-100 dark:hover:bg-zinc-800 border border-transparent'}
                    `}
                  >
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-[13px] line-clamp-1 break-all">
                      {b.titulo || 'Sem título'}
                    </span>
                    <div className="flex items-center gap-1 text-[10px] text-zinc-500 dark:text-zinc-400">
                      <Calendar className="w-3 h-3" />
                      {new Date(b.updated_at).toLocaleDateString()}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="flex-1 bg-transparent"></div>
      )}

      {/* Footer / Theme */}
      <div className={`p-4 border-t border-zinc-200 dark:border-zinc-800 shrink-0 flex items-center ${isCollapsed ? 'justify-center px-0' : 'justify-start px-4'}`}>
        <ThemeToggle />
      </div>
    </aside>
  );
}
