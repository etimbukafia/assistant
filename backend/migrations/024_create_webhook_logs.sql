-- Append-only webhook log for health monitoring and billing audit trail

CREATE TABLE IF NOT EXISTS webhook_logs (
    id SERIAL PRIMARY KEY,
    source VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    error TEXT,
    customer_id VARCHAR,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_webhook_logs_source ON webhook_logs(source);
CREATE INDEX IF NOT EXISTS ix_webhook_logs_event_type ON webhook_logs(event_type);
CREATE INDEX IF NOT EXISTS ix_webhook_logs_received_at ON webhook_logs(received_at);
