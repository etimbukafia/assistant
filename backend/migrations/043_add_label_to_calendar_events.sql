-- Add label column to calendar_events
-- Labels drive briefing eligibility: only events with label='meeting' get a brief.
-- Auto-classified during sync via keyword heuristics; user can override.

ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS label TEXT;

-- Seed existing events with a basic classification:
-- any event with attendees likely came from a calendar invite → meeting
-- everything else → other
UPDATE calendar_events
SET label = CASE
    WHEN participants IS NOT NULL AND participants::text != '[]' AND participants::text != 'null'
        THEN 'meeting'
    ELSE 'other'
END
WHERE label IS NULL;

CREATE INDEX IF NOT EXISTS idx_calendar_events_label ON calendar_events(label);
