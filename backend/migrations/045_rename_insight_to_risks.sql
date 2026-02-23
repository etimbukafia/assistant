-- Migration 045: Rename context_entries type 'insight' to 'risks'
-- The 'insight' type is being repurposed as 'risks' to better reflect its intent.
--
-- Run each statement separately in the Supabase SQL editor to avoid HTTP timeouts.
-- Statement 3 uses NOT VALID to skip the full-table scan on constraint creation;
-- Statement 4 validates in the background with a weaker lock.

-- Statement 1: drop the existing check constraint
ALTER TABLE context_entries DROP CONSTRAINT IF EXISTS ck_context_entries_type;

-- Statement 2: migrate existing rows
UPDATE context_entries SET type = 'risks' WHERE type = 'insight';

-- Statement 3: re-add constraint without immediate full-table validation
ALTER TABLE context_entries ADD CONSTRAINT ck_context_entries_type
    CHECK (type IN ('decision', 'commitment', 'preferences', 'risks', 'relationships')) NOT VALID;

-- Statement 4: validate in the background (ShareUpdateExclusiveLock — non-blocking)
ALTER TABLE context_entries VALIDATE CONSTRAINT ck_context_entries_type;
