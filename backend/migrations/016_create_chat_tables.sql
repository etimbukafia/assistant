-- AI Chat tables for conversational interface
-- Session types: 'command' (30 days retention) or 'reflection' (24 hours retention)

-- Ensure user_settings.user_id has unique constraint (required for FK reference)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'user_settings_user_id_key'
    ) THEN
        ALTER TABLE user_settings ADD CONSTRAINT user_settings_user_id_key UNIQUE (user_id);
    END IF;
END $$;

-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES user_settings(user_id) ON DELETE CASCADE,
    session_type TEXT NOT NULL DEFAULT 'command',
    title TEXT,  -- Optional title for session list
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    state JSONB DEFAULT '{}'::jsonb
);

-- Conversation messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user', 'assistant', or 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Pending actions awaiting user approval
CREATE TABLE IF NOT EXISTS chat_pending_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    action_data JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_last_activity ON chat_sessions(last_activity_at);
CREATE INDEX IF NOT EXISTS ix_chat_sessions_type_activity ON chat_sessions(session_type, last_activity_at);
CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS ix_chat_pending_actions_session_id ON chat_pending_actions(session_id);
CREATE INDEX IF NOT EXISTS ix_chat_pending_actions_status ON chat_pending_actions(status) WHERE status = 'pending';
