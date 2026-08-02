ALTER TABLE context_entries
DROP CONSTRAINT IF EXISTS ck_context_entries_status;

ALTER TABLE context_entries
ADD CONSTRAINT ck_context_entries_status
CHECK (status IN ('active','resolved','stale','archived','forgotten'));
