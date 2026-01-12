-- Migration: Fix thread_states foreign key constraints to allow message deletion
-- This fixes: sqlalchemy.exc.IntegrityError on delete when messages are referenced by thread_states

-- Drop existing constraints
ALTER TABLE thread_states 
DROP CONSTRAINT IF EXISTS thread_states_first_message_id_fkey;

ALTER TABLE thread_states 
DROP CONSTRAINT IF EXISTS thread_states_last_message_id_fkey;

-- Re-add with ON DELETE SET NULL
ALTER TABLE thread_states 
ADD CONSTRAINT thread_states_first_message_id_fkey 
FOREIGN KEY (first_message_id) REFERENCES messages(id) ON DELETE SET NULL;

ALTER TABLE thread_states 
ADD CONSTRAINT thread_states_last_message_id_fkey 
FOREIGN KEY (last_message_id) REFERENCES messages(id) ON DELETE SET NULL;
