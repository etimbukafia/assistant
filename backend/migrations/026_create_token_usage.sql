-- Token usage tracking for LLM operations

CREATE TABLE IF NOT EXISTS token_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd FLOAT NOT NULL DEFAULT 0.0,
    operation VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_token_usage_user_id ON token_usage(user_id);
CREATE INDEX IF NOT EXISTS ix_token_usage_created_at ON token_usage(created_at);
CREATE INDEX IF NOT EXISTS ix_token_usage_operation ON token_usage(operation);
