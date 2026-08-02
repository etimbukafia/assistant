ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS input_source TEXT NOT NULL DEFAULT 'typed';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_context_entries_input_source'
    ) THEN
        ALTER TABLE context_entries
        ADD CONSTRAINT ck_context_entries_input_source
        CHECK (input_source IN ('typed', 'voice'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_context_entries_input_source
ON context_entries (input_source);
