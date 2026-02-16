-- Migration: 033_add_ui_telemetry_event_id.sql
-- Purpose: Add event_id for idempotent client telemetry ingestion.

ALTER TABLE ui_telemetry_events
ADD COLUMN IF NOT EXISTS event_id VARCHAR NULL;

CREATE INDEX IF NOT EXISTS ix_ui_telemetry_events_event_id
ON ui_telemetry_events(event_id);

-- Deduplicate per user when event_id is present.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ui_telemetry_events_user_event_id
ON ui_telemetry_events(user_id, event_id)
WHERE event_id IS NOT NULL;
