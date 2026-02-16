-- Add deterministic dedupe key for vault proposals
ALTER TABLE vault_proposals
ADD COLUMN IF NOT EXISTS dedupe_key TEXT;

CREATE INDEX IF NOT EXISTS idx_vault_proposals_user_dedupe
ON vault_proposals(user_id, dedupe_key);
