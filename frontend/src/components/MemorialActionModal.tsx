import React from 'react';
import { FileText, Trash2, X } from 'lucide-react';

interface MemorialActionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onReplace: () => void;
    onDelete: () => void;
    isDeleting?: boolean;
}

export function MemorialActionModal({ isOpen, onClose, onReplace, onDelete, isDeleting }: MemorialActionModalProps) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
            <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-2xl max-w-md w-full p-6 border border-zinc-200 dark:border-zinc-800 relative">
                <button 
                    onClick={onClose}
                    className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                >
                    <X className="w-5 h-5" />
                </button>
                
                <div className="flex items-center gap-3 mb-4">
                    <FileText className="w-8 h-8 text-emerald-500" />
                    <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Memorial Carregado</h2>
                </div>
                
                <p className="text-zinc-600 dark:text-zinc-400 mb-8 leading-relaxed">
                    Voc jo possui um memorial descritivo vinculado a este oramento. O que deseja fazer?
                </p>

                <div className="flex flex-col gap-3">
                    <button
                        onClick={onReplace}
                        className="w-full py-3 px-4 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 font-medium rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors"
                    >
                        Substituir Memorial
                    </button>
                    
                    <button
                        onClick={onDelete}
                        disabled={isDeleting}
                        className="w-full py-3 px-4 bg-red-50 hover:bg-red-100 text-red-600 dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:text-red-400 font-medium rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                    >
                        {isDeleting ? (
                            <div className="w-5 h-5 border-2 border-red-500/30 border-t-red-500 rounded-full animate-spin" />
                        ) : (
                            <Trash2 className="w-5 h-5" />
                        )}
                        Excluir da IA
                    </button>
                </div>
            </div>
        </div>
    );
}

