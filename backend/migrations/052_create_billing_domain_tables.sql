-- 052_create_billing_domain_tables.sql
-- First-class billing domain tables: plans, subscriptions, invoices, payment attempts, events.

CREATE TABLE IF NOT EXISTS billing_plans (
    id SERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    name TEXT,
    price_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    billing_interval TEXT NOT NULL DEFAULT 'monthly',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_billing_plans_provider_plan UNIQUE (provider, plan_id),
    CONSTRAINT ck_billing_plans_interval CHECK (billing_interval IN ('monthly','annual','one_time'))
);

CREATE INDEX IF NOT EXISTS idx_billing_plans_provider ON billing_plans(provider);
CREATE INDEX IF NOT EXISTS idx_billing_plans_plan_id ON billing_plans(plan_id);
CREATE INDEX IF NOT EXISTS idx_billing_plans_active ON billing_plans(is_active);

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_subscription_id TEXT,
    provider_customer_id TEXT,
    plan_id INTEGER REFERENCES billing_plans(id) ON DELETE SET NULL,
    plan_external_id TEXT,
    status TEXT NOT NULL DEFAULT 'trialing',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    canceled_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_billing_subscriptions_provider_sub UNIQUE (provider, provider_subscription_id),
    CONSTRAINT ck_billing_subscriptions_status CHECK (status IN ('active','trialing','cancel_scheduled','canceled','past_due','expired'))
);

CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_user_id ON billing_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_provider ON billing_subscriptions(provider);
CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_provider_customer_id ON billing_subscriptions(provider_customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_status ON billing_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_period_end ON billing_subscriptions(current_period_end);

CREATE TABLE IF NOT EXISTS billing_invoices (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_invoice_id TEXT,
    subscription_id INTEGER REFERENCES billing_subscriptions(id) ON DELETE SET NULL,
    provider_subscription_id TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    currency TEXT NOT NULL DEFAULT 'USD',
    amount_due_minor INTEGER,
    amount_paid_minor INTEGER,
    amount_remaining_minor INTEGER,
    invoice_pdf_url TEXT,
    hosted_invoice_url TEXT,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_billing_invoices_provider_invoice UNIQUE (provider, provider_invoice_id),
    CONSTRAINT ck_billing_invoices_status CHECK (status IN ('draft','open','paid','void','uncollectible','failed'))
);

CREATE INDEX IF NOT EXISTS idx_billing_invoices_user_id ON billing_invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_provider ON billing_invoices(provider);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_subscription_id ON billing_invoices(subscription_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_status ON billing_invoices(status);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_due_at ON billing_invoices(due_at);

CREATE TABLE IF NOT EXISTS billing_payment_attempts (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    invoice_id INTEGER REFERENCES billing_invoices(id) ON DELETE SET NULL,
    provider_attempt_id TEXT,
    provider_payment_id TEXT,
    provider_subscription_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    currency TEXT NOT NULL DEFAULT 'USD',
    amount_minor INTEGER,
    failure_code TEXT,
    failure_message TEXT,
    attempted_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_billing_payment_attempts_provider_attempt UNIQUE (provider, provider_attempt_id),
    CONSTRAINT ck_billing_payment_attempts_status CHECK (status IN ('pending','succeeded','failed','requires_action','canceled'))
);

CREATE INDEX IF NOT EXISTS idx_billing_payment_attempts_user_id ON billing_payment_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_payment_attempts_provider ON billing_payment_attempts(provider);
CREATE INDEX IF NOT EXISTS idx_billing_payment_attempts_invoice_id ON billing_payment_attempts(invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_payment_attempts_status ON billing_payment_attempts(status);
CREATE INDEX IF NOT EXISTS idx_billing_payment_attempts_attempted_at ON billing_payment_attempts(attempted_at);

CREATE TABLE IF NOT EXISTS billing_events (
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    provider TEXT NOT NULL,
    delivery_id TEXT,
    event_type TEXT NOT NULL,
    customer_id TEXT,
    customer_email TEXT,
    subscription_id TEXT,
    invoice_id TEXT,
    handled BOOLEAN NOT NULL DEFAULT FALSE,
    error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    CONSTRAINT uq_billing_events_provider_delivery UNIQUE (provider, delivery_id)
);

CREATE INDEX IF NOT EXISTS idx_billing_events_user_id ON billing_events(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_provider ON billing_events(provider);
CREATE INDEX IF NOT EXISTS idx_billing_events_event_type ON billing_events(event_type);
CREATE INDEX IF NOT EXISTS idx_billing_events_customer_id ON billing_events(customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_received_at ON billing_events(received_at);
