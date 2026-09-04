'use client';
import React, { useRef, useState } from 'react';
import { FileText, CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { useBudgetStore } from '@/store/useBudgetStore';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export function MemorialUploadButton({ iconOnly = false }: { iconOnly?: boolean }) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { setMemorialId, memorialId } = useBudgetStore();

    const [status, setStatus] = useState<UploadStatus>('idle');
    const [errorMessage, setErrorMessage] = useState('');
    const [chunksGerados, setChunksGerados] = useState(0);

    // Se já há um memorial carregado na sessão, inicializa como sucesso
    const displayStatus: UploadStatus = status === 'idle' && memorialId ? 'success' : status;

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.pdf')) {
            setStatus('error');
            setErrorMessage('Apenas arquivos .pdf são aceitos.');
            if (fileInputRef.current) fileInputRef.current.value = '';
            return;
        }

        setStatus('uploading');
        setErrorMessage('');

        try {
            const formData = new FormData();
            formData.append('arquivo', file);
            // Se já existe um projeto_id (reutilizar memorial do mesmo projeto), envia
            if (memorialId) {
                formData.append('projeto_id', memorialId);
            }

            const res = await fetch('/api/proxy/auditoria/ingerir-memorial', {
                method: 'POST',
                body: formData,
                // Não setar Content-Type: o browser define multipart/form-data + boundary automaticamente
            });

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.detail || `Erro ${res.status} ao processar o PDF.`);
            }

            const data = await res.json();
            setMemorialId(data.projeto_id);
            setChunksGerados(data.chunks_gerados);
            setStatus('success');
            console.log(`[MEMORIAL] Ingerido com sucesso. Projeto: ${data.projeto_id}, Chunks: ${data.chunks_gerados}`);
        } catch (err: any) {
            console.error('[MEMORIAL] Falha ao ingerir memorial:', err);
            setStatus('error');
            setErrorMessage(err.message || 'Falha ao processar o PDF.');
        } finally {
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleClick = () => {
        // Se já carregado, permite trocar o memorial
        setStatus('idle');
        fileInputRef.current?.click();
    };

    const baseClass = iconOnly
        ? "group relative p-2 rounded-lg transition-colors flex items-center justify-center cursor-pointer"
        : "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors text-sm cursor-pointer";

    const getTooltip = (text: string) => {
        if (!iconOnly) return null;
        return (
            <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-zinc-800 text-white text-[11px] font-medium px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                {text}
            </span>
        );
    };

    if (displayStatus === 'success') {
        return (
            <button
                onClick={handleClick}
                className={`${baseClass} ${iconOnly ? 'text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20' : 'bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 dark:border-emerald-500/30 dark:text-emerald-400'}`}
            >
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                {!iconOnly && (
                    <span className="hidden sm:inline">
                        Memorial ✓{chunksGerados > 0 ? ` (${chunksGerados} trechos)` : ''}
                    </span>
                )}
                {getTooltip("Substituir Memorial")}
                <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
            </button>
        );
    }

    if (displayStatus === 'uploading') {
        return (
            <div className={`${baseClass} ${iconOnly ? 'text-zinc-500' : 'bg-zinc-50 dark:bg-zinc-800 border border-zinc-200/80 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400'}`}>
                <Loader2 className="w-5 h-5 animate-spin shrink-0" />
                {!iconOnly && <span className="hidden sm:inline">Processando PDF...</span>}
                {getTooltip("Processando...")}
            </div>
        );
    }

    if (displayStatus === 'error') {
        return (
            <button
                onClick={handleClick}
                className={`${baseClass} ${iconOnly ? 'text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20' : 'bg-red-50 hover:bg-red-100 border border-red-200 text-red-600 dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:border-red-500/30 dark:text-red-400'}`}
            >
                <XCircle className="w-5 h-5 shrink-0" />
                {!iconOnly && <span className="hidden sm:inline">Erro — tentar novamente</span>}
                {getTooltip("Erro no Memorial")}
                <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
            </button>
        );
    }

    // Estado idle
    return (
        <div>
            <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
            <button
                onClick={() => fileInputRef.current?.click()}
                className={`${baseClass} ${iconOnly ? 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800' : 'bg-zinc-50 hover:bg-zinc-100 border border-zinc-200/80 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:border-zinc-700 dark:text-zinc-200'}`}
            >
                <FileText className="w-5 h-5 shrink-0" />
                {!iconOnly && <span className="hidden sm:inline">Carregar Memorial (PDF)</span>}
                {getTooltip("Carregar Memorial")}
            </button>
        </div>
    );
}
