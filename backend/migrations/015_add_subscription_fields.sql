-- Migration: Add subscription fields for Polar payment integration
-- Model: Trial (7-day free) -> Pro (paid subscription)

-- Add subscription fields to user_settings
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'trial';
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'trialing';
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS polar_customer_id TEXT;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS polar_subscription_id TEXT;

-- Index for quick lookups by Polar IDs
CREATE INDEX IF NOT EXISTS ix_user_settings_polar_customer_id ON user_settings(polar_customer_id);
CREATE INDEX IF NOT EXISTS ix_user_settings_polar_subscription_id ON user_settings(polar_subscription_id);

-- Set trial_ends_at for existing users (7 days from now)
UPDATE user_settings
SET trial_ends_at = NOW() + INTERVAL '7 days'
WHERE trial_ends_at IS NULL;
