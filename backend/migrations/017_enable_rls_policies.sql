-- Migration: Enable Row Level Security (RLS) for multi-tenant isolation
--
-- This migration:
-- 1. Creates a helper function to get current user from session config
-- 2. Enables RLS on all user-owned tables
-- 3. Creates policies that filter rows by user_id
--
-- How it works:
-- - FastAPI sets `app.user_id` in PostgreSQL session via set_config()
-- - RLS policies use current_user_id() to filter rows automatically
-- - No manual WHERE user_id = ? needed in application code
--
-- IMPORTANT: Run this AFTER migration 014 (which adds user_id columns)

-- =====================================================
-- Helper function to get current user ID from session
-- =====================================================
CREATE OR REPLACE FUNCTION current_user_id()
RETURNS TEXT AS $$
    SELECT NULLIF(current_setting('app.user_id', true), '')::TEXT;
$$ LANGUAGE SQL STABLE;

COMMENT ON FUNCTION current_user_id() IS
    'Returns the current user ID set by the application via set_config(). Used by RLS policies.';

-- =====================================================
-- Messages table
-- =====================================================
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS messages_user_isolation ON messages;
CREATE POLICY messages_user_isolation ON messages
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

COMMENT ON POLICY messages_user_isolation ON messages IS
    'Users can only access their own messages. Allows all access when user_id not set (migrations, admin).';

-- =====================================================
-- Tasks table
-- =====================================================
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tasks_user_isolation ON tasks;
CREATE POLICY tasks_user_isolation ON tasks
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Thread states table
-- =====================================================
ALTER TABLE thread_states ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS thread_states_user_isolation ON thread_states;
CREATE POLICY thread_states_user_isolation ON thread_states
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Calendar events table
-- =====================================================
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS calendar_events_user_isolation ON calendar_events;
CREATE POLICY calendar_events_user_isolation ON calendar_events
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Scheduling suggestions table
-- =====================================================
ALTER TABLE scheduling_suggestions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scheduling_suggestions_user_isolation ON scheduling_suggestions;
CREATE POLICY scheduling_suggestions_user_isolation ON scheduling_suggestions
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Gmail accounts table
-- =====================================================
ALTER TABLE gmail_accounts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS gmail_accounts_user_isolation ON gmail_accounts;
CREATE POLICY gmail_accounts_user_isolation ON gmail_accounts
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- User settings table
-- =====================================================
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_settings_user_isolation ON user_settings;
CREATE POLICY user_settings_user_isolation ON user_settings
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Digests table
-- =====================================================
ALTER TABLE digests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS digests_user_isolation ON digests;
CREATE POLICY digests_user_isolation ON digests
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Principal memory table (user preferences)
-- =====================================================
ALTER TABLE principal_memory ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS principal_memory_user_isolation ON principal_memory;
CREATE POLICY principal_memory_user_isolation ON principal_memory
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Decision patterns table
-- =====================================================
ALTER TABLE decision_patterns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS decision_patterns_user_isolation ON decision_patterns;
CREATE POLICY decision_patterns_user_isolation ON decision_patterns
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Contact contexts table
-- =====================================================
ALTER TABLE contact_contexts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS contact_contexts_user_isolation ON contact_contexts;
CREATE POLICY contact_contexts_user_isolation ON contact_contexts
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Task queue table (background jobs)
-- =====================================================
-- Note: task_queue may need different handling if jobs run without user context
ALTER TABLE task_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS task_queue_user_isolation ON task_queue;
CREATE POLICY task_queue_user_isolation ON task_queue
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Tables that DON'T need RLS (linked via foreign keys)
-- =====================================================
-- task_reminders: Linked to tasks via task_id, inherits isolation
-- agent_activity_log: Audit log, may need separate access control

-- =====================================================
-- Verification query (run manually to check policies)
-- =====================================================
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
-- FROM pg_policies
-- WHERE tablename IN ('messages', 'tasks', 'user_settings', 'thread_states');
