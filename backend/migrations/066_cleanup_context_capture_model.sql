-- Migration 066: Clean up diary capture model
-- Goals:
-- 1. Canonicalize context types to the 5 product categories
-- 2. Drop classifier rationale persistence

UPDATE context_entries
SET type = CASE
    WHEN type = 'preferences' THEN 'preference'
    WHEN type = 'risks' THEN 'risk'
    WHEN type IN ('relationship', 'relationships') THEN 'insight'
    ELSE type
END
WHERE type IN ('preferences', 'risks', 'relationship', 'relationships');

UPDATE context_entries
SET classification_suggested_type = CASE
    WHEN classification_suggested_type = 'preferences' THEN 'preference'
    WHEN classification_suggested_type = 'risks' THEN 'risk'
    WHEN classification_suggested_type IN ('relationship', 'relationships') THEN 'insight'
    ELSE classification_suggested_type
END
WHERE classification_suggested_type IN ('preferences', 'risks', 'relationship', 'relationships');

ALTER TABLE context_entries
    DROP CONSTRAINT IF EXISTS ck_context_entries_type;

ALTER TABLE context_entries
    ADD CONSTRAINT ck_context_entries_type
    CHECK (type IN ('decision','commitment','preference','risk','insight')) NOT VALID;

ALTER TABLE context_entries
    DROP CONSTRAINT IF EXISTS ck_context_entries_classification_suggested_type;

ALTER TABLE context_entries
    ADD CONSTRAINT ck_context_entries_classification_suggested_type
    CHECK (
        classification_suggested_type IS NULL
        OR classification_suggested_type IN ('decision','commitment','preference','risk','insight')
    ) NOT VALID;

ALTER TABLE context_entries
    DROP COLUMN IF EXISTS classification_rationale;
