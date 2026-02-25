-- 053_add_dunning_state_to_user_settings.sql
-- Adds dunning state fields for calm payment recovery flow.

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS dunning_active BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS dunning_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dunning_deadline_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dunning_attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS dunning_last_notified_stage TEXT,
    ADD COLUMN IF NOT EXISTS dunning_last_payment_failed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dunning_suspended_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_user_settings_dunning_active ON user_settings(dunning_active);
CREATE INDEX IF NOT EXISTS idx_user_settings_dunning_deadline ON user_settings(dunning_deadline_at);
CREATE INDEX IF NOT EXISTS idx_user_settings_dunning_suspended ON user_settings(dunning_suspended_at);
