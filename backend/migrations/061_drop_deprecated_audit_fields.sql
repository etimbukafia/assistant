-- Drop deprecated audit/telemetry fields after backfill/minimization.
-- Apply after 060_minimize_audit_pii.sql.

ALTER TABLE billing_events
    DROP COLUMN IF EXISTS customer_email;

ALTER TABLE ui_telemetry_events
    DROP COLUMN IF EXISTS session_id;

ALTER TABLE chat_model_call_metrics
    DROP COLUMN IF EXISTS prompt_prefix_signature;
