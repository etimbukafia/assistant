-- 051_add_dodo_subscription_fields.sql
-- Add Dodo billing linkage fields while keeping Polar fields for provider fallback.

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS dodo_customer_id TEXT;

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS dodo_subscription_id TEXT;

CREATE INDEX IF NOT EXISTS idx_user_settings_dodo_customer_id
  ON user_settings (dodo_customer_id);

CREATE INDEX IF NOT EXISTS idx_user_settings_dodo_subscription_id
  ON user_settings (dodo_subscription_id);
