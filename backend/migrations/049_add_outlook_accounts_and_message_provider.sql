-- Migration: Add Outlook accounts and message provider fields
-- 049_add_outlook_accounts_and_message_provider.sql

CREATE TABLE IF NOT EXISTS outlook_accounts (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE,
    user_id TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expiry TIMESTAMP,
    last_sync TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_delta_token TEXT,
    initial_sync_completed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS ix_outlook_accounts_user_id ON outlook_accounts(user_id);

ALTER TABLE messages
ADD COLUMN IF NOT EXISTS provider VARCHAR DEFAULT 'google',
ADD COLUMN IF NOT EXISTS external_message_id VARCHAR,
ADD COLUMN IF NOT EXISTS external_thread_id VARCHAR;

CREATE INDEX IF NOT EXISTS ix_messages_provider ON messages(provider);
CREATE INDEX IF NOT EXISTS ix_messages_external_message_id ON messages(external_message_id);
CREATE INDEX IF NOT EXISTS ix_messages_external_thread_id ON messages(external_thread_id);
