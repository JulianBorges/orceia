"use client";
import React, { useEffect } from 'react';
import { useAutoSave } from '../hooks/useAutoSave';
import { useSseListener } from '../hooks/useSseListener';
import { BudgetTable } from '../components/BudgetTable';
import { UploadPlanilha } from '../components/UploadPlanilha';
import { Sidebar } from '../components/Sidebar';
import { MemorialUploadButton } from '../components/MemorialUploadButton';
import { AuditorButton } from '../components/AuditorButton';
import * as XLSX from 'xlsx';
import { useBudgetStore } from '../store/useBudgetStore';
import { Loader2, Download, Layers, Trash2, MoreVertical } from 'lucide-react';

export default function Home() {
  const { 
      planilhaId, 
      tableData, 
      isProcessing, 
      processingStatusText,
      processedItemsCount,
      totalItemsToProcess,
      currentAnalyzingItemName,
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
      <div className="flex h-screen overflow-hidden w-full bg-[#f4f5f7] dark:bg-[#0a0a0c]">
        
        <Sidebar />

        <main className="flex-1 flex flex-col items-center relative overflow-y-auto">
            <div className="w-full max-w-[96vw] md:max-w-[92vw] 2xl:max-w-[1800px] flex flex-col flex-1 pb-4 md:pb-8 pt-8 md:pt-10 gap-4 md:gap-6 min-h-0">
                {/* Header */}
                <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 md:gap-6 shrink-0">
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
                    <div className="flex items-center gap-3 w-full overflow-x-auto pb-2 md:pb-0">
                    {tableData.length === 0 ? (
                        <div className="flex items-center gap-3">
                            <UploadPlanilha />
                            <MemorialUploadButton />
                        </div>
                    ) : (
                        isProcessing ? (
                            <div className="flex flex-col justify-center gap-2 bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 px-5 py-2.5 rounded-xl shadow-sm w-full md:w-[450px]">
                                <div className="flex items-center justify-between text-zinc-700 dark:text-zinc-300 w-full">
                                    <div className="flex items-center gap-2 overflow-hidden mr-3">
                                        <Loader2 className="w-4 h-4 text-purple-600 dark:text-purple-400 animate-spin shrink-0" />
                                        <span className="text-sm font-medium truncate" title={currentAnalyzingItemName}>
                                            {currentAnalyzingItemName || "Iniciando lote..."}
                                        </span>
                                    </div>
                                    <span className="text-sm font-bold text-zinc-700 dark:text-zinc-300 shrink-0">
                                        {totalItemsToProcess > 0 ? Math.round((processedItemsCount / totalItemsToProcess) * 100) : 0}%
                                    </span>
                                </div>
                                <div className="flex items-center gap-3 w-full">
                                    <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                                        <div 
                                            className="bg-purple-600 dark:bg-purple-400 h-1.5 rounded-full transition-all duration-300 ease-out"
                                            style={{ width: `${totalItemsToProcess > 0 ? (processedItemsCount / totalItemsToProcess) * 100 : 0}%` }}
                                        ></div>
                                    </div>
                                    <span className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500 shrink-0 whitespace-nowrap">
                                        {processedItemsCount} / {totalItemsToProcess}
                                    </span>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-3">
                                <div className="flex items-center bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 rounded-xl p-1.5 shadow-sm min-w-max">
                                    <div className="flex flex-col border-r border-zinc-100 dark:border-zinc-800 px-4 py-2 w-[100px] md:w-[120px]">
                                        <span className="text-[9px] md:text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-1">BDI (%)</span>
                                        <div className="flex items-center justify-between w-full">
                                            <input 
                                                type="number"
                                                value={bdi}
                                                onChange={(e) => setBdi(Number(e.target.value) || 0)}
                                                className="w-12 md:w-14 bg-transparent text-[16px] md:text-[20px] font-bold text-zinc-900 dark:text-zinc-100 outline-none text-left"
                                            />
                                            <span className="text-zinc-400 text-[13px] md:text-[15px] font-medium">%</span>
                                        </div>
                                    </div>
                                    <div className="flex flex-col px-4 py-2 min-w-[180px] md:min-w-[220px]">
                                        <span className="text-[9px] md:text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-1">Total (c/ BDI)</span>
                                        <span className="text-[20px] md:text-[24px] font-bold text-[#00cc88] dark:text-[#00cc88] leading-none mt-0.5">
                                            {totalSomado.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                        </span>
                                    </div>
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
                    <div className="flex flex-col flex-1 w-full overflow-visible min-h-0 relative mb-1">
                        <span className="text-[12px] md:text-[13px] font-medium text-zinc-400 dark:text-zinc-500 mb-2 md:mb-3 px-1 shrink-0">
                            Orçamento com {tableData.length} itens
                        </span>
                        <section className="w-full flex flex-col flex-1 min-h-0 bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800 rounded-xl shadow-sm overflow-visible relative">
                            <div className="flex-1 overflow-hidden rounded-xl">
                                <BudgetTable />
                            </div>
                            
                            {/* Floating Add Button on the bottom border */}
                            <UploadPlanilha append={true} isFloatingAdd={true} />
                        </section>

                        {/* Actions Toolbar - Footer */}
                        <div className="flex justify-between mt-4 shrink-0 px-1">
                            <div>
                                <AuditorButton />
                            </div>

                            <div className="group flex items-center justify-end relative">
                                
                                {/* Expanded Menu (Horizontal sliding to the left) */}
                                <div className="flex items-center gap-2 opacity-0 translate-x-4 invisible group-hover:opacity-100 group-hover:translate-x-0 group-hover:visible transition-all duration-300 mr-2">
                                    <UploadPlanilha />
                                    <MemorialUploadButton />
                                    
                                    <div className="w-px h-6 bg-zinc-300 dark:bg-zinc-800 mx-1"></div>
                                    
                                    <button 
                                        onClick={handleDownload} 
                                        className="flex items-center gap-2 bg-zinc-50 hover:bg-zinc-100 border border-zinc-200/80 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:border-zinc-700 dark:text-zinc-200 px-4 py-2 rounded-lg font-medium transition-colors text-sm"
                                    >
                                        <Download className="w-4 h-4" />
                                        Baixar Planilha
                                    </button>
                                    
                                    <button 
                                        onClick={() => {
                                            if(confirm("Tem certeza que deseja limpar todos os itens? Essa ação não pode ser desfeita.")) clearBudget();
                                        }}
                                        className="flex items-center gap-2 bg-red-50 hover:bg-red-100 border border-red-200/80 text-red-600 dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:border-red-500/30 dark:text-red-400 px-4 py-2 rounded-lg font-medium transition-colors text-sm"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                        Limpar Orçamento
                                    </button>
                                </div>

                                {/* Trigger Icon */}
                                <button className="flex items-center justify-center p-2.5 rounded-xl transition-colors text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:text-zinc-200 dark:hover:bg-zinc-800 relative z-10">
                                    <MoreVertical className="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </main>
      </div>
  );
}
