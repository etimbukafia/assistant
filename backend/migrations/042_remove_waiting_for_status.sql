-- Migration 042: Remove waiting_for task status
-- All waiting_for tasks are re-classified as approved (active).
-- The status was used for email follow-up tracking but is no longer
-- exposed in the UI or available during task creation.

UPDATE tasks
SET status = 'approved'
WHERE status = 'waiting_for';
