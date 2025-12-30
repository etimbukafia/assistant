-- Migration: Add AgentActivityLog table
-- Date: 2025-12-22
-- Description: Adds agent_activity_log table to track autonomous agent actions

-- Create agent_activity_log table
CREATE TABLE IF NOT EXISTS agent_activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Agent identification
    orchestrator_id TEXT,
    module_name TEXT,

    -- Action details
    action_type TEXT,
    action_description TEXT,
    confidence REAL,

    -- User-facing information
    user_visible_message TEXT,

    -- Relations
    related_message_id INTEGER,
    related_task_id INTEGER,

    -- Decision context (JSON)
    decision_context TEXT,  -- JSON stored as TEXT in SQLite
    action_result TEXT,      -- JSON stored as TEXT in SQLite

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (related_message_id) REFERENCES messages(id),
    FOREIGN KEY (related_task_id) REFERENCES tasks(id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_agent_activity_log_action_type ON agent_activity_log(action_type);
CREATE INDEX IF NOT EXISTS idx_agent_activity_log_related_message ON agent_activity_log(related_message_id);
CREATE INDEX IF NOT EXISTS idx_agent_activity_log_related_task ON agent_activity_log(related_task_id);
CREATE INDEX IF NOT EXISTS idx_agent_activity_log_created_at ON agent_activity_log(created_at);

-- Note: This migration is optional if you're using SQLAlchemy's Base.metadata.create_all()
-- The table will be created automatically when the app starts.
-- However, this script is useful for manual database setup or inspection.
