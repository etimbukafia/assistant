-- Update default reminder offset to 1 hour for existing users if still set to 24
UPDATE user_settings
SET reminder_preferences = jsonb_set(
    COALESCE(reminder_preferences::jsonb, '{}'::jsonb),
    '{default_reminder_offset_hours}',
    '1',
    true
)::json
WHERE (reminder_preferences->>'default_reminder_offset_hours' IS NULL
   OR reminder_preferences->>'default_reminder_offset_hours' = '24');
