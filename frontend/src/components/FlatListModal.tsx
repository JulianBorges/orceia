import React from 'react';
import { AlertCircle, Sparkles } from 'lucide-react';

interface FlatListModalProps {
    isOpen: boolean;
    onMapearComoListaPlana: () => void;
    onUsarIAParaEAP: () => void;
    isLoading: boolean;
}

export function FlatListModal({ isOpen, onMapearComoListaPlana, onUsarIAParaEAP, isLoading }: FlatListModalProps) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-2xl max-w-lg w-full p-6 border border-zinc-200 dark:border-zinc-800">
                <div className="flex items-center gap-3 mb-4">
                    <AlertCircle className="w-8 h-8 text-amber-500" />
                    <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Lista Plana Detectada</h2>
                </div>
                
                <p className="text-zinc-600 dark:text-zinc-400 mb-8 leading-relaxed">
                    Não identificamos etapas estruturais (como 1.0, 2.0 ou cabeçalhos) na sua planilha. Deseja prosseguir assim mesmo ou usar a IA para estruturar uma EAP lógica automaticamente?
                </p>

                <div className="flex flex-col gap-3">
                    <button
                        onClick={onMapearComoListaPlana}
                        disabled={isLoading}
                        className="w-full py-3 px-4 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 font-medium rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors disabled:opacity-50"
                    >
                        Mapear como Lista Plana
                    </button>
                    
                    <button
                        onClick={onUsarIAParaEAP}
                        disabled={isLoading}
                        className="w-full py-3 px-4 bg-violet-500 hover:bg-violet-600 text-white font-medium rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                    >
                        {isLoading ? (
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                            <Sparkles className="w-5 h-5" />
                        )}
                        Usar IA para Estruturar EAP
                    </button>
                </div>
            </div>
        </div>
    );
}
