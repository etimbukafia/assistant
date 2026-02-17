-- Backfill missing task.user_id based on source message
UPDATE tasks
SET user_id = messages.user_id
FROM messages
WHERE tasks.user_id IS NULL
  AND tasks.message_id = messages.id;
