-- ============================================================
-- FULL DATABASE WIPE SCRIPT
-- Deletes ALL data from ALL tables, preserves schema
-- ⚠️ ONLY USE ON DEV/STAGING - NEVER PRODUCTION!
-- ============================================================

-- Safety check - uncomment to require explicit confirmation
-- DO $$ BEGIN RAISE EXCEPTION 'SAFETY: Remove this line to run'; END $$;

BEGIN;

-- Disable foreign key checks
SET session_replication_role = 'replica';

-- ============================================
-- Public Schema Tables (order matters for FKs)
-- ============================================

-- Queue/Jobs
TRUNCATE TABLE public.task_queue CASCADE;

-- Chat
TRUNCATE TABLE public.chat_messages CASCADE;
TRUNCATE TABLE public.chat_sessions CASCADE;

-- Calendar
TRUNCATE TABLE public.calendar_events CASCADE;

-- Core data
TRUNCATE TABLE public.tasks CASCADE;
TRUNCATE TABLE public.messages CASCADE;

-- Accounts
TRUNCATE TABLE public.gmail_accounts CASCADE;

-- User settings (depends on auth.users)
TRUNCATE TABLE public.user_settings CASCADE;

-- Logs
TRUNCATE TABLE public.agent_activity_log CASCADE;

-- ============================================
-- Auth Schema (Supabase)
-- ============================================
TRUNCATE TABLE auth.users CASCADE;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

COMMIT;

-- Output confirmation
SELECT 'Database wiped successfully!' AS status;
