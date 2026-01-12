-- Add user_id column to gmail_accounts table
ALTER TABLE gmail_accounts ADD COLUMN IF NOT EXISTS user_id TEXT;
CREATE INDEX IF NOT EXISTS ix_gmail_accounts_user_id ON gmail_accounts (user_id);

-- Enable Row Level Security
ALTER TABLE gmail_accounts ENABLE ROW LEVEL SECURITY;

-- Create RLS Policy regarding Gmail Accounts
-- Users can only see their own gmail accounts
CREATE POLICY "Users can only see their own gmail accounts" ON gmail_accounts
    FOR ALL
    USING (user_id = current_setting('app.user_id', true));
