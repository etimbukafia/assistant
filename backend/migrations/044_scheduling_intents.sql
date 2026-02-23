-- Migration 044: Create scheduling_intents table
-- Replaces the eager scheduling_suggestions pipeline with a lean intent record.
-- Suggestions (slots, draft replies) are now generated on-demand by CalendarOrchestrator.

CREATE TABLE IF NOT EXISTS scheduling_intents (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    thread_id TEXT,
    sender_name TEXT,
    sender_email TEXT,
    intent_type TEXT NOT NULL DEFAULT 'availability_request',
    -- availability_request | time_request | meeting_confirmation | meeting_reminder | reschedule_request
    intent_summary TEXT,           -- LLM-generated: "Sarah asked when you're free for the Q4 review"
    meeting_title TEXT,            -- extracted meeting title for calendar matching
    meeting_date DATE,             -- extracted date for calendar matching (null if not specified)
    matched_event_id INTEGER REFERENCES calendar_events(id) ON DELETE SET NULL,
    -- populated for meeting_reminder when a matching calendar event is found
    status TEXT NOT NULL DEFAULT 'pending',
    -- pending | sent | dismissed | acknowledged | added | expired
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scheduling_intents_user_id ON scheduling_intents(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_intents_message_id ON scheduling_intents(message_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_intents_thread_id ON scheduling_intents(thread_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_intents_status ON scheduling_intents(status);

ALTER TABLE scheduling_intents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scheduling_intents_user_policy ON scheduling_intents;
CREATE POLICY scheduling_intents_user_policy ON scheduling_intents
    USING (user_id = current_setting('app.user_id', true));

-- scheduling_suggestions table is kept for data preservation.
-- It can be dropped in a future migration once all clients are updated.
