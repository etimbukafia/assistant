-- Migration: Create calendar_events table
-- 013_create_calendar_events.sql

CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    
    -- Event details
    title VARCHAR NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    participants JSONB DEFAULT '[]',
    organizer VARCHAR,
    timezone VARCHAR DEFAULT 'UTC',
    location VARCHAR,
    
    -- Source: created (by us) | synced (from calendar)
    source VARCHAR DEFAULT 'created',
    
    -- Relations (for created events)
    source_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    source_suggestion_id INTEGER REFERENCES scheduling_suggestions(id) ON DELETE SET NULL,
    
    -- External calendar integration
    provider VARCHAR DEFAULT 'google',
    external_event_id VARCHAR UNIQUE,
    calendar_id VARCHAR DEFAULT 'primary',
    last_synced_at TIMESTAMPTZ,
    
    -- Meeting briefing
    briefing JSONB,
    briefing_generated_at TIMESTAMPTZ,
    related_message_ids JSONB DEFAULT '[]',
    related_task_ids JSONB DEFAULT '[]',
    
    -- Status: upcoming | completed | cancelled | pending | created | failed
    status VARCHAR DEFAULT 'upcoming',
    error_message TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source ON calendar_events(source);
CREATE INDEX IF NOT EXISTS idx_calendar_events_external_id ON calendar_events(external_event_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source_message ON calendar_events(source_message_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source_suggestion ON calendar_events(source_suggestion_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);
CREATE INDEX IF NOT EXISTS idx_calendar_events_created_at ON calendar_events(created_at);
