-- Migration: Add user_id columns for multi-tenant support
-- Adds user_id to all user-owned tables for tenant isolation

-- =====================================================
-- Messages table
-- =====================================================
ALTER TABLE messages ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS ix_messages_user_status ON messages(user_id, status);

-- =====================================================
-- Tasks table
-- =====================================================
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS ix_tasks_user_status ON tasks(user_id, status);

-- =====================================================
-- Thread states table
-- =====================================================
ALTER TABLE thread_states ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_thread_states_user_id ON thread_states(user_id);

-- =====================================================
-- Calendar events table
-- =====================================================
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_calendar_events_user_id ON calendar_events(user_id);
CREATE INDEX IF NOT EXISTS ix_calendar_events_user_start ON calendar_events(user_id, start_time);

-- =====================================================
-- Scheduling suggestions table
-- =====================================================
ALTER TABLE scheduling_suggestions ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_scheduling_suggestions_user_id ON scheduling_suggestions(user_id);

-- =====================================================
-- Gmail accounts table
-- =====================================================
ALTER TABLE gmail_accounts ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_gmail_accounts_user_id ON gmail_accounts(user_id);

-- =====================================================
-- User settings table (add user_id alongside user_email)
-- =====================================================
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_user_settings_user_id ON user_settings(user_id);

-- =====================================================
-- Digests table (add user_id alongside user_email)
-- =====================================================
ALTER TABLE digests ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_digests_user_id ON digests(user_id);
