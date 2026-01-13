-- Migration: Add chat tables for AI Chat feature
-- Based on ai_chat.md spec

-- Chat sessions (retention varies by type)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES user_settings(user_id) ON DELETE CASCADE,
    session_type TEXT NOT NULL DEFAULT 'command',  -- 'command' (30 days) or 'reflection' (24 hours)
    title TEXT,  -- Optional title for display
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    state JSONB NOT NULL DEFAULT '{}'::jsonb  -- ConversationState
);

-- Conversation messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb  -- tool calls, pending actions, etc.
);

-- Pending actions awaiting approval
CREATE TABLE IF NOT EXISTS chat_pending_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,  -- 'draft_reply', 'create_task', 'update_principal_memory', etc.
    action_data JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_last_activity ON chat_sessions(last_activity_at);
CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS ix_chat_pending_actions_session_id ON chat_pending_actions(session_id);
CREATE INDEX IF NOT EXISTS ix_chat_pending_actions_status ON chat_pending_actions(status);

-- Enable RLS
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_pending_actions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for chat_sessions
DROP POLICY IF EXISTS chat_sessions_user_policy ON chat_sessions;
CREATE POLICY chat_sessions_user_policy ON chat_sessions
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- RLS Policies for chat_messages (via session ownership)
DROP POLICY IF EXISTS chat_messages_user_policy ON chat_messages;
CREATE POLICY chat_messages_user_policy ON chat_messages
    FOR ALL
    USING (
        session_id IN (
            SELECT id FROM chat_sessions 
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    );

-- RLS Policies for chat_pending_actions (via session ownership)
DROP POLICY IF EXISTS chat_pending_actions_user_policy ON chat_pending_actions;
CREATE POLICY chat_pending_actions_user_policy ON chat_pending_actions
    FOR ALL
    USING (
        session_id IN (
            SELECT id FROM chat_sessions 
            WHERE user_id = current_setting('app.current_user_id', true)
        )
    );
