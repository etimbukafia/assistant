-- Migration 046: Fix context_entries entity model
--
-- Changes:
-- 1. Replace 'assistant'/'executive' entity_type values with 'global'
-- 2. Add 'task' as a valid entity_type
-- 3. Add linked_to column (display name of the primary linked entity)
-- 4. Backfill entity_type, entity_id, linked_to from diary_entry_links for entries that have them
--
-- Run each statement separately in the Supabase SQL editor to avoid HTTP timeouts.

-- Statement 1: drop the existing entity_type check constraint
ALTER TABLE context_entries DROP CONSTRAINT IF EXISTS ck_context_entries_entity_type;

-- Statement 2: migrate 'assistant' and 'executive' rows to 'global'
UPDATE context_entries SET entity_type = 'global' WHERE entity_type IN ('assistant', 'executive');

-- Statement 3: add the new check constraint
ALTER TABLE context_entries ADD CONSTRAINT ck_context_entries_entity_type
    CHECK (entity_type IN ('global', 'contact', 'thread', 'message', 'event', 'task')) NOT VALID;

-- Statement 4: validate the constraint
ALTER TABLE context_entries VALIDATE CONSTRAINT ck_context_entries_entity_type;

-- Statement 5: add the linked_to column
ALTER TABLE context_entries ADD COLUMN IF NOT EXISTS linked_to TEXT;

-- Statement 6: backfill entity_type, entity_id, and linked_to from the primary diary_entry_link
-- (first link per entry, by insertion order) for entries that are still 'global' but have links
UPDATE context_entries ce
SET
    entity_type = dl.entity_type,
    entity_id   = dl.entity_id,
    linked_to   = dl.display_name
FROM (
    SELECT DISTINCT ON (entry_id)
        entry_id,
        entity_type,
        entity_id,
        display_name
    FROM diary_entry_links
    ORDER BY entry_id, id ASC
) dl
WHERE ce.id = dl.entry_id
  AND ce.entity_type = 'global';

-- Statement 7: index linked_to for display queries
CREATE INDEX IF NOT EXISTS ix_context_entries_linked_to
    ON context_entries (user_id, linked_to)
    WHERE linked_to IS NOT NULL;
