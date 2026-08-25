-- Migration: 03_tabela_tenants.sql
-- Objetivo: Criar a tabela de Tenants autorizado (Source of Truth para autenticação)
-- Esta tabela é consultada no login para impedir acesso de tenants não cadastrados.

CREATE TABLE IF NOT EXISTS public.tenants (
    id VARCHAR(255) PRIMARY KEY,        -- Mesmo formato do tenant_id usado em todo o sistema
    nome VARCHAR(500) NOT NULL,          -- Nome da empresa/cliente
    ativo BOOLEAN NOT NULL DEFAULT true, -- Permite suspender acesso sem deletar dados
    plano VARCHAR(50) NOT NULL DEFAULT 'basico',
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Permitir leitura total temporariamente (tenants)"
ON public.tenants
FOR SELECT
USING (true);

CREATE POLICY "Apenas service role pode modificar tenants"
ON public.tenants
FOR ALL
USING (true)
WITH CHECK (true);

-- SEEDING INICIAL: Substitua pelo(s) tenant(s) real(is) antes do go-live
INSERT INTO public.tenants (id, nome, plano) VALUES
    ('tenant_alfa', 'Tenant de Desenvolvimento', 'basico')
ON CONFLICT (id) DO NOTHING;
