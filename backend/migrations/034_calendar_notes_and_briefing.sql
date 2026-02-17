-- Migration: 034_calendar_notes_and_briefing.sql
-- Purpose: Add calendar notes, all-day support, briefing schedule, and calendar settings

ALTER TABLE IF EXISTS calendar_events
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS all_day BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS briefing_scheduled_for TIMESTAMPTZ;

ALTER TABLE IF EXISTS user_settings
    ADD COLUMN IF NOT EXISTS default_calendar_id VARCHAR DEFAULT 'primary',
    ADD COLUMN IF NOT EXISTS auto_briefing_enabled BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS briefing_hours_before INTEGER DEFAULT 1;
