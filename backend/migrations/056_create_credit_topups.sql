-- One-time AI credit top-up purchases (idempotent by provider/payment id)
CREATE TABLE IF NOT EXISTS credit_topups (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    provider_payment_id VARCHAR NOT NULL,
    amount_minor INTEGER NOT NULL,
    currency VARCHAR NOT NULL DEFAULT 'USD',
    credits_added INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    provider_metadata JSONB DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_topups_provider_payment
    ON credit_topups(provider, provider_payment_id);

CREATE INDEX IF NOT EXISTS ix_credit_topups_user_id
    ON credit_topups(user_id);

CREATE INDEX IF NOT EXISTS ix_credit_topups_created_at
    ON credit_topups(created_at);
