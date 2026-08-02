ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS raw_text TEXT;

ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS classification_status TEXT NOT NULL DEFAULT 'classified';

ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS classification_confidence DOUBLE PRECISION;

ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS classification_rationale TEXT;

ALTER TABLE context_entries
ADD COLUMN IF NOT EXISTS user_corrected BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE context_entries
DROP CONSTRAINT IF EXISTS ck_context_entries_type;

ALTER TABLE context_entries
ADD CONSTRAINT ck_context_entries_type
CHECK (type IN ('decision','commitment','preference','preferences','risk','risks','relationship','relationships','insight'));

ALTER TABLE context_entries
DROP CONSTRAINT IF EXISTS ck_context_entries_classification_status;

ALTER TABLE context_entries
ADD CONSTRAINT ck_context_entries_classification_status
CHECK (classification_status IN ('pending','classified','user_corrected'));

UPDATE context_entries
SET raw_text = content
WHERE raw_text IS NULL;

UPDATE context_entries
SET classification_status = 'classified'
WHERE classification_status IS NULL;
