-- Migration: 032_create_ui_telemetry_events.sql
-- Description: Persistent frontend telemetry events for product analytics

CREATE TABLE IF NOT EXISTS ui_telemetry_events (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_payload JSONB DEFAULT '{}'::jsonb,
    page_path TEXT NULL,
    session_id TEXT NULL,
    client_ts TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ui_telemetry_events_user_id ON ui_telemetry_events(user_id);
CREATE INDEX IF NOT EXISTS ix_ui_telemetry_events_event_name ON ui_telemetry_events(event_name);
CREATE INDEX IF NOT EXISTS ix_ui_telemetry_events_created_at ON ui_telemetry_events(created_at);
CREATE INDEX IF NOT EXISTS ix_ui_telemetry_events_page_path ON ui_telemetry_events(page_path);

-- RLS
ALTER TABLE ui_telemetry_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ui_telemetry_events_user_isolation ON ui_telemetry_events;
CREATE POLICY ui_telemetry_events_user_isolation ON ui_telemetry_events
    FOR ALL
    USING (user_id = current_setting('app.user_id', true));
