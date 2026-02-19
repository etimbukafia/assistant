-- Split task_type (work category) from task_signal (detection provenance)
-- Normalize existing task_type values to categories

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS task_signal VARCHAR;

UPDATE tasks
SET task_signal = 'explicit'
WHERE task_signal IS NULL;

ALTER TABLE tasks
    ALTER COLUMN task_type SET DEFAULT 'other';

-- Map legacy values
UPDATE tasks
SET task_signal = 'explicit',
    task_type = 'other'
WHERE task_type = 'explicit';

UPDATE tasks
SET task_signal = 'implied',
    task_type = 'follow_up'
WHERE task_type = 'implied_followup';

UPDATE tasks
SET task_signal = 'explicit',
    task_type = 'prep'
WHERE task_type = 'meeting_prep';

UPDATE tasks
SET task_signal = 'explicit',
    task_type = 'follow_up',
    status = 'waiting_for'
WHERE task_type = 'waiting_for';

UPDATE tasks
SET task_type = 'other'
WHERE task_type IS NULL;
