-- Add action_points column to thread_states for quick-scan executive briefing
ALTER TABLE thread_states ADD COLUMN IF NOT EXISTS action_points JSONB DEFAULT '[]';
