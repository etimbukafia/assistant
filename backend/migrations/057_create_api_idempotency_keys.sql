-- Idempotency keys for mutating API requests (billing safety)
CREATE TABLE IF NOT EXISTS api_idempotency_keys (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    route_key VARCHAR NOT NULL,
    idempotency_key VARCHAR NOT NULL,
    request_hash VARCHAR NOT NULL,
    response_status INTEGER NOT NULL DEFAULT 0,
    response_body JSONB NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_api_idempotency_user_route_key
    ON api_idempotency_keys(user_id, route_key, idempotency_key);

CREATE INDEX IF NOT EXISTS ix_api_idempotency_expires
    ON api_idempotency_keys(expires_at);

