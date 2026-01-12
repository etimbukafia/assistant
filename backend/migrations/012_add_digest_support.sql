-- Migration: Add outbound tracking and digest support
-- 012_add_digest_support.sql

-- ============================================================================
-- Part 1: Outbound Reply Detection (Prerequisite)
-- ============================================================================

-- Add last_outbound_at to thread_states for tracking user replies
ALTER TABLE thread_states ADD COLUMN IF NOT EXISTS last_outbound_at TIMESTAMPTZ;

-- ============================================================================
-- Part 2: Digest Preferences (UserSettings extension)
-- ============================================================================

-- Add digest_preferences JSON column to user_settings
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS digest_preferences JSONB DEFAULT '{
    "enabled": false,
    "morning_briefing": {
        "enabled": true,
        "time": "08:00",
        "include": ["tasks", "threads", "calendar"]
    },
    "end_of_day": {
        "enabled": true,
        "time": "18:00",
        "include": ["completed", "pending", "tomorrow"]
    },
    "weekly_review": {
        "enabled": true,
        "day": "monday",
        "time": "09:00",
        "include": ["waiting_for", "overdue", "stats"]
    },
    "delivery_channel": "email"
}'::jsonb;

-- ============================================================================
-- Part 3: Digests Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS digests (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR NOT NULL,
    
    -- Digest info
    digest_type VARCHAR NOT NULL,  -- morning_briefing | end_of_day | weekly_review
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    
    -- Content
    content JSONB NOT NULL,
    html_content TEXT,
    text_content TEXT,
    
    -- Delivery
    delivery_channel VARCHAR NOT NULL,  -- email | telegram | push
    delivery_status VARCHAR DEFAULT 'pending',  -- pending | sent | failed
    delivered_at TIMESTAMPTZ,
    delivery_error TEXT,
    
    -- Stats for the digest
    task_count INTEGER DEFAULT 0,
    thread_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_digests_user_email ON digests(user_email);
CREATE INDEX IF NOT EXISTS idx_digests_type ON digests(digest_type);
CREATE INDEX IF NOT EXISTS idx_digests_created_at ON digests(created_at);
