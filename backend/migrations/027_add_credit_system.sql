-- Credit system for AI usage gating
-- Trial: 100 credits = $1.00 USD, Pro: 500 credits = $5.00 USD
-- Only Gemini models consume credits (not Gemma)

ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS credits_used FLOAT DEFAULT 0.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS credits_limit FLOAT DEFAULT 1.0;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS credits_period_start TIMESTAMPTZ;

-- Add index on model column in token_usage for efficient Gemini filtering
CREATE INDEX IF NOT EXISTS ix_token_usage_model ON token_usage(model);
