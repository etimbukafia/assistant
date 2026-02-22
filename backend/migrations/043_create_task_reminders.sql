-- Migration 043: Create task_reminders table
-- Stores an audit log of every reminder sent for a task.
-- Replaces missing table referenced in 017_enable_rls_policies.sql comments.

CREATE TABLE IF NOT EXISTS task_reminders (
    id              SERIAL PRIMARY KEY,
    task_id         INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,               -- denormalised for RLS queries
    reminder_type   TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled | urgent_nudge | digest | manual
    channel         TEXT NOT NULL DEFAULT 'push',        -- push | email | in_app
    reminded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered       BOOLEAN NOT NULL DEFAULT FALSE,
    delivery_error  TEXT,                        -- populated if push/email delivery failed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_reminders_task_id   ON task_reminders (task_id);
CREATE INDEX IF NOT EXISTS idx_task_reminders_user_id   ON task_reminders (user_id);
CREATE INDEX IF NOT EXISTS idx_task_reminders_reminded_at ON task_reminders (reminded_at DESC);

-- RLS: users can only see their own reminder records
ALTER TABLE task_reminders ENABLE ROW LEVEL SECURITY;

CREATE POLICY task_reminders_user_isolation ON task_reminders
    USING (user_id = current_setting('app.user_id', true));
