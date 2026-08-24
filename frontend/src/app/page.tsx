"use client";
import React, { useEffect } from 'react';
import { useAutoSave } from '../hooks/useAutoSave';
import { useSseListener } from '../hooks/useSseListener';
import { BudgetTable } from '../components/BudgetTable';
import { ThemeToggle } from '../components/ThemeToggle';
import { UploadPlanilha } from '../components/UploadPlanilha';
import * as XLSX from 'xlsx';
import { useBudgetStore } from '../store/useBudgetStore';
import { Loader2, Download, Layers, Trash2, Plus } from 'lucide-react';

export default function Home() {
  const { 
      planilhaId, 
      tableData, 
      isProcessing, 
      processingStatusText,
      bdi,
      setBdi,
      title,
      setTitle,
      clearBudget
  } = useBudgetStore();
  
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
      setIsMounted(true);
  }, []);

  useAutoSave();
  useSseListener(planilhaId || "");

  if (!isMounted) return null;

  const totalSomado = tableData
      .filter(r => !r.is_macro_item)
      .reduce((acc, r) => acc + (r.total * (1 + bdi / 100)), 0);

  const handleDownload = () => {
      const headers = [
          "ITEM", "CÓDIGO", "BASE", "DESCRIÇÃO DO SERVIÇO", 
          "UND", "QUANT", "VALOR UNIT", "VALOR C/ BDI", "TOTAL", 
          "PARECER IA", "JUSTIFICATIVA IA"
      ];

      const dataRows = tableData.map(row => {
          const valBdi = row.valorUnit * (1 + bdi / 100);
          const totalBdi = row.total * (1 + bdi / 100);
          return [
              row.item,
              row.codigo,
              row.base,
              row.descricao,
              row.und,
              row.quant,
              row.valorUnit,
              valBdi,
              totalBdi,
              row.ai_status || "PENDENTE",
              row.ai_parecer_tecnico || ""
          ];
      });

      const worksheet = XLSX.utils.aoa_to_sheet([headers, ...dataRows]);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Orçamento");
      XLSX.writeFile(workbook, `${title || 'orcamento'}.xlsx`);
  };

  return (
      <main className="h-screen overflow-hidden bg-[#f4f5f7] dark:bg-[#0a0a0c] flex flex-col items-center relative">
        
        <div className="w-full max-w-[96vw] md:max-w-[92vw] 2xl:max-w-[1800px] flex flex-col flex-1 pb-4 md:pb-8 pt-16 md:pt-20 gap-4 md:gap-6 min-h-0">
            {/* Header */}
            <header className="flex flex-col md:flex-row justify-between items-start gap-4 md:gap-6 shrink-0">
              <div className="flex flex-col gap-1 w-full md:w-auto">
                <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="text-[24px] md:text-[28px] font-bold text-zinc-900 dark:text-zinc-100 bg-transparent border-none outline-none w-full min-w-[200px] md:min-w-[300px] placeholder-zinc-300"
                    placeholder="Orçamento"
                />
                <p className="text-zinc-500 dark:text-zinc-400 text-[13px] md:text-[14px]">Gerencie itens, insumos e composições com IA.</p>
              </div>
              
              <div className="relative flex flex-col items-end w-full md:w-auto">
                 <div className="absolute -top-12 right-0 z-50">
                     <ThemeToggle />
                 </div>
                 <div className="flex items-center gap-4 w-full overflow-x-auto pb-2 md:pb-0">
                 {tableData.length === 0 ? (
                     <UploadPlanilha />
                 ) : (
                     isProcessing ? (
                         <div className="flex items-center gap-3 bg-purple-50/80 dark:bg-purple-500/10 border border-purple-200/50 dark:border-purple-500/20 text-purple-700 dark:text-purple-400 px-6 py-4 rounded-xl font-medium shadow-sm w-full md:w-auto">
                             <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                             <span className="text-sm md:text-base whitespace-nowrap">{processingStatusText || "Buscando itens no banco de dados e SINAPI..."}</span>
                         </div>
                     ) : (
                         <div className="flex items-center bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 rounded-xl p-1.5 shadow-sm min-w-max">
                             <div className="flex flex-col border-r border-zinc-100 dark:border-zinc-800 px-4 md:px-6 py-2.5 w-[100px] md:w-[120px]">
                                 <span className="text-[9px] md:text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-2">BDI (%)</span>
                                 <div className="flex items-center justify-between w-full">
                                     <input 
                                         type="number"
                                         value={bdi}
                                         onChange={(e) => setBdi(Number(e.target.value) || 0)}
                                         className="w-12 md:w-14 bg-transparent text-[18px] md:text-[22px] font-bold text-zinc-900 dark:text-zinc-100 outline-none text-left"
                                     />
                                     <span className="text-zinc-400 text-[13px] md:text-[15px] font-medium">%</span>
                                 </div>
                             </div>
                             <div className="flex flex-col px-4 md:px-6 py-2.5 min-w-[200px] md:min-w-[260px]">
                                 <span className="text-[9px] md:text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-2">Total do Orçamento (c/ BDI)</span>
                                 <span className="text-[22px] md:text-[28px] font-bold text-[#00cc88] dark:text-[#00cc88] leading-none mt-0.5">
                                     {totalSomado.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                 </span>
                             </div>
                         </div>
                     )
                 )}
                 </div>
              </div>
            </header>

            {tableData.length === 0 ? (
                <section className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl bg-white/50 dark:bg-zinc-900/30 min-h-[300px] md:min-h-[400px]">
                    <div className="text-center flex flex-col items-center gap-5 px-4">
                        <div className="w-16 h-16 md:w-20 md:h-20 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center">
                            <Layers className="w-8 h-8 md:w-10 md:h-10 text-zinc-400 dark:text-zinc-500" strokeWidth={1.5} />
                        </div>
                        <div>
                            <h2 className="text-lg md:text-xl font-semibold text-zinc-800 dark:text-zinc-200">Nenhum orçamento carregado</h2>
                            <p className="text-zinc-500 dark:text-zinc-400 mt-2 max-w-sm text-sm md:text-base">Faça o upload da sua planilha Excel para a Inteligência Artificial analisar.</p>
                        </div>
                    </div>
                </section>
            ) : (
                <div className="flex flex-col flex-1 w-full overflow-hidden min-h-0">
                    <span className="text-[12px] md:text-[13px] font-medium text-zinc-400 dark:text-zinc-500 mb-2 md:mb-3 px-1 shrink-0">
                        Orçamento com {tableData.length} itens
                    </span>
                    <section className="w-full flex flex-col flex-1 min-h-0 bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden">
                        <BudgetTable />
                    </section>
                    
                    <div className="flex flex-col md:flex-row justify-between items-stretch md:items-center gap-4 mt-5 shrink-0">
                        <div className="flex flex-col sm:flex-row gap-3 md:gap-4">
                            <UploadPlanilha append={true} className="flex justify-center items-center gap-2 bg-white hover:bg-zinc-50 border border-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:border-zinc-700 dark:text-zinc-200 px-5 py-2.5 rounded-lg font-medium shadow-sm transition-colors text-[13px] w-full sm:w-auto">
                                <Plus className="w-4 h-4 text-zinc-500" />
                                Carregar Mais Itens
                            </UploadPlanilha>
                            <button 
                                onClick={() => clearBudget()}
                                className="flex justify-center items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:text-red-400 px-5 py-2.5 rounded-lg font-medium transition-colors text-[13px] w-full sm:w-auto"
                            >
                                <Trash2 className="w-4 h-4" />
                                Limpar Orçamento
                            </button>
                        </div>
                        <div className="w-full md:w-auto">
                            <button onClick={handleDownload} className="flex justify-center items-center gap-2 bg-[#5c4cfc] hover:bg-[#4a39eb] text-white px-8 py-2.5 rounded-lg font-medium shadow-sm transition-colors text-[13px] w-full md:w-auto">
                                <Download className="w-4 h-4" />
                                Download
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
      </main>
  );
}
