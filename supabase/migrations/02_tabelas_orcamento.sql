-- Migration: 02_tabelas_orcamento.sql
-- Objetivo: Criar a tabela mãe (planilhas) e a tabela filha (planilhas_linhas) com Integridade Referencial

-- 1. Tabela Mãe (planilhas)
CREATE TABLE IF NOT EXISTS public.planilhas (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    titulo VARCHAR(255) NOT NULL DEFAULT 'Nova Planilha',
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.planilhas ENABLE ROW LEVEL SECURITY;

-- 2. Tabela Filha (planilhas_linhas)
CREATE TABLE IF NOT EXISTS public.planilhas_linhas (
    id VARCHAR(255) PRIMARY KEY, -- ID gerado pelo Frontend (Zustand)
    id_planilha VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    codigo VARCHAR(255),
    descricao TEXT NOT NULL,
    unidade VARCHAR(50) NOT NULL,
    quantidade NUMERIC(15, 4) DEFAULT 0,
    preco_unitario NUMERIC(15, 4) DEFAULT 0,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Integridade Referencial (Deleção em Cascata)
    CONSTRAINT fk_planilha 
        FOREIGN KEY (id_planilha) 
        REFERENCES public.planilhas(id) 
        ON DELETE CASCADE
);

ALTER TABLE public.planilhas_linhas ENABLE ROW LEVEL SECURITY;

-- 3. Políticas Provisórias de Acesso (RLS)
-- Nota: A segurança real no momento é garantida pelo Backend (FastAPI) injetando a cláusula WHERE tenant_id = $x.
-- Mas habilitar a política é necessário para a inserção funcionar.
CREATE POLICY "Permitir leitura/escrita total temporariamente (planilhas)"
ON public.planilhas
FOR ALL
USING (true)
WITH CHECK (true);

CREATE POLICY "Permitir leitura/escrita total temporariamente (linhas)"
ON public.planilhas_linhas
FOR ALL
USING (true)
WITH CHECK (true);
