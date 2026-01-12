-- Migration: Add data lifecycle fields to messages and gmail_accounts tables
-- Date: 2025-12-27
-- Description: Adds fields for content expiration, source deletion tracking, encryption status,
--              and Gmail History API tracking for deletion sync

-- =============================================================================
-- Messages table: Data lifecycle fields
-- =============================================================================

-- Add content_expired column (True when body deleted after retention period)
ALTER TABLE messages ADD COLUMN content_expired BOOLEAN DEFAULT FALSE;

-- Add source_deleted column (True when Gmail reports message deleted)
ALTER TABLE messages ADD COLUMN source_deleted BOOLEAN DEFAULT FALSE;

-- Add body_encrypted column (True when body is encrypted at rest)
ALTER TABLE messages ADD COLUMN body_encrypted BOOLEAN DEFAULT FALSE;

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_messages_content_expired ON messages(content_expired);
CREATE INDEX IF NOT EXISTS idx_messages_source_deleted ON messages(source_deleted);

-- Composite index for cleanup job queries
CREATE INDEX IF NOT EXISTS idx_messages_lifecycle ON messages(content_expired, source_deleted, received_at);

-- =============================================================================
-- Gmail Accounts table: History API tracking
-- =============================================================================

-- Add last_history_id column for tracking Gmail deletions via History API
ALTER TABLE gmail_accounts ADD COLUMN last_history_id TEXT;

-- =============================================================================
-- Note: Run this migration manually with SQLite:
--   sqlite3 assistant.db < migrations/004_add_data_lifecycle_fields.sql
--
-- Or the application will auto-create these columns on startup via SQLAlchemy
-- Base.metadata.create_all() if the table already exists.
-- =============================================================================
