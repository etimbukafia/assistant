-- Add personal profile fields to user_settings
ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS full_name TEXT,
    ADD COLUMN IF NOT EXISTS preferred_name TEXT,
    ADD COLUMN IF NOT EXISTS role TEXT,
    ADD COLUMN IF NOT EXISTS personal_preferences TEXT;
