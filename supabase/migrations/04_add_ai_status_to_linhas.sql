-- Migration: 04_add_ai_status_to_linhas.sql
-- Objetivo: Adicionar campos de persistência da Inteligência Artificial para não reprocessar itens

ALTER TABLE public.planilhas_linhas 
ADD COLUMN IF NOT EXISTS ai_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS ai_parecer_tecnico TEXT;
