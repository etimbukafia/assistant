-- Migration 067: drop legacy context entry importance level
-- Importance was removed from the diary capture product model.

ALTER TABLE context_entries
    DROP CONSTRAINT IF EXISTS ck_context_entries_importance_level;

DROP INDEX IF EXISTS ix_context_entries_importance_level;

ALTER TABLE context_entries
    DROP COLUMN IF EXISTS importance_level;
