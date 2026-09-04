'use client';
import React from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { useBudgetStore } from '@/store/useBudgetStore';

export function AuditorButton() {
    const { memorialId, auditarPlanilha, isProcessing, tableData } = useBudgetStore();

    const hasItems = tableData.some(r => !r.is_macro_item);
    
    if (!memorialId) return null; // Só aparece se tiver memorial

    return (
        <button
            onClick={auditarPlanilha}
            disabled={isProcessing || !hasItems}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium shadow-sm transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
            {isProcessing ? (
                <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
            ) : (
                <Sparkles className="w-4 h-4 shrink-0" />
            )}
            <span className="hidden sm:inline">
                {isProcessing ? "Validando..." : "Validar Orçamento"}
            </span>
        </button>
    );
}
