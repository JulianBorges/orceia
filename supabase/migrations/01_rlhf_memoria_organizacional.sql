-- Migration: 01_rlhf_memoria_organizacional.sql
-- Objetivo: Criar a tabela de Aprendizado por Feedback Humano (RLHF)

CREATE TABLE IF NOT EXISTS public.memoria_organizacional (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    termo_original VARCHAR(1000) NOT NULL,
    codigo_escolhido VARCHAR(255) NOT NULL,
    parecer TEXT,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Restrição de Unicidade: Cada tenant só pode ter 1 escolha preferida por termo exato
    CONSTRAINT uk_tenant_termo UNIQUE (tenant_id, termo_original)
);

-- Habilitando RLS (Row Level Security) para o futuro SaaS
ALTER TABLE public.memoria_organizacional ENABLE ROW LEVEL SECURITY;

-- Política Provisória (Permitir Tudo) até finalizarmos a Sprint de Multi-Tenancy
CREATE POLICY "Permitir leitura/escrita total temporariamente"
ON public.memoria_organizacional
FOR ALL
USING (true)
WITH CHECK (true);
