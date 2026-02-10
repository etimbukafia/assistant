-- Migration: 028_add_pagination_indexes.sql
-- Description: Add missing indexes identified during pagination audit
-- Date: 2024-02-08

-- ============================================================================
-- TIER 1: Critical Missing Indexes
-- ============================================================================

-- Index for filtering messages by needs_reply status
-- Used in: GET /messages?needs_reply=true, system stats
CREATE INDEX IF NOT EXISTS ix_messages_needs_reply ON messages(needs_reply);

-- Index for time-range queries on completed tasks
-- Used in: Weekly digest stats, completed task aggregation
CREATE INDEX IF NOT EXISTS ix_tasks_completed_at ON tasks(completed_at);

-- ============================================================================
-- TIER 2: Optimization Indexes
-- ============================================================================

-- Composite index for thread-based message lookups
-- Used in: process_messages_batch(), thread state initialization
-- Improves batch processing performance when grouping messages by thread
CREATE INDEX IF NOT EXISTS ix_messages_user_thread ON messages(user_id, thread_id);

-- Composite index for deadline-based task queries
-- Used in: Digest due-today queries, deadline filtering
-- Helps tenant-isolated deadline range queries
CREATE INDEX IF NOT EXISTS ix_tasks_user_deadline ON tasks(user_id, deadline);

-- ============================================================================
-- Notes:
-- - All indexes use IF NOT EXISTS for idempotent migrations
-- - Compatible with both PostgreSQL (production) and SQLite (testing)
-- - Tier 3 indexes (priority) deferred pending performance monitoring
-- ============================================================================
