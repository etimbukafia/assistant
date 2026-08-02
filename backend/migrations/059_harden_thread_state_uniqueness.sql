-- 059_harden_thread_state_uniqueness.sql
-- Scope thread state uniqueness to (user_id, thread_id) and backfill user ownership.

-- Backfill user_id for legacy rows where messages point to exactly one user.
UPDATE thread_states AS ts
SET user_id = src.user_id
FROM (
    SELECT
        m.thread_id,
        MIN(m.user_id) AS user_id
    FROM messages AS m
    WHERE m.thread_id IS NOT NULL
      AND m.user_id IS NOT NULL
    GROUP BY m.thread_id
    HAVING COUNT(DISTINCT m.user_id) = 1
) AS src
WHERE ts.user_id IS NULL
  AND ts.thread_id = src.thread_id;

-- Drop legacy global uniqueness on thread_id.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'thread_states_thread_id_key'
    ) THEN
        ALTER TABLE thread_states
            DROP CONSTRAINT thread_states_thread_id_key;
    END IF;
END $$;

DROP INDEX IF EXISTS thread_states_thread_id_key;

-- Recreate user-scoped uniqueness.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_thread_states_user_thread_id'
    ) THEN
        ALTER TABLE thread_states
            ADD CONSTRAINT uq_thread_states_user_thread_id
            UNIQUE (user_id, thread_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_thread_states_user_thread_id
    ON thread_states(user_id, thread_id);
