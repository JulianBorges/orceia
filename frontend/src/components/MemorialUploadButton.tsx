'use client';
import React, { useRef, useState } from 'react';
import { FileText, CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { useBudgetStore } from '@/store/useBudgetStore';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export function MemorialUploadButton() {
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

    if (displayStatus === 'success') {
        return (
            <button
                onClick={handleClick}
                title="Memorial carregado. Clique para substituir."
                className="flex items-center gap-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 dark:border-emerald-500/30 dark:text-emerald-400 px-4 py-2 rounded-lg font-medium shadow-sm transition-colors text-sm"
            >
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span className="hidden sm:inline">
                    Memorial ✓{chunksGerados > 0 ? ` (${chunksGerados} trechos)` : ''}
                </span>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={handleFileChange}
                />
            </button>
        );
    }

    if (displayStatus === 'uploading') {
        return (
            <div className="flex items-center gap-2 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400 px-4 py-2 rounded-lg text-sm">
                <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                <span className="hidden sm:inline">Processando PDF...</span>
            </div>
        );
    }

    if (displayStatus === 'error') {
        return (
            <button
                onClick={handleClick}
                title={errorMessage}
                className="flex items-center gap-2 bg-red-50 hover:bg-red-100 border border-red-200 text-red-600 dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:border-red-500/30 dark:text-red-400 px-4 py-2 rounded-lg font-medium shadow-sm transition-colors text-sm"
            >
                <XCircle className="w-4 h-4 shrink-0" />
                <span className="hidden sm:inline">Erro — tentar novamente</span>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={handleFileChange}
                />
            </button>
        );
    }

    // Estado idle
    return (
        <div>
            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileChange}
            />
            <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-2 bg-white hover:bg-zinc-50 border border-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700 dark:border-zinc-700 dark:text-zinc-200 px-4 py-2 rounded-lg font-medium shadow-sm transition-colors text-sm"
            >
                <FileText className="w-4 h-4 shrink-0" />
                <span className="hidden sm:inline">Carregar Memorial (PDF)</span>
            </button>
        </div>
    );
}
