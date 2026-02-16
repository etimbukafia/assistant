-- ============================================================================
-- Teeks Database Schema for Supabase
-- Generated from SQLAlchemy models
-- Run this in your new Zurich Supabase project's SQL Editor
-- ============================================================================

-- ============================================================================
-- 1. Messages Table (Email messages synced from Gmail)
-- ============================================================================
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR UNIQUE NOT NULL,
    thread_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    subject VARCHAR,
    sender VARCHAR,
    recipient VARCHAR,
    body TEXT,
    received_at TIMESTAMPTZ,
    
    -- AI-generated fields
    summary TEXT,
    needs_reply BOOLEAN,
    extracted_tasks JSONB,
    extracted_dates JSONB,
    extracted_people JSONB,
    extracted_decisions JSONB,
    draft_reply TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    ai_fallback BOOLEAN DEFAULT FALSE,
    status VARCHAR DEFAULT 'inbox',
    
    -- Data Lifecycle fields
    content_expired BOOLEAN DEFAULT FALSE,
    source_deleted BOOLEAN DEFAULT FALSE,
    body_encrypted BOOLEAN DEFAULT FALSE,
    
    -- Attachment processing
    has_attachments BOOLEAN DEFAULT FALSE,
    attachments JSONB,
    attachment_insights JSONB,
    
    -- Scheduling intent detection
    scheduling_intent BOOLEAN DEFAULT FALSE,
    scheduling_intent_confidence FLOAT,
    scheduling_intent_type VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_messages_message_id ON messages(message_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_needs_reply ON messages(needs_reply);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_content_expired ON messages(content_expired);
CREATE INDEX IF NOT EXISTS idx_messages_source_deleted ON messages(source_deleted);
CREATE INDEX IF NOT EXISTS idx_messages_scheduling_intent ON messages(scheduling_intent);

-- ============================================================================
-- 2. Gmail Accounts Table (OAuth credentials)
-- ============================================================================
CREATE TABLE IF NOT EXISTS gmail_accounts (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    user_id VARCHAR,
    
    -- OAuth tokens (encrypted)
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expiry TIMESTAMPTZ,
    
    -- Metadata
    last_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Gmail History API tracking
    last_history_id VARCHAR,
    
    -- Initial sync tracking
    initial_sync_completed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_gmail_accounts_email ON gmail_accounts(email);
CREATE INDEX IF NOT EXISTS idx_gmail_accounts_user_id ON gmail_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_gmail_accounts_initial_sync ON gmail_accounts(initial_sync_completed);

-- ============================================================================
-- 3. User Settings Table (Preferences, subscription, calendar settings)
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR UNIQUE NOT NULL,
    user_email VARCHAR UNIQUE NOT NULL,
    
    -- Task Detection
    auto_approve_tasks BOOLEAN DEFAULT FALSE,
    task_detection_instructions TEXT,
    
    -- Reminder Preferences (JSON)
    reminder_preferences JSONB DEFAULT '{"max_reminders_per_day": 10, "quiet_hours_start": "22:00", "quiet_hours_end": "08:00", "default_reminder_offset_hours": 24}',
    
    -- Notification Preferences (JSON)
    notification_preferences JSONB DEFAULT '{"push_enabled": true, "push_urgent_tasks": true, "push_deadlines": true, "push_digests": true, "push_briefings": true}',
    
    -- Quick Reply Feature
    enable_quick_reply_from_task BOOLEAN DEFAULT FALSE,
    
    -- Calendar Preferences
    default_meeting_duration INTEGER DEFAULT 30,
    preferred_meeting_times VARCHAR DEFAULT 'any',
    buffer_minutes INTEGER DEFAULT 15,
    working_hours_start VARCHAR DEFAULT '09:00',
    working_hours_end VARCHAR DEFAULT '17:00',
    default_timezone VARCHAR DEFAULT 'UTC',
    calendar_ids JSONB DEFAULT '[]',
    
    -- Digest Preferences (JSON)
    digest_preferences JSONB DEFAULT '{"enabled": false, "morning_briefing": {"enabled": true, "time": "08:00", "include": ["tasks", "threads", "calendar"]}, "end_of_day": {"enabled": true, "time": "18:00", "include": ["completed", "pending", "tomorrow"]}, "weekly_review": {"enabled": true, "day": "monday", "time": "09:00", "include": ["waiting_for", "overdue", "stats"]}, "delivery_channel": "email"}',
    
    -- Subscription fields
    subscription_tier VARCHAR DEFAULT 'trial',
    subscription_status VARCHAR DEFAULT 'trialing',
    trial_ends_at TIMESTAMPTZ,
    subscription_expires_at TIMESTAMPTZ,
    polar_customer_id VARCHAR,
    polar_subscription_id VARCHAR,
    
    -- Trial warning tracking
    last_trial_warning_sent TIMESTAMPTZ,
    last_trial_warning_milestone VARCHAR,
    
    -- Personalization & Onboarding
    assistant_name VARCHAR DEFAULT 'Donna',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    
    -- Credit system
    credits_used FLOAT DEFAULT 0.0,
    credits_limit FLOAT DEFAULT 1.0,
    credits_period_start TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_user_email ON user_settings(user_email);
CREATE INDEX IF NOT EXISTS idx_user_settings_polar_customer ON user_settings(polar_customer_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_polar_subscription ON user_settings(polar_subscription_id);

-- ============================================================================
-- 4. Tasks Table (Extracted tasks from messages)
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    
    -- Links
    thread_id VARCHAR,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id VARCHAR,
    
    -- Task Details
    title VARCHAR NOT NULL,
    description TEXT,
    source_snippet TEXT,
    
    -- Task Type/Category
    task_type VARCHAR,
    priority VARCHAR DEFAULT 'normal',
    
    -- Approval Workflow
    status VARCHAR DEFAULT 'pending_approval',
    approved_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    
    -- Reminder Logic
    reminder_context JSONB,
    scheduled_reminder_at TIMESTAMPTZ,
    last_reminded_at TIMESTAMPTZ,
    reminder_count INTEGER DEFAULT 0,
    snoozed_until TIMESTAMPTZ,
    
    -- Extracted Entities
    related_people JSONB DEFAULT '[]',
    related_dates JSONB DEFAULT '[]',
    
    -- Deadline fields
    deadline TIMESTAMPTZ,
    deadline_source VARCHAR DEFAULT 'explicit',
    deadline_confidence FLOAT,
    deadline_user_confirmed BOOLEAN DEFAULT FALSE,
    urgency_suggested_by_ai BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_thread_id ON tasks(thread_id);
CREATE INDEX IF NOT EXISTS idx_tasks_message_id ON tasks(message_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_completed_at ON tasks(completed_at);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_reminder_at ON tasks(scheduled_reminder_at);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

-- ============================================================================
-- 5. Task Reminders Table (History of reminders sent)
-- ============================================================================
CREATE TABLE IF NOT EXISTS task_reminders (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    reminded_at TIMESTAMPTZ DEFAULT NOW(),
    reminder_type VARCHAR,
    delivered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_reminders_task_id ON task_reminders(task_id);

-- ============================================================================
-- 6. Agent Activity Log Table (Autonomous agent actions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_activity_log (
    id SERIAL PRIMARY KEY,
    orchestrator_id VARCHAR,
    module_name VARCHAR,
    action_type VARCHAR,
    action_description TEXT,
    confidence FLOAT,
    user_visible_message TEXT,
    related_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    related_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    decision_context JSONB,
    action_result JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_activity_action_type ON agent_activity_log(action_type);
CREATE INDEX IF NOT EXISTS idx_agent_activity_related_message ON agent_activity_log(related_message_id);
CREATE INDEX IF NOT EXISTS idx_agent_activity_related_task ON agent_activity_log(related_task_id);
CREATE INDEX IF NOT EXISTS idx_agent_activity_created_at ON agent_activity_log(created_at);

-- ============================================================================
-- 7. Scheduling Suggestions Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS scheduling_suggestions (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id VARCHAR,
    participants JSONB DEFAULT '[]',
    suggested_slots JSONB DEFAULT '[]',
    time_window_start TIMESTAMPTZ,
    time_window_end TIMESTAMPTZ,
    timezone VARCHAR DEFAULT 'UTC',
    meeting_type VARCHAR DEFAULT 'other',
    duration_minutes INTEGER DEFAULT 30,
    intent_type VARCHAR DEFAULT 'availability_request',
    source_text_snippet TEXT,
    draft_reply TEXT,
    draft_event_description TEXT,
    status VARCHAR DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduling_suggestions_thread_id ON scheduling_suggestions(thread_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_suggestions_message_id ON scheduling_suggestions(message_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_suggestions_user_id ON scheduling_suggestions(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduling_suggestions_status ON scheduling_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_scheduling_suggestions_created_at ON scheduling_suggestions(created_at);

-- ============================================================================
-- 8. Calendar Events Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,
    title VARCHAR NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    participants JSONB DEFAULT '[]',
    organizer VARCHAR,
    timezone VARCHAR DEFAULT 'UTC',
    location VARCHAR,
    source VARCHAR DEFAULT 'created',
    source_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    source_suggestion_id INTEGER REFERENCES scheduling_suggestions(id) ON DELETE SET NULL,
    provider VARCHAR DEFAULT 'google',
    external_event_id VARCHAR UNIQUE,
    calendar_id VARCHAR DEFAULT 'primary',
    last_synced_at TIMESTAMPTZ,
    briefing JSONB,
    briefing_generated_at TIMESTAMPTZ,
    related_message_ids JSONB DEFAULT '[]',
    related_task_ids JSONB DEFAULT '[]',
    status VARCHAR DEFAULT 'upcoming',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_id ON calendar_events(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source ON calendar_events(source);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source_message ON calendar_events(source_message_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source_suggestion ON calendar_events(source_suggestion_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_external_event ON calendar_events(external_event_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);
CREATE INDEX IF NOT EXISTS idx_calendar_events_created_at ON calendar_events(created_at);

-- ============================================================================
-- 9. Principal Memory Table (Executive Context Engine)
-- ============================================================================
CREATE TABLE IF NOT EXISTS principal_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value TEXT NOT NULL,
    context_type VARCHAR NOT NULL,
    source VARCHAR DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_principal_memory_user_id ON principal_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_principal_memory_key ON principal_memory(key);
CREATE INDEX IF NOT EXISTS idx_principal_memory_context_type ON principal_memory(context_type);

-- ============================================================================
-- 10. Decision Patterns Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS decision_patterns (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    pattern_key VARCHAR NOT NULL,
    pattern_type VARCHAR NOT NULL,
    context_type VARCHAR NOT NULL,
    conditions JSONB,
    action VARCHAR NOT NULL,
    occurrences INTEGER DEFAULT 1,
    confidence FLOAT DEFAULT 0.33,
    last_occurrence_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR DEFAULT 'observed',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_patterns_user_id ON decision_patterns(user_id);
CREATE INDEX IF NOT EXISTS idx_decision_patterns_pattern_key ON decision_patterns(pattern_key);
CREATE INDEX IF NOT EXISTS idx_decision_patterns_pattern_type ON decision_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_decision_patterns_context_type ON decision_patterns(context_type);
CREATE INDEX IF NOT EXISTS idx_decision_patterns_status ON decision_patterns(status);

-- ============================================================================
-- 11. Thread States Table (State-Based Thread Processing)
-- ============================================================================
CREATE TABLE IF NOT EXISTS thread_states (
    id SERIAL PRIMARY KEY,
    thread_id VARCHAR UNIQUE NOT NULL,
    user_id VARCHAR,
    summary TEXT,
    open_tasks JSONB DEFAULT '[]',
    decisions JSONB DEFAULT '[]',
    participants JSONB DEFAULT '[]',
    last_action VARCHAR,
    last_action_by VARCHAR,
    last_action_at TIMESTAMPTZ,
    needs_reply BOOLEAN DEFAULT FALSE,
    last_outbound_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    first_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    last_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    subject VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thread_states_thread_id ON thread_states(thread_id);
CREATE INDEX IF NOT EXISTS idx_thread_states_user_id ON thread_states(user_id);
CREATE INDEX IF NOT EXISTS idx_thread_states_created_at ON thread_states(created_at);

-- ============================================================================
-- 12. Contact Contexts Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS contact_contexts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    contact_email VARCHAR NOT NULL,
    contact_name VARCHAR,
    contact_metadata JSONB DEFAULT '{"message_count": 0, "last_interaction_at": null, "avg_response_latency_hours": null, "primary_channel": "email", "typical_time_of_day": null, "urgency_frequency": 0}',
    notes TEXT,
    category VARCHAR,
    preferred_tone VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contact_contexts_user_id ON contact_contexts(user_id);
CREATE INDEX IF NOT EXISTS idx_contact_contexts_contact_email ON contact_contexts(contact_email);

-- ============================================================================
-- 13. Digests Table (Morning briefing, end-of-day, weekly review)
-- ============================================================================
CREATE TABLE IF NOT EXISTS digests (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,
    user_email VARCHAR,
    digest_type VARCHAR,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    content JSONB NOT NULL,
    html_content TEXT,
    text_content TEXT,
    delivery_channel VARCHAR,
    delivery_status VARCHAR DEFAULT 'pending',
    delivered_at TIMESTAMPTZ,
    delivery_error TEXT,
    task_count INTEGER DEFAULT 0,
    thread_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digests_user_id ON digests(user_id);
CREATE INDEX IF NOT EXISTS idx_digests_user_email ON digests(user_email);
CREATE INDEX IF NOT EXISTS idx_digests_digest_type ON digests(digest_type);
CREATE INDEX IF NOT EXISTS idx_digests_created_at ON digests(created_at);

-- ============================================================================
-- 14. Chat Sessions Table (AI assistant conversations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL DEFAULT 'command',
    title VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    state JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);

-- ============================================================================
-- 15. Chat Messages Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    message_metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);

-- ============================================================================
-- 16. Chat Pending Actions Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_pending_actions (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE CASCADE,
    action_type VARCHAR NOT NULL,
    action_data JSONB NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_pending_actions_session_id ON chat_pending_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_pending_actions_message_id ON chat_pending_actions(message_id);

-- ============================================================================
-- 17. Device Tokens Table (Expo push notifications)
-- ============================================================================
CREATE TABLE IF NOT EXISTS device_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    expo_push_token VARCHAR NOT NULL UNIQUE,
    device_name VARCHAR,
    platform VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_device_tokens_user_id ON device_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_device_tokens_is_active ON device_tokens(is_active);

-- ============================================================================
-- 18. Notifications Table (In-app notification feed)
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    body TEXT,
    category VARCHAR NOT NULL,
    priority VARCHAR DEFAULT 'normal',
    target_type VARCHAR,
    target_id VARCHAR,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    push_sent BOOLEAN DEFAULT FALSE,
    push_sent_at TIMESTAMPTZ,
    push_ticket_id VARCHAR,
    push_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_category ON notifications(category);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);

-- ============================================================================
-- 19. Webhook Logs Table (Health monitoring and audit)
-- ============================================================================
CREATE TABLE IF NOT EXISTS webhook_logs (
    id SERIAL PRIMARY KEY,
    source VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    error TEXT,
    customer_id VARCHAR,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_source ON webhook_logs(source);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_event_type ON webhook_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_received_at ON webhook_logs(received_at);

-- ============================================================================
-- 20. Token Usage Table (LLM cost monitoring)
-- ============================================================================
CREATE TABLE IF NOT EXISTS token_usage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd FLOAT NOT NULL DEFAULT 0.0,
    operation VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_user_id ON token_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_operation ON token_usage(operation);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at);

-- ============================================================================
-- 21. Task Queue Table (Background job queue)
-- ============================================================================
CREATE TABLE IF NOT EXISTS task_queue (
    id SERIAL PRIMARY KEY,
    
    -- Task identification
    task_type VARCHAR NOT NULL,
    correlation_id VARCHAR,
    user_id VARCHAR,
    
    -- Task data
    payload JSONB NOT NULL DEFAULT '{}',
    
    -- Execution tracking
    status VARCHAR NOT NULL DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_error TEXT,
    
    -- Scheduling
    scheduled_for TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_task_type ON task_queue(task_type);
CREATE INDEX IF NOT EXISTS idx_task_queue_correlation_id ON task_queue(correlation_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_user_id ON task_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_scheduled_for ON task_queue(scheduled_for);

-- ============================================================================
-- Done! All 21 tables created with TIMESTAMPTZ for timezone awareness.
-- ============================================================================
