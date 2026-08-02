-- 058_add_contact_links_to_messages_and_threads.sql
-- Deterministic contact linking for ingested messages and thread state.

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS contact_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_messages_contact_id'
    ) THEN
        ALTER TABLE messages
            ADD CONSTRAINT fk_messages_contact_id
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_messages_contact_id ON messages(contact_id);
CREATE INDEX IF NOT EXISTS ix_messages_user_contact_id ON messages(user_id, contact_id);

ALTER TABLE thread_states
    ADD COLUMN IF NOT EXISTS contact_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_thread_states_contact_id'
    ) THEN
        ALTER TABLE thread_states
            ADD CONSTRAINT fk_thread_states_contact_id
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_thread_states_contact_id ON thread_states(contact_id);
CREATE INDEX IF NOT EXISTS ix_thread_states_user_contact_id ON thread_states(user_id, contact_id);

-- Best-effort backfill for existing rows where sender can be matched to contact email.
UPDATE messages AS m
SET contact_id = c.id
FROM contacts AS c
WHERE m.contact_id IS NULL
  AND c.email IS NOT NULL
  AND m.user_id = c.user_id
  AND lower(trim(regexp_replace(m.sender, '.*<([^>]+)>.*', '\1'))) = lower(trim(c.email));

-- Backfill thread contact from earliest linked message in each thread.
UPDATE thread_states AS ts
SET contact_id = src.contact_id
FROM (
    SELECT DISTINCT ON (m.thread_id)
        m.thread_id,
        m.contact_id
    FROM messages AS m
    WHERE m.contact_id IS NOT NULL
    ORDER BY m.thread_id, m.received_at ASC, m.id ASC
) AS src
WHERE ts.contact_id IS NULL
  AND ts.thread_id = src.thread_id;

