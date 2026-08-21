'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Lock, ArrowRight } from 'lucide-react';

export default function LoginPage() {
    const [tenant, setTenant] = useState('');
    const [loading, setLoading] = useState(false);
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!tenant.trim()) return;
        setLoading(true);

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tenant_id: tenant })
            });

            if (res.ok) {
                // Ao forçar um refresh total (ou push), o middleware rodará
                router.push('/');
                router.refresh();
            } else {
                alert('Erro ao fazer login.');
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex flex-col items-center justify-center p-4">
            <div className="w-full max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-xl overflow-hidden">
                <div className="p-8 flex flex-col items-center text-center">
                    <div className="w-12 h-12 bg-indigo-500/10 text-indigo-500 rounded-xl flex items-center justify-center mb-6">
                        <Box className="w-6 h-6" />
                    </div>
                    <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mb-2">Bem-vindo ao OrceIA</h1>
                    <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-8">
                        Identifique sua Construtora para acessar o Cérebro Organizacional e isolar seus dados B2B.
                    </p>

                    <form onSubmit={handleLogin} className="w-full space-y-4">
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                            <input
                                type="text"
                                value={tenant}
                                onChange={(e) => setTenant(e.target.value)}
                                placeholder="Ex: Construtora Alfa"
                                className="w-full pl-10 pr-4 py-3 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
                                required
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading || !tenant.trim()}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? 'Entrando...' : 'Acessar Workspace'}
                            {!loading && <ArrowRight className="w-4 h-4" />}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
