"use client";
import React, { useState, useEffect } from 'react';
import { useAutoSave } from '../hooks/useAutoSave';
import { useSseListener } from '../hooks/useSseListener';
import { BudgetTable } from '../components/BudgetTable';
import { ThemeProvider } from '../components/ThemeProvider';
import { ThemeToggle } from '../components/ThemeToggle';
import { UploadPlanilha } from '../components/UploadPlanilha';
import { useBudgetStore } from '../store/useBudgetStore';
import { Bot, FileSpreadsheet } from 'lucide-react';

export default function Home() {
  const { planilhaId, tableData, isProcessing, processingStatusText, processarOrcamentoIA } = useBudgetStore();
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
      setIsMounted(true);
  }, []);

  // Ativa o hook "fantasma" que salva a planilha em background O(1) silenciosamente
  useAutoSave();
  
  // Ouve os resultados mastigados da IA caindo pelo Redis em tempo real apenas quando houver ID
  useSseListener(planilhaId || "");

  if (!isMounted) return null;

  return (
    <ThemeProvider defaultTheme="system" storageKey="orceia-theme">
      <main className="h-screen max-h-screen bg-background p-4 flex flex-col gap-4 overflow-hidden">
        <header className="flex justify-between items-center py-2 px-2 shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                <Bot className="w-6 h-6 text-indigo-500" /> OrceIA V3
            </h1>
            <p className="text-muted-foreground text-sm">Copiloto B2B de Orçamento</p>
          </div>
          
          <div className="flex items-center gap-4">
             {/* Mostra botão extra de upload só se já houver algo na tela para não ficar redundante com o Empty State */}
             {tableData.length > 0 && <UploadPlanilha />}
             <ThemeToggle />
          </div>
        </header>

        {tableData.length === 0 ? (
            <section className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-border rounded-xl bg-card/50 m-4">
                <div className="max-w-md text-center flex flex-col items-center gap-6">
                    <div className="w-20 h-20 bg-indigo-500/10 rounded-full flex items-center justify-center">
                        <FileSpreadsheet className="w-10 h-10 text-indigo-500" />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold mb-2">Pronto para orçar com Inteligência?</h2>
                        <p className="text-muted-foreground text-sm mb-6">Suba a planilha no formato padrão (com cabeçalhos Item, Descrição, Quantidade e Valor) e deixe a IA cuidar do resto.</p>
                        <UploadPlanilha />
                    </div>
                </div>
            </section>
        ) : (
            <>
                <div className="flex items-center justify-between px-2 shrink-0">
                    <div className="flex items-center gap-3">
                        <button 
                            onClick={() => processarOrcamentoIA()}
                            disabled={isProcessing}
                            className={`flex items-center gap-2 px-6 py-2.5 rounded-full font-semibold shadow-md transition-all ${isProcessing ? 'bg-zinc-200 text-zinc-500 dark:bg-zinc-800 cursor-not-allowed' : 'bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white'}`}
                        >
                            <Bot className="w-5 h-5" />
                            {isProcessing ? 'Inteligência em Andamento...' : '✨ Iniciar Inteligência (Copiloto)'}
                        </button>
                        
                        {isProcessing && (
                            <span className="text-sm font-medium text-indigo-600 dark:text-indigo-400 animate-pulse flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping"></span>
                                {processingStatusText}
                            </span>
                        )}
                    </div>
                </div>

                <section className="flex-1 w-full overflow-hidden relative">
                    <BudgetTable />
                </section>
            </>
        )}
      </main>
    </ThemeProvider>
  );
}
