-- Add initial_sync_completed flag to gmail_accounts
ALTER TABLE gmail_accounts 
ADD COLUMN IF NOT EXISTS initial_sync_completed BOOLEAN DEFAULT FALSE;

-- Index for efficient filtering
CREATE INDEX IF NOT EXISTS idx_gmail_accounts_initial_sync 
ON gmail_accounts(initial_sync_completed);
