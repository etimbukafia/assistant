-- Replace mixed webhook audit identity fields with explicit columns.

ALTER TABLE webhook_logs
    ADD COLUMN IF NOT EXISTS user_id TEXT,
    ADD COLUMN IF NOT EXISTS provider_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS subject_ref TEXT;

ALTER TABLE webhook_deliveries
    ADD COLUMN IF NOT EXISTS user_id TEXT,
    ADD COLUMN IF NOT EXISTS provider_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS subject_ref TEXT;

-- Legacy Gmail/Outlook rows stored app user IDs in customer_id.
UPDATE webhook_logs
SET user_id = customer_id
WHERE user_id IS NULL
  AND customer_id IS NOT NULL
  AND source IN ('gmail', 'outlook', 'calendar')
  AND customer_id NOT LIKE 'email:%';

UPDATE webhook_deliveries
SET user_id = customer_id
WHERE user_id IS NULL
  AND customer_id IS NOT NULL
  AND source IN ('gmail', 'outlook', 'calendar')
  AND customer_id NOT LIKE 'email:%';

-- Legacy billing rows stored provider customer IDs in customer_id.
UPDATE webhook_logs
SET provider_customer_id = customer_id
WHERE provider_customer_id IS NULL
  AND customer_id IS NOT NULL
  AND source IN ('dodo', 'polar', 'billing')
  AND customer_id NOT LIKE 'email:%';

UPDATE webhook_deliveries
SET provider_customer_id = customer_id
WHERE provider_customer_id IS NULL
  AND customer_id IS NOT NULL
  AND source IN ('dodo', 'polar', 'billing')
  AND customer_id NOT LIKE 'email:%';

-- Legacy billing rows with hashed email fallback become subject references.
UPDATE webhook_logs
SET subject_ref = customer_id
WHERE subject_ref IS NULL
  AND customer_id LIKE 'email:%';

UPDATE webhook_deliveries
SET subject_ref = customer_id
WHERE subject_ref IS NULL
  AND customer_id LIKE 'email:%';

-- Best-effort backfill of billing webhook rows to app user IDs via stored provider customer IDs.
UPDATE webhook_logs wl
SET user_id = us.user_id
FROM user_settings us
WHERE wl.user_id IS NULL
  AND wl.source = 'dodo'
  AND wl.provider_customer_id IS NOT NULL
  AND wl.provider_customer_id = us.dodo_customer_id;

UPDATE webhook_logs wl
SET user_id = us.user_id
FROM user_settings us
WHERE wl.user_id IS NULL
  AND wl.source = 'polar'
  AND wl.provider_customer_id IS NOT NULL
  AND wl.provider_customer_id = us.polar_customer_id;

UPDATE webhook_deliveries wd
SET user_id = us.user_id
FROM user_settings us
WHERE wd.user_id IS NULL
  AND wd.source = 'dodo'
  AND wd.provider_customer_id IS NOT NULL
  AND wd.provider_customer_id = us.dodo_customer_id;

UPDATE webhook_deliveries wd
SET user_id = us.user_id
FROM user_settings us
WHERE wd.user_id IS NULL
  AND wd.source = 'polar'
  AND wd.provider_customer_id IS NOT NULL
  AND wd.provider_customer_id = us.polar_customer_id;

CREATE INDEX IF NOT EXISTS ix_webhook_logs_user_id ON webhook_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_webhook_logs_provider_customer_id ON webhook_logs(provider_customer_id);
CREATE INDEX IF NOT EXISTS ix_webhook_logs_subject_ref ON webhook_logs(subject_ref);

CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_user_id ON webhook_deliveries(user_id);
CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_provider_customer_id ON webhook_deliveries(provider_customer_id);
CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_subject_ref ON webhook_deliveries(subject_ref);

ALTER TABLE webhook_logs
    DROP COLUMN IF EXISTS customer_id;

ALTER TABLE webhook_deliveries
    DROP COLUMN IF EXISTS customer_id;
