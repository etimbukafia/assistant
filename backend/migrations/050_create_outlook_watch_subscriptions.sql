-- Migration: Create outlook_watch_subscriptions table
-- 050_create_outlook_watch_subscriptions.sql

CREATE TABLE IF NOT EXISTS outlook_watch_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL UNIQUE,
    resource TEXT NOT NULL,
    client_state TEXT NOT NULL,
    expiration TIMESTAMP NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outlook_watch_user_id ON outlook_watch_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_outlook_watch_subscription_id ON outlook_watch_subscriptions(subscription_id);
CREATE INDEX IF NOT EXISTS idx_outlook_watch_expiration ON outlook_watch_subscriptions(expiration);
