-- Add executive profile fields to user_settings
ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS exec_full_name TEXT,
    ADD COLUMN IF NOT EXISTS exec_preferred_name TEXT,
    ADD COLUMN IF NOT EXISTS exec_role TEXT,
    ADD COLUMN IF NOT EXISTS exec_preferences TEXT;
