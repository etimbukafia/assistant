-- Minimize stored PII in audit and metrics tables.
-- Assumes PostgreSQL.

-- Billing events should keep normalized replay data only.
UPDATE billing_events
SET customer_email = NULL,
    payload = CASE
        WHEN payload ? 'normalized' THEN jsonb_build_object('normalized', payload->'normalized')
        ELSE '{}'::jsonb
    END;

-- Telemetry session linkage is no longer retained.
UPDATE ui_telemetry_events
SET session_id = NULL
WHERE session_id IS NOT NULL;

-- Chat metrics keep a pseudonymous session key and no persisted prompt signatures.
UPDATE chat_model_call_metrics
SET session_id = md5(session_id),
    prompt_prefix_signature = '{}'::jsonb
WHERE session_id IS NOT NULL;
