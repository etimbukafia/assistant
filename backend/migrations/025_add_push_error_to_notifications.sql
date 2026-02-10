-- Add push_error column to notifications table for tracking delivery failures
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS push_error TEXT;
