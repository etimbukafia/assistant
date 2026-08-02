ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS classification_suggested_type TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_context_entries_classification_suggested_type'
    ) THEN
        ALTER TABLE context_entries
        ADD CONSTRAINT ck_context_entries_classification_suggested_type
        CHECK (
            classification_suggested_type IS NULL
            OR classification_suggested_type IN (
                'decision',
                'commitment',
                'preference',
                'preferences',
                'risk',
                'risks',
                'relationship',
                'relationships',
                'insight'
            )
        );
    END IF;
END $$;
