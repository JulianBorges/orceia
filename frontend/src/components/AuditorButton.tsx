'use client';
import React from 'react';
import { ShieldCheck, Loader2 } from 'lucide-react';
import { useBudgetStore } from '@/store/useBudgetStore';

export function AuditorButton() {
    const { memorialId, auditarPlanilha, isProcessing, tableData } = useBudgetStore();

    const hasItems = tableData.some(r => !r.is_macro_item);
    
    if (!memorialId) return null; // Só aparece se tiver memorial

    return (
        <button
            onClick={auditarPlanilha}
            disabled={isProcessing || !hasItems}
            title={!hasItems ? "Nenhum item para auditar" : "Auditar orçamento contra o memorial"}
            className="flex items-center gap-2 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 dark:bg-indigo-500/10 dark:hover:bg-indigo-500/20 dark:border-indigo-500/30 dark:text-indigo-400 px-4 py-2 rounded-lg font-medium shadow-sm transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
            {isProcessing ? (
                <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
            ) : (
                <ShieldCheck className="w-4 h-4 shrink-0" />
            )}
            <span className="hidden sm:inline">
                {isProcessing ? "Auditando..." : "Auditar Orçamento"}
            </span>
        </button>
    );
}
