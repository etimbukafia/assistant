-- Migration: Add task deadline fields for Smart Todo List
-- Adds 5 new columns to support AI deadline extraction with user control

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deadline TIMESTAMP;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deadline_source VARCHAR DEFAULT 'explicit';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deadline_confidence FLOAT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deadline_user_confirmed BOOLEAN DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS urgency_suggested_by_ai BOOLEAN DEFAULT FALSE;

-- Create index on deadline for efficient sorting and filtering
CREATE INDEX IF NOT EXISTS ix_tasks_deadline ON tasks(deadline);
