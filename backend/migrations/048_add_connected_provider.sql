-- Migration: Add connected_provider to user_settings for single-provider mode (MVP)
-- 048_add_connected_provider.sql

ALTER TABLE user_settings
ADD COLUMN IF NOT EXISTS connected_provider VARCHAR DEFAULT 'none';

CREATE INDEX IF NOT EXISTS idx_user_settings_connected_provider
ON user_settings(connected_provider);
