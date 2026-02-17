"""
SQLAlchemy models for the assistant application

These models match the database migrations in backend/migrations/.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, ForeignKey, Date
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import relationship


from app.infra.database import Base
from app.infra.config import get_settings
from core.queue.models import create_task_queue_model

# Clock skew tolerance for time comparisons (handles drift between app server and DB)
# Supabase/AWS has sub-second drift with NTP; 30s is conservative buffer
CLOCK_SKEW_TOLERANCE = timedelta(seconds=30)

TaskQueue = create_task_queue_model(Base)


class Message(Base):
    """Email messages synced from Gmail"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    thread_id = Column(String, index=True)
    user_id = Column(String, index=True)
    subject = Column(String)
    sender = Column(String)
    recipient = Column(String)
    body = Column(Text)
    received_at = Column(DateTime)

    # AI-generated fields
    summary = Column(Text, nullable=True)
    needs_reply = Column(Boolean, nullable=True, index=True)
    extracted_tasks = Column(JSON, nullable=True)
    extracted_dates = Column(JSON, nullable=True)
    extracted_people = Column(JSON, nullable=True)
    extracted_decisions = Column(JSON, nullable=True)
    draft_reply = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    processed = Column(Boolean, default=False)
    ai_fallback = Column(Boolean, default=False)  # True if AI processing failed and used fallback
    status = Column(String, default="inbox", index=True)  # inbox | done | archived

    # Data Lifecycle fields
    content_expired = Column(Boolean, default=False, index=True)  # True when body deleted after retention period
    source_deleted = Column(Boolean, default=False, index=True)   # True when Gmail reports message deleted
    body_encrypted = Column(Boolean, default=False)  # True when body is encrypted at rest

    # Attachment processing
    has_attachments = Column(Boolean, default=False)  # True if email has attachments
    attachments = Column(JSON, nullable=True)  # List of {name, mime_type, size, attachment_id}
    attachment_insights = Column(JSON, nullable=True)  # AI-extracted: {summary, tasks, key_points, deadlines}

    # Scheduling intent detection (metadata only, action requires manual trigger)
    scheduling_intent = Column(Boolean, default=False, index=True)  # True if scheduling intent detected
    scheduling_intent_confidence = Column(Float, nullable=True)  # 0.0-1.0 confidence score
    scheduling_intent_type = Column(String, nullable=True)  # availability_request | time_request | meeting_confirmation | reschedule_request

    # Relationships
    tasks = relationship("Task", back_populates="source_message")

    @property
    def decrypted_body(self) -> str:
        """Get decrypted body content, handling encryption and expiration"""
        if not self.body:
            return ""
        if self.content_expired:
            return "[Content expired]"
        if self.body_encrypted:
            from app.security.encryption import decrypt_body
            return decrypt_body(self.body)
        return self.body


class GmailAccount(Base):
    """Gmail account OAuth credentials"""
    __tablename__ = "gmail_accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    user_id = Column(String, index=True, nullable=True) # Nullable for migration, should be required later

    # OAuth tokens (encrypted)
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=True)  # Encrypted (nullable in case not provided)
    token_expiry = Column(DateTime, nullable=True)

    # Metadata
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Gmail History API tracking for deletion sync
    last_history_id = Column(String, nullable=True)

    # Initial sync tracking
    initial_sync_completed = Column(Boolean, default=False, index=True)


class UserSettings(Base):
    """User preferences for task management, reminders, calendar, and billing"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    user_email = Column(String, unique=True, index=True)
    notification_email = Column(String, nullable=True, index=True)

    # Task Detection
    auto_approve_tasks = Column(Boolean, default=False)
    task_detection_instructions = Column(Text, nullable=True)

    # Reminder Preferences (JSON)
    reminder_preferences = Column(JSON, default=lambda: {
        "max_reminders_per_day": 10,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "default_reminder_offset_hours": 1
    })

    # Notification Preferences (JSON)
    notification_preferences = Column(JSON, default=lambda: {
        "push_enabled": True,
        "push_urgent_tasks": True,
        "push_deadlines": True,
        "push_digests": True,
        "push_briefings": True,
    })

    # Quick Reply Feature
    enable_quick_reply_from_task = Column(Boolean, default=False)

    # Calendar Preferences
    default_meeting_duration = Column(Integer, default=30)  # Minutes
    preferred_meeting_times = Column(String, default="any")  # morning | afternoon | any
    buffer_minutes = Column(Integer, default=15)  # Minutes between meetings
    working_hours_start = Column(String, default="09:00")  # HH:MM format
    working_hours_end = Column(String, default="17:00")  # HH:MM format
    default_timezone = Column(String, default="UTC")  # IANA format, e.g., "Africa/Johannesburg"
    calendar_ids = Column(JSON, default=list)  # Google Calendar IDs to check for availability
    default_calendar_id = Column(String, default="primary")
    auto_briefing_enabled = Column(Boolean, default=True)
    briefing_hours_before = Column(Integer, default=1)

    # Digest Preferences (JSON)
    digest_preferences = Column(JSON, default=lambda: {
        "enabled": False,
        "morning_briefing": {
            "enabled": True,
            "time": "08:00",
            "include": ["tasks", "threads", "calendar"]
        },
        "end_of_day": {
            "enabled": True,
            "time": "18:00",
            "include": ["completed", "pending", "tomorrow"]
        },
        "weekly_review": {
            "enabled": True,
            "day": "monday",
            "time": "09:00",
            "include": ["waiting_for", "overdue", "stats"]
        },
        "delivery_channel": "email"
    })

    # Subscription fields (from migration 015)
    subscription_tier = Column(String, default="trial")  # trial | pro
    subscription_status = Column(String, default="trialing")  # trialing | active | canceled | past_due | expired
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    polar_customer_id = Column(String, index=True, nullable=True)
    polar_subscription_id = Column(String, index=True, nullable=True)

    # Trial warning tracking (from migration 022)
    last_trial_warning_sent = Column(DateTime, nullable=True)  # When last warning was sent
    last_trial_warning_milestone = Column(String, nullable=True)  # 3_days | 1_day | expired | grace_ending

    # Personalization & Onboarding (from migration 023)
    assistant_name = Column(String, default="Teeks")  # User's chosen name for AI assistant
    onboarding_completed = Column(Boolean, default=False)  # True after first-time setup

    # Credit system (from migration 027)
    credits_used = Column(Float, default=0.0)  # USD spent on Gemini models this period
    credits_limit = Column(Float, default=1.0)  # USD limit (1.0 trial, 5.0 pro)
    credits_period_start = Column(DateTime, nullable=True)  # When current billing period started

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Trial is NOT auto-started — user must explicitly activate
        # self.trial_ends_at is set by the /subscription/activate-trial endpoint
        
        # Ensure defaults are set for new instances
        if self.assistant_name is None:
            self.assistant_name = "Teeks"
        if self.onboarding_completed is None:
            self.onboarding_completed = False

    @property
    def is_active(self) -> bool:
        """Check if user has active subscription or valid trial"""
        now = datetime.now(timezone.utc)

        if self.subscription_tier == "pro":
            if self.subscription_status not in ["active", "trialing"]:
                return False
            # Also verify subscription hasn't expired (handles webhook delays)
            if self.subscription_expires_at:
                return self.subscription_expires_at > (now - CLOCK_SKEW_TOLERANCE)
            # No expiry date set - trust status (edge case during initial setup)
            return True

        # Trial user - add clock skew tolerance to prevent edge cases
        if self.trial_ends_at and self.trial_ends_at > (now - CLOCK_SKEW_TOLERANCE):
            return True

        return False

    @property
    def days_remaining(self) -> int:
        """Days remaining in trial or subscription"""
        now = datetime.now(timezone.utc)

        if self.subscription_tier == "pro" and self.subscription_expires_at:
            delta = self.subscription_expires_at - now
            return max(0, delta.days)

        if self.trial_ends_at:
            delta = self.trial_ends_at - now
            return max(0, delta.days)

        return 0

    @property
    def credits_remaining(self) -> float:
        """Remaining credits in USD for this billing period"""
        limit = self.credits_limit if self.credits_limit is not None else 1.0
        used = self.credits_used if self.credits_used is not None else 0.0
        return max(0.0, limit - used)

    @property
    def credits_exhausted(self) -> bool:
        """Check if user has exhausted their AI credits"""
        return self.credits_remaining <= 0


class Task(Base):
    """Structured tasks extracted from messages with smart reminders"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    # Link to thread (PRIMARY relationship - tasks belong to threads)
    thread_id = Column(String, nullable=True, index=True)

    # Link to source message (for context/audit trail)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, index=True)

    # Task Details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source_snippet = Column(Text, nullable=True)  # Context snippet from email explaining why this task exists

    # Task Type/Category
    task_type = Column(String, index=True)  # explicit, implied_followup, waiting_for, meeting_prep
    priority = Column(String, default="normal")  # low, normal, high, urgent

    # Approval Workflow
    status = Column(String, default="pending_approval", index=True)
    # Status options: pending_approval, approved, dismissed, completed, snoozed, superseded
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    dismissed_at = Column(DateTime, nullable=True)

    # Reminder Logic
    reminder_context = Column(JSON, nullable=True)  # AI-extracted context
    scheduled_reminder_at = Column(DateTime, nullable=True, index=True)
    last_reminded_at = Column(DateTime, nullable=True)
    reminder_count = Column(Integer, default=0)
    snoozed_until = Column(DateTime, nullable=True)

    # Extracted Entities
    related_people = Column(JSON, default=list)
    related_dates = Column(JSON, default=list)

    # Deadline fields (Smart Todo List)
    deadline = Column(DateTime, nullable=True, index=True)
    deadline_source = Column(String, default="explicit")  # explicit | inferred
    deadline_confidence = Column(Float, nullable=True)  # 0.0-1.0 for inferred deadlines
    deadline_user_confirmed = Column(Boolean, default=False)
    urgency_suggested_by_ai = Column(Boolean, default=False)  # True when AI sets priority=urgent

    # Metadata
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    source_message = relationship("Message", back_populates="tasks")


class TaskReminder(Base):
    """History of reminders sent for tasks"""
    __tablename__ = "task_reminders"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    reminded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reminder_type = Column(String)  # scheduled, urgent_nudge, digest
    delivered = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DailyFocus(Base):
    """Daily focus goals and weekly target for the Focus tab"""
    __tablename__ = "daily_focus"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    focus_date = Column(Date, nullable=False, index=True)

    # Up to 3 daily goals: [{text: str, completed: bool}]
    goals = Column(JSON, default=list)

    # "Eat the frog" task
    frog_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    frog_task = relationship("Task", foreign_keys=[frog_task_id])

    # Weekly target text
    weekly_target = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AgentActivityLog(Base):
    """Track all autonomous agent actions for transparency"""
    __tablename__ = "agent_activity_log"

    id = Column(Integer, primary_key=True, index=True)

    # Agent identification
    orchestrator_id = Column(String, nullable=True)  # For tracking orchestrator instances
    module_name = Column(String, nullable=True)  # Which module performed the action

    # Action details
    action_type = Column(String, index=True)  # auto_reply, follow_up, task_approval, etc.
    action_description = Column(Text)  # Human-readable description
    confidence = Column(Float, nullable=True)  # Confidence score for the action

    # User-facing information
    user_visible_message = Column(Text, nullable=True)  # Message shown to user

    # Relations
    related_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)

    # Decision context (JSON)
    decision_context = Column(JSON, nullable=True)  # Context used for decision
    action_result = Column(JSON, nullable=True)  # Result of the action

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class SchedulingSuggestion(Base):
    """
    AI-generated scheduling suggestions for messages with scheduling intent.

    TimeSlot structure (stored in suggested_slots JSON):
    {
        "start_time": "2024-01-15T11:00:00Z",
        "end_time": "2024-01-15T11:30:00Z",
        "has_conflict": false,
        "conflict_details": null
    }
    """
    __tablename__ = "scheduling_suggestions"

    id = Column(Integer, primary_key=True, index=True)

    # Thread-level tracking for multi-message scheduling conversations
    thread_id = Column(String, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, index=True)

    # Extracted scheduling details
    participants = Column(JSON, default=list)  # List of email addresses or names
    suggested_slots = Column(JSON, default=list)  # List of TimeSlot objects
    time_window_start = Column(DateTime, nullable=True)  # Optional: earliest acceptable time
    time_window_end = Column(DateTime, nullable=True)  # Optional: latest acceptable time
    timezone = Column(String, default="UTC")  # IANA format (e.g., "Africa/Johannesburg")
    meeting_type = Column(String, default="other")  # call | review | demo | coffee | interview | other
    duration_minutes = Column(Integer, default=30)
    intent_type = Column(String, default="availability_request")  # availability_request | time_request | meeting_confirmation | meeting_reminder | reschedule_request

    # Source context
    source_text_snippet = Column(Text, nullable=True)  # The text that triggered scheduling detection

    # AI-generated drafts
    draft_reply = Column(Text, nullable=True)  # Availability reply text
    draft_event_description = Column(Text, nullable=True)  # Calendar event description

    # Status workflow: pending | sent | accepted | dismissed | expired
    status = Column(String, default="pending", index=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CalendarEvent(Base):
    """
    Calendar events - both created by us and synced from Google Calendar.
    Used for scheduling and meeting briefings.
    """
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)

    # Event details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)  # User-authored meeting/event notes
    all_day = Column(Boolean, default=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    participants = Column(JSON, default=list)  # [{email, name, response_status}]
    organizer = Column(String, nullable=True)  # Email of organizer
    timezone = Column(String, default="UTC")  # IANA format
    location = Column(String, nullable=True)  # Meeting link or physical location

    # Source: created (by us) | synced (from calendar)
    source = Column(String, default="created", index=True)

    # Relations (for created events)
    source_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    source_suggestion_id = Column(Integer, ForeignKey("scheduling_suggestions.id", ondelete="SET NULL"), nullable=True, index=True)

    # External calendar integration
    provider = Column(String, default="google")  # google (MVP only)
    external_event_id = Column(String, nullable=True, unique=True, index=True)  # Google Calendar event ID
    calendar_id = Column(String, default="primary")  # Which calendar this event is on
    last_synced_at = Column(DateTime, nullable=True)

    # Meeting briefing
    briefing = Column(JSON, nullable=True)  # Generated briefing data
    briefing_generated_at = Column(DateTime, nullable=True)
    briefing_scheduled_for = Column(DateTime, nullable=True)
    related_message_ids = Column(JSON, default=list)  # Messages involving attendees
    related_task_ids = Column(JSON, default=list)  # Tasks involving attendees

    # Status: upcoming | completed | cancelled | pending | created | failed
    status = Column(String, default="upcoming", index=True)
    error_message = Column(Text, nullable=True)  # Error details if creation failed

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# =============================================================================
# Principal Memory (Executive Context Engine) - Phase 1
# =============================================================================

class PrincipalMemory(Base):
    """
    Explicit, user-owned preferences.
    Never inferred, always editable, always explainable.

    Examples: preferred tone, reply length, default sign-off, VIP contacts
    """
    __tablename__ = "principal_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Preference key-value
    key = Column(String, nullable=False, index=True)  # e.g., "tone", "sign_off", "reply_length"
    value = Column(Text, nullable=False)  # e.g., "formal", "Best regards,", "concise"

    # Context type for relevance filtering
    context_type = Column(String, nullable=False, index=True)  # drafting | scheduling | task_review

    # Source tracking
    source = Column(String, default="manual")  # manual | approved_suggestion

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DecisionPattern(Base):
    """
    Observed, read-only behavioral patterns.
    Tracked repetitions surfaced as suggestions only.

    Phase 1: Count occurrences, track confidence, surface as suggestions.
    Confidence formula: occurrences / (occurrences + 2)
    """
    __tablename__ = "decision_patterns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Pattern identification
    pattern_key = Column(String, nullable=False, index=True)  # Unique identifier for this pattern type
    pattern_type = Column(String, nullable=False, index=True)  # dismiss_email, prefer_morning, shorten_draft

    # Context type for relevance filtering
    context_type = Column(String, nullable=False, index=True)  # drafting | scheduling | task_review

    # Pattern details
    conditions = Column(JSON, nullable=True)  # e.g., {"sender_domain": "newsletter.com"}
    action = Column(String, nullable=False)  # e.g., "dismiss", "prefer_time:morning"

    # Tracking
    occurrences = Column(Integer, default=1)
    confidence = Column(Float, default=0.33)  # Calculated: occurrences / (occurrences + 2)
    last_occurrence_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Status workflow
    status = Column(String, default="observed", index=True)  # observed | suggested | rejected | approved

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# =============================================================================
# Thread State Machine - State-Based Thread Processing
# =============================================================================

class ThreadState(Base):
    """
    Single source of truth for a conversation thread.

    Threads are state machines. Messages are state updates.
    Raw history is not the authority - this state is.

    Each new message incrementally updates this state rather than
    re-analyzing the full thread transcript.
    """
    __tablename__ = "thread_states"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, index=True)

    # Thread summary - what the conversation is about
    summary = Column(Text, nullable=True)

    # Open tasks/loops at thread level (deduplicated)
    # Structure: [{"id": str, "title": str, "status": "open|completed|superseded", "created_at": str, "source_message_id": int}]
    open_tasks = Column(JSON, default=list)

    # Decisions made in this thread
    # Structure: [{"decision": str, "made_at": str, "source_message_id": int}]
    decisions = Column(JSON, default=list)

    # Participants in the thread
    # Structure: [{"email": str, "name": str, "role": "sender|recipient|cc"}]
    participants = Column(JSON, default=list)

    # Last meaningful action in the thread
    last_action = Column(String, nullable=True)  # e.g., "User requested update", "Bob confirmed meeting"
    last_action_by = Column(String, nullable=True)  # Email of who took the action
    last_action_at = Column(DateTime, nullable=True)

    # Thread-level reply status
    needs_reply = Column(Boolean, default=False)
    last_outbound_at = Column(DateTime, nullable=True)  # When user last replied

    # Action points — concise imperative "what do I need to do" list
    action_points = Column(JSON, default=list)  # ["Send Q3 report by Friday", "Confirm with Mike"]

    # Message count for quick reference
    message_count = Column(Integer, default=0)

    # First and last message tracking
    first_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    last_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)

    # Subject (from first message, for display)
    subject = Column(String, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ContactContext(Base):
    """
    Lightweight per-contact metadata.

    Auto-stored: interaction frequency, last interaction, channel
    Manual-only: relationship notes, contact category

    Rules:
    - No emotional inference
    - No auto-written notes
    - If it contains an adjective about personality or intent, it's forbidden unless manually entered
    """
    __tablename__ = "contact_contexts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Contact identification
    contact_email = Column(String, nullable=False, index=True)
    contact_name = Column(String, nullable=True)

    # Auto-tracked data (factual, observable)
    contact_metadata = Column(JSON, default=lambda: {
        "message_count": 0,
        "last_interaction_at": None,
        "avg_response_latency_hours": None,
        "primary_channel": "email",
        "typical_time_of_day": None,  # morning | afternoon | evening
        "urgency_frequency": 0  # Count of messages with urgency markers
    })

    # Manual-only fields
    notes = Column(Text, nullable=True)  # User-written notes only
    category = Column(String, nullable=True)  # vip | colleague | external | vendor
    preferred_tone = Column(String, nullable=True)  # formal | neutral | casual (overrides default)
    promoted = Column(Boolean, default=False, index=True)  # User-promoted contact for vault/mentions
    vault_note_id = Column(Integer, ForeignKey("vault_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    aliases = Column(JSON, default=list)  # Additional names/emails used for resolution

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class VaultNote(Base):
    """Knowledge vault note (Markdown + frontmatter)."""
    __tablename__ = "vault_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    slug = Column(String, nullable=False, index=True)
    note_type = Column(String, nullable=False, index=True)  # person|project|meeting|decision|commitment
    title = Column(String, nullable=False)
    frontmatter = Column(JSON, default=dict)
    body = Column(Text, default="")
    canonical_email = Column(String, nullable=True, index=True)
    aliases = Column(JSON, default=list)
    source = Column(String, default="manual", index=True)
    confidence = Column(Float, default=1.0)
    status = Column(String, default="active", index=True)  # active|archived|draft
    pinned = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_referenced_at = Column(DateTime, nullable=True, index=True)


class VaultLink(Base):
    """Graph edge between two vault notes."""
    __tablename__ = "vault_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    source_note_id = Column(Integer, ForeignKey("vault_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_note_id = Column(Integer, ForeignKey("vault_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type = Column(String, default="reference", index=True)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class VaultProposal(Base):
    """Human-in-the-loop vault proposal queue."""
    __tablename__ = "vault_proposals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    target_note_id = Column(Integer, ForeignKey("vault_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    proposal_type = Column(String, nullable=False, index=True)  # create_note|update_note|add_link|update_frontmatter
    proposed_data = Column(JSON, nullable=False)
    diff_summary = Column(Text, nullable=True)
    source_type = Column(String, nullable=True, index=True)
    source_id = Column(String, nullable=True, index=True)
    dedupe_key = Column(String, nullable=True, index=True)
    confidence = Column(Float, default=0.5)
    priority = Column(String, default="normal", index=True)
    status = Column(String, default="pending", index=True)  # auto_approved reserved for post-MVP
    rejection_reason = Column(Text, nullable=True)
    rejection_category = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at = Column(DateTime, nullable=True, index=True)


class VaultMetricsDaily(Base):
    """Daily aggregates for vault observability."""
    __tablename__ = "vault_metrics_daily"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    context_attempt_count = Column(Integer, default=0)
    context_injected_count = Column(Integer, default=0)
    notes_referenced_count = Column(Integer, default=0)
    proposals_created_count = Column(Integer, default=0)


# =============================================================================
# Scheduled Digests
# =============================================================================

class Digest(Base):
    """
    Generated digests (morning briefing, end-of-day, weekly review).

    Digests aggregate state from ThreadState and Task tables.
    No AI processing - just database queries.
    """
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    user_email = Column(String, index=True)

    # Digest info
    digest_type = Column(String, index=True)  # morning_briefing | end_of_day | weekly_review
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)

    # Content
    content = Column(JSON, nullable=False)  # Structured digest content
    html_content = Column(Text, nullable=True)  # Rendered HTML
    text_content = Column(Text, nullable=True)  # Plain text version

    # Delivery
    delivery_channel = Column(String)  # email | telegram | push
    delivery_status = Column(String, default="pending")  # pending | sent | failed
    delivered_at = Column(DateTime, nullable=True)
    delivery_error = Column(Text, nullable=True)

    # Stats
    task_count = Column(Integer, default=0)
    thread_count = Column(Integer, default=0)
    event_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# =============================================================================
# AI Chat 
# =============================================================================

class ChatSession(Base):
    """
    Chat sessions for AI assistant conversations.
    
    Session types:
    - 'command': Work-related queries (30 days retention)
    - 'reflection': Supportive/emotional conversations (24 hours retention)
    """
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, nullable=False, index=True)
    session_type = Column(String, nullable=False, default="command")  # 'command' or 'reflection'
    title = Column(String, nullable=True)  # Optional display title
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    state = Column(JSON, nullable=False, default=dict)  # ConversationState

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    pending_actions = relationship("ChatPendingAction", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """
    Individual messages within a chat session.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    message_metadata = Column(JSON, default=dict)  # tool calls, etc.

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    pending_actions = relationship("ChatPendingAction", back_populates="message")


class ChatPendingAction(Base):
    """
    Actions proposed by AI that await user approval.
    
    Status:
    - 'pending': Awaiting user decision
    - 'approved': User approved, action executed
    - 'rejected': User rejected
    - 'expired': Session ended without decision
    """
    __tablename__ = "chat_pending_actions"

    id = Column(String, primary_key=True)  # UUID
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    action_type = Column(String, nullable=False)  # 'draft_reply', 'create_task', etc.
    action_data = Column(JSON, nullable=False)  # Action-specific data
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("ChatSession", back_populates="pending_actions")
    message = relationship("ChatMessage", back_populates="pending_actions")


class DeviceToken(Base):
    """Expo push notification device tokens"""
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    expo_push_token = Column(String, nullable=False, unique=True)
    device_name = Column(String, nullable=True)
    platform = Column(String, nullable=True)  # "ios" | "android"
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Notification(Base):
    """In-app notification feed entries with push delivery tracking"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Content
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    category = Column(String, nullable=False, index=True)
    # Categories: task_urgent | task_deadline | digest_ready | briefing_ready | reminder_due | system
    priority = Column(String, default="normal")  # low | normal | high

    # Deep link target
    target_type = Column(String, nullable=True)  # task | message | digest | briefing | settings
    target_id = Column(String, nullable=True)

    # Read state
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)

    # Push delivery tracking
    push_sent = Column(Boolean, default=False)
    push_sent_at = Column(DateTime, nullable=True)
    push_ticket_id = Column(String, nullable=True)
    push_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class WebhookLog(Base):
    """Append-only log of incoming webhooks for health monitoring and audit."""
    __tablename__ = "webhook_logs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)        # "polar" | "gmail"
    event_type = Column(String, nullable=False, index=True)    # e.g. "subscription.created", "gmail_push"
    processed = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    customer_id = Column(String, nullable=True)                # Polar customer_id or email address
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class UITelemetryEvent(Base):
    """Product telemetry events emitted from frontend interactions."""
    __tablename__ = "ui_telemetry_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    event_id = Column(String, nullable=True, index=True)
    event_name = Column(String, nullable=False, index=True)
    event_payload = Column(JSON, default=dict)
    page_path = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    client_ts = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class TokenUsage(Base):
    """Track LLM token usage per user for cost monitoring."""
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    operation = Column(String, nullable=False, index=True)  # email_processing | chat | scheduling | etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
