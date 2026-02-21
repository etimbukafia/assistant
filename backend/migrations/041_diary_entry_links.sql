-- Migration 041: Diary entry links
-- Supports multiple entity links per diary context entry (@mentions)

CREATE TABLE IF NOT EXISTS diary_entry_links (
    id SERIAL PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES context_entries(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,   -- contact | thread | message | event | task
    entity_id TEXT NOT NULL,            -- email for contacts, ref for others
    display_name TEXT NOT NULL,         -- the @label as shown to the user
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_diary_entry_links_entry_id ON diary_entry_links(entry_id);
