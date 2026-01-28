-- Migration: Create notification tables for push + in-app notification feed
--
-- Tables:
-- - device_tokens: Expo push notification tokens per user
-- - notifications: Feed entries with push delivery tracking
--
-- Also adds notification_preferences column to user_settings

-- =====================================================
-- Device Tokens (Expo Push)
-- =====================================================
CREATE TABLE IF NOT EXISTS device_tokens (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    expo_push_token TEXT NOT NULL UNIQUE,
    device_name TEXT,
    platform TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_device_tokens_user_id ON device_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_device_tokens_active ON device_tokens(is_active) WHERE is_active = TRUE;

-- =====================================================
-- Notifications (In-App Feed + Push Tracking)
-- =====================================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    category TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    target_type TEXT,
    target_id TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    push_sent BOOLEAN DEFAULT FALSE,
    push_sent_at TIMESTAMP WITH TIME ZONE,
    push_ticket_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_user_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_category ON notifications(category);

-- =====================================================
-- RLS Policies
-- =====================================================
ALTER TABLE device_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS device_tokens_user_isolation ON device_tokens;
CREATE POLICY device_tokens_user_isolation ON device_tokens
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notifications_user_isolation ON notifications;
CREATE POLICY notifications_user_isolation ON notifications
    FOR ALL
    USING (user_id = current_user_id() OR current_user_id() IS NULL);

-- =====================================================
-- Add notification_preferences to user_settings
-- =====================================================
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS notification_preferences JSONB DEFAULT '{
    "push_enabled": true,
    "push_urgent_tasks": true,
    "push_deadlines": true,
    "push_digests": true,
    "push_briefings": true
}'::jsonb;
