CREATE TABLE IF NOT EXISTS automation_user_settings (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    automation_id TEXT NOT NULL,
    configured BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    safety_mode TEXT NOT NULL DEFAULT 'review_required',
    execution_mode TEXT NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_automation_user_settings_user_automation UNIQUE (user_id, automation_id)
);

CREATE INDEX IF NOT EXISTS ix_automation_user_settings_user_id
    ON automation_user_settings (user_id);

CREATE INDEX IF NOT EXISTS ix_automation_user_settings_automation_id
    ON automation_user_settings (automation_id);

CREATE TABLE IF NOT EXISTS automation_runs (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    automation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    trigger TEXT NOT NULL DEFAULT 'manual',
    summary TEXT NULL,
    run_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_automation_runs_user_id
    ON automation_runs (user_id);

CREATE INDEX IF NOT EXISTS ix_automation_runs_automation_id
    ON automation_runs (automation_id);

CREATE INDEX IF NOT EXISTS ix_automation_runs_started_at
    ON automation_runs (started_at);
