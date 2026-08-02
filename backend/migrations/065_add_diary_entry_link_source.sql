ALTER TABLE diary_entry_links
ADD COLUMN IF NOT EXISTS source VARCHAR(20);

UPDATE diary_entry_links
SET source = 'user'
WHERE source IS NULL OR source = '';

ALTER TABLE diary_entry_links
ALTER COLUMN source SET DEFAULT 'user';

ALTER TABLE diary_entry_links
ALTER COLUMN source SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_diary_entry_links_source'
    ) THEN
        ALTER TABLE diary_entry_links
        ADD CONSTRAINT ck_diary_entry_links_source
        CHECK (source IN ('user', 'teeks'));
    END IF;
END $$;
