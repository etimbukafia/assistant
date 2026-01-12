-- Migration: Add missing columns to calendar_events table
-- 013b_alter_calendar_events.sql

-- Add missing columns (IF NOT EXISTS for Postgres 11+)
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS participants JSONB DEFAULT '[]';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS organizer VARCHAR;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS timezone VARCHAR DEFAULT 'UTC';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS location VARCHAR;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'created';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS source_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS source_suggestion_id INTEGER REFERENCES scheduling_suggestions(id) ON DELETE SET NULL;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS provider VARCHAR DEFAULT 'google';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS external_event_id VARCHAR UNIQUE;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS calendar_id VARCHAR DEFAULT 'primary';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS briefing JSONB;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS briefing_generated_at TIMESTAMPTZ;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS related_message_ids JSONB DEFAULT '[]';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS related_task_ids JSONB DEFAULT '[]';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'upcoming';
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Create indexes if not exist
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source ON calendar_events(source);
CREATE INDEX IF NOT EXISTS idx_calendar_events_external_id ON calendar_events(external_event_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source_message ON calendar_events(source_message_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source_suggestion ON calendar_events(source_suggestion_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);
CREATE INDEX IF NOT EXISTS idx_calendar_events_created_at ON calendar_events(created_at);
