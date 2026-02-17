ALTER TABLE user_settings
ADD COLUMN IF NOT EXISTS notification_email TEXT;

UPDATE user_settings
SET notification_email = user_email
WHERE notification_email IS NULL;
