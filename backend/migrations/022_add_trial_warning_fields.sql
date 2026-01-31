-- Add trial warning tracking fields to user_settings
-- These fields prevent duplicate notifications when the scheduled job runs

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS last_trial_warning_sent TIMESTAMP WITH TIME ZONE DEFAULT NULL;

ALTER TABLE user_settings 
ADD COLUMN IF NOT EXISTS last_trial_warning_milestone VARCHAR(20) DEFAULT NULL;

COMMENT ON COLUMN user_settings.last_trial_warning_sent IS 'When the last trial expiration warning was sent';
COMMENT ON COLUMN user_settings.last_trial_warning_milestone IS 'Which milestone was last notified: 3_days, 1_day, expired, grace_ending';
