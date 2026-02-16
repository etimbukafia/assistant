-- Migration: 031_create_daily_focus.sql
-- Description: Daily Focus / goal-setting table for the Focus tab

CREATE TABLE IF NOT EXISTS daily_focus (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    focus_date DATE NOT NULL DEFAULT CURRENT_DATE,

    -- Up to 3 daily goals: [{text: string, completed: boolean}]
    goals JSONB DEFAULT '[]'::jsonb,

    -- "Eat the frog" - FK to tasks table (the hardest task to do first)
    frog_task_id INTEGER NULL REFERENCES tasks(id) ON DELETE SET NULL,

    -- Weekly target text - same value for every row in the same ISO week
    weekly_target TEXT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_daily_focus_user_date
    ON daily_focus(user_id, focus_date);
CREATE INDEX IF NOT EXISTS ix_daily_focus_user_id ON daily_focus(user_id);

-- RLS
ALTER TABLE daily_focus ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS daily_focus_user_isolation ON daily_focus;
CREATE POLICY daily_focus_user_isolation ON daily_focus
    FOR ALL
    USING (user_id = current_setting('app.user_id', true));
