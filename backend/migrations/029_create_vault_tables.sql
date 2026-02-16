-- Migration: 029_create_vault_tables.sql
-- Description: Knowledge Vault tables, indexes, constraints, and RLS

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- vault_notes
-- ============================================================================
CREATE TABLE IF NOT EXISTS vault_notes (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    note_type TEXT NOT NULL,
    title TEXT NOT NULL,
    frontmatter JSONB DEFAULT '{}'::jsonb,
    body TEXT DEFAULT '',
    canonical_email TEXT NULL,
    aliases JSONB DEFAULT '[]'::jsonb,
    source TEXT DEFAULT 'manual',
    confidence FLOAT DEFAULT 1.0,
    status TEXT DEFAULT 'active',
    pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_referenced_at TIMESTAMPTZ NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vault_notes_user_slug
    ON vault_notes(user_id, slug);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vault_notes_user_canonical_email
    ON vault_notes(user_id, canonical_email)
    WHERE canonical_email IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_vault_notes_user_id ON vault_notes(user_id);
CREATE INDEX IF NOT EXISTS ix_vault_notes_note_type ON vault_notes(note_type);
CREATE INDEX IF NOT EXISTS ix_vault_notes_canonical_email ON vault_notes(canonical_email);
CREATE INDEX IF NOT EXISTS ix_vault_notes_updated_at ON vault_notes(updated_at);
CREATE INDEX IF NOT EXISTS ix_vault_notes_title_trgm ON vault_notes USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_vault_notes_body_trgm ON vault_notes USING GIN (body gin_trgm_ops);

-- ============================================================================
-- vault_links
-- ============================================================================
CREATE TABLE IF NOT EXISTS vault_links (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_note_id INTEGER NOT NULL REFERENCES vault_notes(id) ON DELETE CASCADE,
    target_note_id INTEGER NOT NULL REFERENCES vault_notes(id) ON DELETE CASCADE,
    link_type TEXT DEFAULT 'reference',
    context TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_vault_links_no_self CHECK (source_note_id <> target_note_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vault_links_unique_edge
    ON vault_links(source_note_id, target_note_id, link_type);
CREATE INDEX IF NOT EXISTS ix_vault_links_user_id ON vault_links(user_id);
CREATE INDEX IF NOT EXISTS ix_vault_links_source ON vault_links(source_note_id);
CREATE INDEX IF NOT EXISTS ix_vault_links_target ON vault_links(target_note_id);

-- Ensure denormalized vault_links.user_id matches note owners
CREATE OR REPLACE FUNCTION ensure_vault_link_user_consistency()
RETURNS TRIGGER AS $$
DECLARE
    source_user TEXT;
    target_user TEXT;
BEGIN
    SELECT user_id INTO source_user FROM vault_notes WHERE id = NEW.source_note_id;
    SELECT user_id INTO target_user FROM vault_notes WHERE id = NEW.target_note_id;

    IF source_user IS NULL OR target_user IS NULL THEN
        RAISE EXCEPTION 'Invalid vault link: source or target note not found';
    END IF;

    IF source_user <> target_user OR NEW.user_id <> source_user THEN
        RAISE EXCEPTION 'vault_links.user_id must match source and target note user_id';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vault_link_user_consistency ON vault_links;
CREATE TRIGGER trg_vault_link_user_consistency
BEFORE INSERT OR UPDATE ON vault_links
FOR EACH ROW
EXECUTE FUNCTION ensure_vault_link_user_consistency();

-- ============================================================================
-- vault_proposals
-- ============================================================================
CREATE TABLE IF NOT EXISTS vault_proposals (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    target_note_id INTEGER NULL REFERENCES vault_notes(id) ON DELETE SET NULL,
    proposal_type TEXT NOT NULL,
    proposed_data JSONB NOT NULL,
    diff_summary TEXT NULL,
    source_type TEXT NULL,
    source_id TEXT NULL,
    confidence FLOAT DEFAULT 0.5,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'pending', -- auto_approved reserved, unused in MVP
    rejection_reason TEXT NULL,
    rejection_category TEXT NULL,
    reviewed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_vault_proposals_user_id ON vault_proposals(user_id);
CREATE INDEX IF NOT EXISTS ix_vault_proposals_status ON vault_proposals(status);
CREATE INDEX IF NOT EXISTS ix_vault_proposals_created_at ON vault_proposals(created_at);
CREATE INDEX IF NOT EXISTS ix_vault_proposals_target_note ON vault_proposals(target_note_id);

-- ============================================================================
-- vault_metrics_daily
-- ============================================================================
CREATE TABLE IF NOT EXISTS vault_metrics_daily (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    date DATE NOT NULL,
    context_attempt_count INTEGER DEFAULT 0,
    context_injected_count INTEGER DEFAULT 0,
    notes_referenced_count INTEGER DEFAULT 0,
    proposals_created_count INTEGER DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_vault_metrics_daily_user_date
    ON vault_metrics_daily(user_id, date);
CREATE INDEX IF NOT EXISTS ix_vault_metrics_daily_user_id ON vault_metrics_daily(user_id);

-- ============================================================================
-- contact_contexts additions
-- ============================================================================
ALTER TABLE contact_contexts ADD COLUMN IF NOT EXISTS promoted BOOLEAN DEFAULT FALSE;
ALTER TABLE contact_contexts ADD COLUMN IF NOT EXISTS vault_note_id INTEGER NULL REFERENCES vault_notes(id) ON DELETE SET NULL;
ALTER TABLE contact_contexts ADD COLUMN IF NOT EXISTS aliases JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS ix_contact_contexts_promoted ON contact_contexts(promoted);
CREATE INDEX IF NOT EXISTS ix_contact_contexts_vault_note_id ON contact_contexts(vault_note_id);

-- ============================================================================
-- RLS
-- ============================================================================
ALTER TABLE vault_notes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vault_notes_user_isolation ON vault_notes;
CREATE POLICY vault_notes_user_isolation ON vault_notes
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

ALTER TABLE vault_links ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vault_links_user_isolation ON vault_links;
CREATE POLICY vault_links_user_isolation ON vault_links
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

ALTER TABLE vault_proposals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vault_proposals_user_isolation ON vault_proposals;
CREATE POLICY vault_proposals_user_isolation ON vault_proposals
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

ALTER TABLE vault_metrics_daily ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS vault_metrics_daily_user_isolation ON vault_metrics_daily;
CREATE POLICY vault_metrics_daily_user_isolation ON vault_metrics_daily
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

