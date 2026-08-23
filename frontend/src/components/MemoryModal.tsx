import React from 'react';
import { Brain, X } from 'lucide-react';

export interface MemoryModalProps {
    memoryModalData: { matches: any[], rowIndex: number, legado: string, codigoSelecionado?: string | null } | null;
    setMemoryModalData: (data: any) => void;
    data: any[];
    updateRow: (index: number, newRowData: any) => void;
    memorizeHumanFeedback: (original: string, novo: string, parecer: string) => void;
}

export function MemoryModal({ memoryModalData, setMemoryModalData, data, updateRow, memorizeHumanFeedback }: MemoryModalProps) {
    if (!memoryModalData) return null;

    return (
        <div 
            className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setMemoryModalData(null)}
        >
            <div 
                className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
                    <div className="flex items-center gap-2 text-indigo-400">
                        <Brain className="w-5 h-5" />
                        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Memória de Cálculo da IA</h2>
                    </div>
                    <button 
                        onClick={() => setMemoryModalData(null)}
                        className="p-1.5 rounded-md hover:bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
                
                <div className="p-4 overflow-y-auto custom-scrollbar flex flex-col gap-3">
                    <div className="bg-indigo-500/5 dark:bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-4 mb-2 flex flex-col gap-2 shrink-0">
                        <p className="text-sm text-zinc-700 dark:text-zinc-300">
                            A IA analisou o banco de dados do SINAPI e selecionou as {memoryModalData.matches.length} opções mais prováveis antes de tomar a decisão final para o item:
                        </p>
                        <p className="text-sm font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-500/10 px-3 py-2 rounded-md border border-indigo-500/20 break-words whitespace-normal">
                            {memoryModalData.legado}
                        </p>
                    </div>
                    
                    {memoryModalData.matches.map((match: any, idx: number) => (
                        <div key={idx} className="bg-white dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-700/50 rounded-lg p-4 flex flex-col gap-3 relative overflow-hidden group/match hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors shrink-0">
                            {match.codigo === memoryModalData.codigoSelecionado && (
                                <div className="absolute top-0 right-0 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-bl-lg border-l border-b border-emerald-500/20">
                                    Vencedor
                                </div>
                            )}
                            <div className="flex items-center gap-2 flex-wrap pr-16">
                                <span className="text-xs font-mono text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded border border-blue-400/20">{match.codigo}</span>
                                <span className="text-xs font-medium text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded border border-emerald-400/20">R$ {Number(match.preco || 0).toFixed(2)}</span>
                                <span className="text-xs font-medium text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20">{match.unidade}</span>
                                <span className="text-xs font-medium text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">Match: {match.score}%</span>
                            </div>
                            <div className="flex items-start justify-between gap-4">
                                <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed flex-1 break-words whitespace-normal">
                                    {match.descricao}
                                </p>
                                <button 
                                    onClick={() => {
                                        if (window.confirm("Deseja substituir o item atual por esta composição do SINAPI?")) {
                                            const originalTerm = data[memoryModalData.rowIndex].descricao;
                                            const parecerText = 'Composição substituída manualmente pelo usuário via Memória de Cálculo.';
                                            
                                            updateRow(memoryModalData.rowIndex, {
                                                codigo: match.codigo,
                                                descricao: match.descricao,
                                                valorUnit: Number(match.preco) || 0,
                                                und: match.unidade,
                                                ai_status: 'SUBSTITUIDO',
                                                ai_parecer_tecnico: parecerText,
                                                base: 'SINAPI'
                                            });
                                            
                                            memorizeHumanFeedback(originalTerm, match.codigo, parecerText);
                                            setMemoryModalData(null);
                                        }
                                    }}
                                    className="opacity-0 group-hover/match:opacity-100 transition-opacity bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded shrink-0"
                                >
                                    Substituir
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
                
                <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 flex justify-end">
                    <button 
                        onClick={() => setMemoryModalData(null)}
                        className="px-4 py-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-sm font-medium text-zinc-900 dark:text-zinc-100 rounded-md transition-colors"
                    >
                        Fechar
                    </button>
                </div>
            </div>
        </div>
    );
}
