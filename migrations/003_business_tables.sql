-- Business tables for franchise training and recruitment management.
-- These are created in the application Supabase project (not the agent PostgreSQL database).
-- Run this migration in your Supabase SQL editor or via supabase CLI.

-- =============================================================================
-- TRAINING MANAGEMENT
-- =============================================================================

-- Franchise units (stores/locations)
CREATE TABLE IF NOT EXISTS unidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome TEXT NOT NULL,
    telefone TEXT,                          -- E.164 preferred (e.g. +5511999999999)
    email TEXT,
    responsavel TEXT,                       -- contact name at the unit
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    arquivado BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_unidades_telefone ON unidades (telefone);
CREATE INDEX IF NOT EXISTS idx_unidades_arquivado ON unidades (arquivado);

-- Training schedule (cronograma)
CREATE TABLE IF NOT EXISTS cronograma (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome TEXT NOT NULL,
    descricao TEXT,
    data DATE NOT NULL,                     -- training date
    horario TIME,                           -- optional start time
    tipo TEXT,                              -- e.g. 'presencial', 'online', 'hibrido'
    local TEXT,                             -- venue or meeting link
    ativo BOOLEAN NOT NULL DEFAULT FALSE,   -- set to TRUE via ativar_treinamento tool
    arquivado BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cronograma_data ON cronograma (data);
CREATE INDEX IF NOT EXISTS idx_cronograma_ativo ON cronograma (ativo);
CREATE INDEX IF NOT EXISTS idx_cronograma_arquivado ON cronograma (arquivado);

-- Training attendance records (inscricoes)
-- One row per unit per training; resposta tracks YES/NO/pending confirmation.
CREATE TABLE IF NOT EXISTS inscricoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cronograma_id UUID NOT NULL REFERENCES cronograma (id) ON DELETE CASCADE,
    unidade_id UUID REFERENCES unidades (id) ON DELETE SET NULL,
    -- Fallback fields when unit is not in the unidades table
    responsavel_nome TEXT,
    responsavel_telefone TEXT,
    resposta TEXT NOT NULL DEFAULT 'pendente' CHECK (resposta IN ('pendente', 'sim', 'nao')),
    observacoes TEXT,
    arquivado BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inscricoes_cronograma ON inscricoes (cronograma_id);
CREATE INDEX IF NOT EXISTS idx_inscricoes_unidade ON inscricoes (unidade_id);
CREATE INDEX IF NOT EXISTS idx_inscricoes_resposta ON inscricoes (resposta);
CREATE INDEX IF NOT EXISTS idx_inscricoes_arquivado ON inscricoes (arquivado);

-- =============================================================================
-- RECRUITMENT PIPELINE
-- =============================================================================

-- Job positions (vagas)
CREATE TABLE IF NOT EXISTS vagas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo TEXT NOT NULL,
    descricao TEXT,
    requisitos TEXT,
    local TEXT,
    tipo TEXT,                              -- e.g. 'clt', 'pj', 'estagio'
    salario TEXT,                           -- free-form (e.g. "R$ 2.500 + benefícios")
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    arquivado BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vagas_ativa ON vagas (ativa);
CREATE INDEX IF NOT EXISTS idx_vagas_arquivado ON vagas (arquivado);

-- Candidates (candidatos)
-- Submitted via Tally webhook; CV analyzed by GPT-4o in background.
CREATE TABLE IF NOT EXISTS candidatos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vaga_id UUID REFERENCES vagas (id) ON DELETE SET NULL,
    nome TEXT NOT NULL,
    email TEXT,
    telefone TEXT,                          -- E.164 preferred
    pdf_url TEXT,                           -- original CV PDF download URL
    texto_pdf TEXT,                         -- extracted text from CV (cached after first extraction)
    nota INTEGER CHECK (nota >= 0 AND nota <= 10),  -- GPT-4o suitability score
    justificativa TEXT,                     -- GPT-4o explanation (max ~300 chars)
    perfil_comportamental TEXT,             -- generated from behavioral assessment form (Tally)
    status TEXT NOT NULL DEFAULT 'recebido' CHECK (
        status IN (
            'recebido',
            'analisado',
            'contatado',
            'em_processo',
            'aprovado',
            'reprovado',
            'desistiu',
            'comportamental_recebido'
        )
    ),
    observacoes TEXT,
    arquivado BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidatos_vaga ON candidatos (vaga_id);
CREATE INDEX IF NOT EXISTS idx_candidatos_status ON candidatos (status);
CREATE INDEX IF NOT EXISTS idx_candidatos_nota ON candidatos (nota DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_candidatos_arquivado ON candidatos (arquivado);

-- =============================================================================
-- Auto-update updated_at via trigger (optional but recommended)
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['unidades', 'cronograma', 'inscricoes', 'vagas', 'candidatos']
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I; '
            'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION set_updated_at();',
            t, t, t, t
        );
    END LOOP;
END;
$$;
