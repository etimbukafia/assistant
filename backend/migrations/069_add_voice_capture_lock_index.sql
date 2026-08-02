DELETE FROM task_queue
WHERE task_type = 'voice_capture_transcription'
  AND status IN ('pending', 'in_progress')
  AND created_at < NOW() - INTERVAL '10 minutes';

CREATE UNIQUE INDEX IF NOT EXISTS uq_task_queue_voice_capture_lock
ON task_queue (user_id, task_type)
WHERE task_type = 'voice_capture_transcription'
  AND status IN ('pending', 'in_progress');
