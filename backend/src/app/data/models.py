"""
SQLAlchemy models for the assistant application

These models match the database migrations in backend/migrations/.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    JSON,
    Float,
    ForeignKey,
    Date,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
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
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    body = Column(Text)
    received_at = Column(DateTime)
    provider = Column(String, default="google", index=True)  # google | microsoft
    external_message_id = Column(String, nullable=True, index=True)
    external_thread_id = Column(String, nullable=True, index=True)

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


class OutlookAccount(Base):
    """Microsoft Outlook account OAuth credentials"""
    __tablename__ = "outlook_accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    user_id = Column(String, index=True, nullable=True)

    # OAuth tokens (encrypted)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)

    # Metadata
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Microsoft delta sync tracking
    last_delta_token = Column(Text, nullable=True)
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

    # Connected provider (MVP single-provider mode)
    # none | google | microsoft
    connected_provider = Column(String, default="none", index=True)

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
    subscription_status = Column(String, default="trialing")  # trialing | active | cancel_scheduled | canceled | past_due | expired
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    dodo_customer_id = Column(String, index=True, nullable=True)
    dodo_subscription_id = Column(String, index=True, nullable=True)
    polar_customer_id = Column(String, index=True, nullable=True)
    polar_subscription_id = Column(String, index=True, nullable=True)
    # Dunning state (calm recovery window before pausing access)
    dunning_active = Column(Boolean, default=False, index=True)
    dunning_started_at = Column(DateTime, nullable=True)
    dunning_deadline_at = Column(DateTime, nullable=True, index=True)
    dunning_attempt_count = Column(Integer, default=0)
    dunning_last_notified_stage = Column(String, nullable=True)  # initial | midpoint | final
    dunning_last_payment_failed_at = Column(DateTime, nullable=True)
    dunning_suspended_at = Column(DateTime, nullable=True, index=True)

    # Trial warning tracking (from migration 022)
    last_trial_warning_sent = Column(DateTime, nullable=True)  # When last warning was sent
    last_trial_warning_milestone = Column(String, nullable=True)  # 3_days | 1_day | expired

    # Personalization & Onboarding (from migration 023)
    assistant_name = Column(String, default="Teeks")  # User's chosen name for AI assistant
    onboarding_completed = Column(Boolean, default=False)  # True after first-time setup

    # Personal profile (from migration 054)
    full_name = Column(Text, nullable=True)
    preferred_name = Column(Text, nullable=True)
    role = Column(Text, default="Executive Assistant")
    personal_preferences = Column(Text, nullable=True)

    # Executive profile (from migration 055)
    exec_full_name = Column(Text, nullable=True)
    exec_preferred_name = Column(Text, nullable=True)
    exec_role = Column(Text, nullable=True)
    exec_preferences = Column(Text, nullable=True)

    # Credit system (from migration 027)
    credits_used = Column(Float, default=0.0)  # USD spent on billable AI models this period
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
        settings = get_settings()

        # Dunning suspension takes precedence over all active states.
        if self.dunning_suspended_at:
            return False

        if self.subscription_tier == "pro":
            allowed_statuses = ["active", "trialing", "cancel_scheduled"]
            if self.dunning_active and not self.dunning_suspended_at:
                allowed_statuses.append("past_due")
            # "cancel_scheduled" keeps access until period end (+ configured grace).
            if self.subscription_status not in allowed_statuses:
                return False
            # Also verify subscription hasn't expired (handles webhook delays)
            if self.subscription_expires_at:
                pro_grace_days = max(0, int(getattr(settings, "PRO_GRACE_DAYS", 4)))
                grace_cutoff = self.subscription_expires_at + timedelta(days=pro_grace_days)
                return grace_cutoff > (now - CLOCK_SKEW_TOLERANCE)
            # No expiry date set - trust status (edge case during initial setup)
            return True

        # Trial user - no grace period by policy.
        if self.trial_ends_at and self.trial_ends_at > (now - CLOCK_SKEW_TOLERANCE):
            return True

        return False

    @property
    def days_remaining(self) -> int:
        """Days remaining in trial or subscription"""
        now = datetime.now(timezone.utc)
        settings = get_settings()

        if self.subscription_tier == "pro" and self.subscription_expires_at:
            hard_delta = self.subscription_expires_at - now
            if hard_delta.days > 0:
                return max(0, hard_delta.days)

            # While inside pro grace, expose remaining days until access cutoff.
            if self.subscription_status in ["active", "trialing", "cancel_scheduled"]:
                pro_grace_days = max(0, int(getattr(settings, "PRO_GRACE_DAYS", 4)))
                grace_end = self.subscription_expires_at + timedelta(days=pro_grace_days)
                grace_delta = grace_end - now
                return max(0, grace_delta.days)
            return 0

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

    @property
    def dunning_days_remaining(self) -> int:
        """Days remaining before dunning pause takes effect."""
        if not self.dunning_active or not self.dunning_deadline_at:
            return 0
        now = datetime.now(timezone.utc)
        return max(0, (self.dunning_deadline_at - now).days)


class AutomationUserSetting(Base):
    """Per-user automation state for productized automations."""
    __tablename__ = "automation_user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "automation_id", name="uq_automation_user_settings_user_automation"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    automation_id = Column(String, nullable=False, index=True)
    configured = Column(Boolean, default=False, nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    safety_mode = Column(String, nullable=False, default="review_required")
    execution_mode = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AutomationRun(Base):
    """Execution log for automation previews and runs."""
    __tablename__ = "automation_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    automation_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="completed", index=True)
    trigger = Column(String, nullable=False, default="manual")
    summary = Column(Text, nullable=True)
    run_metadata = Column(JSON, default=dict)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


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

    # Task Type/Category (work category)
    task_type = Column(String, index=True, default="other")  # follow_up, scheduling, prep, decision, review, other
    # Task Signal (how detected)
    task_signal = Column(String, index=True, default="explicit")  # explicit | implied | inferred_pattern
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
    reminders = relationship("TaskReminder", back_populates="task", cascade="all, delete-orphan")


class TaskReminder(Base):
    """Audit log of every reminder sent (or attempted) for a task."""
    __tablename__ = "task_reminders"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # denormalised for RLS

    reminded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    reminder_type = Column(String, nullable=False, default="scheduled")  # scheduled | urgent_nudge | digest | manual
    channel = Column(String, nullable=False, default="push")              # push | email | in_app
    delivered = Column(Boolean, default=False)
    delivery_error = Column(Text, nullable=True)  # set if push/email delivery failed

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    task = relationship("Task", back_populates="reminders")


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


class SchedulingIntent(Base):
    """
    Lean scheduling intent record created when an email with scheduling intent is processed.

    Replaces the old SchedulingSuggestion model. No pre-generated slots or draft replies —
    those are produced on-demand by CalendarOrchestrator when the user takes action.
    """
    __tablename__ = "scheduling_intents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True)
    thread_id = Column(String, index=True)
    sender_name = Column(String, nullable=True)
    sender_email = Column(String, nullable=True)
    intent_type = Column(String, nullable=False, default="availability_request")
    # availability_request | time_request | meeting_confirmation | meeting_reminder | reschedule_request
    intent_summary = Column(Text, nullable=True)  # "Sarah asked when you're free for the Q4 review"
    meeting_title = Column(String, nullable=True)  # extracted for calendar matching
    meeting_date = Column(Date, nullable=True)     # extracted date for calendar matching
    matched_event_id = Column(Integer, ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    # pending | sent | dismissed | acknowledged | added | expired
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


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

    # Label: meeting | personal | travel | deadline | other
    # Only 'meeting' events get briefings. Auto-classified during sync; user can override.
    label = Column(String, nullable=True, index=True)

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

    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uq_thread_states_user_thread_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, nullable=False, index=True)
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
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ContactContext(Base):
    """
    Legacy per-contact metadata.

    Canonical relationship intelligence belongs in Contact and ContextEntry.
    Keep this model only for backward-compatible derived metrics/manual metadata
    that older filtering and vault flows still read.

    Auto-stored: derived interaction frequency, last interaction, channel
    Manual-only: legacy notes, contact category

    Rules:
    - No emotional inference
    - No auto-written relationship notes
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


class ContextEntry(Base):
    """Structured long-term memory entry for assistant/executive/contact/thread/message/event context."""
    __tablename__ = "context_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)  # decision|commitment|preference|risk|insight
    content = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=True)  # Original capture text before/alongside structured organization
    input_source = Column(String, nullable=False, default="typed", server_default="typed", index=True)  # typed|voice
    entity_type = Column(String, nullable=False, index=True)  # global|contact|thread|message|event|task
    entity_id = Column(String, nullable=True, index=True)    # email for contacts, string ref for threads/events/messages/tasks
    linked_to = Column(String, nullable=True, index=True)    # display name of the primary linked entity (e.g. "Sarah Chen", "Q4 Review")
    created_by = Column(String, nullable=False, default="You")  # Teeks|You
    status = Column(String, nullable=False, default="active", index=True)  # active|resolved|stale|archived|forgotten
    classification_status = Column(String, nullable=False, default="classified", index=True)  # pending|classified|user_corrected
    classification_confidence = Column(Float, nullable=True)
    classification_suggested_type = Column(String, nullable=True)
    user_corrected = Column(Boolean, nullable=False, default=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "type IN ('decision','commitment','preference','risk','insight')",
            name="ck_context_entries_type",
        ),
        CheckConstraint(
            "input_source IN ('typed','voice')",
            name="ck_context_entries_input_source",
        ),
        CheckConstraint(
            "entity_type IN ('global','contact','thread','message','event','task')",
            name="ck_context_entries_entity_type",
        ),
        CheckConstraint(
            "created_by IN ('Teeks','You')",
            name="ck_context_entries_created_by",
        ),
        CheckConstraint(
            "status IN ('active','resolved','stale','archived','forgotten')",
            name="ck_context_entries_status",
        ),
        CheckConstraint(
            "classification_status IN ('pending','classified','user_corrected')",
            name="ck_context_entries_classification_status",
        ),
        CheckConstraint(
            "classification_suggested_type IS NULL OR classification_suggested_type IN ('decision','commitment','preference','risk','insight')",
            name="ck_context_entries_classification_suggested_type",
        ),
        Index("ix_context_entries_user_entity", "user_id", "entity_type", "entity_id"),
        Index("ix_context_entries_user_type", "user_id", "type"),
    )

    links = relationship("DiaryEntryLink", back_populates="entry", cascade="all, delete-orphan", lazy="selectin")


class DiaryEntryLink(Base):
    """Multiple entity links for a single diary context entry (from @mentions)."""
    __tablename__ = "diary_entry_links"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("context_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)   # contact|thread|message|event|task
    entity_id = Column(Text, nullable=False)            # email for contacts, ref for others
    display_name = Column(Text, nullable=False)         # @label shown to user
    source = Column(String(20), nullable=False, default="user", server_default="user")  # user|teeks
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    entry = relationship("ContextEntry", back_populates="links")


class Contact(Base):
    """User-managed contact catalog for mention resolution and context scoping."""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    role = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # vip, colleague, external, vendor
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_contacts_user_email"),
    )


class EntityReference(Base):
    """Catalog of user-friendly entity references for thread/event/message mention resolution."""
    __tablename__ = "entity_references"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)  # thread|message|event
    display_name = Column(String, nullable=False, index=True)
    ref = Column(String, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('thread','message','event')",
            name="ck_entity_references_type",
        ),
        UniqueConstraint("user_id", "entity_type", "display_name", name="uq_entity_refs_user_type_name"),
        UniqueConstraint("user_id", "entity_type", "ref", name="uq_entity_refs_user_type_ref"),
    )


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
    reviewed_at = Column(DateTime, nullable=True)

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


class BillingPlan(Base):
    """Billing plan catalog (provider plan/product mapping)."""
    __tablename__ = "billing_plans"
    __table_args__ = (
        UniqueConstraint("provider", "plan_id", name="uq_billing_plans_provider_plan"),
        CheckConstraint("billing_interval IN ('monthly','annual','one_time')", name="ck_billing_plans_interval"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)  # dodo | polar
    plan_id = Column(String, nullable=False, index=True)   # provider plan/product id
    name = Column(String, nullable=True)
    price_minor = Column(Integer, nullable=True)           # cents / minor unit
    currency = Column(String, nullable=False, default="USD")
    billing_interval = Column(String, nullable=False, default="monthly")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)


class BillingSubscription(Base):
    """User subscription snapshot from provider events."""
    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subscription_id", name="uq_billing_subscriptions_provider_sub"),
        CheckConstraint(
            "status IN ('active','trialing','cancel_scheduled','canceled','past_due','expired')",
            name="ck_billing_subscriptions_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_subscription_id = Column(String, nullable=True, index=True)
    provider_customer_id = Column(String, nullable=True, index=True)
    plan_id = Column(Integer, ForeignKey("billing_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_external_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="trialing", index=True)
    current_period_start = Column(DateTime, nullable=True, index=True)
    current_period_end = Column(DateTime, nullable=True, index=True)
    cancel_at_period_end = Column(Boolean, default=False, index=True)
    canceled_at = Column(DateTime, nullable=True, index=True)
    # DB column is `metadata` from migration 052; keep attribute as provider_metadata in app code.
    provider_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)


class BillingInvoice(Base):
    """Invoices generated by billing provider."""
    __tablename__ = "billing_invoices"
    __table_args__ = (
        UniqueConstraint("provider", "provider_invoice_id", name="uq_billing_invoices_provider_invoice"),
        CheckConstraint("status IN ('draft','open','paid','void','uncollectible','failed')", name="ck_billing_invoices_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    provider_invoice_id = Column(String, nullable=True, index=True)
    subscription_id = Column(Integer, ForeignKey("billing_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    provider_subscription_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="open", index=True)
    currency = Column(String, nullable=False, default="USD")
    amount_due_minor = Column(Integer, nullable=True)
    amount_paid_minor = Column(Integer, nullable=True)
    amount_remaining_minor = Column(Integer, nullable=True)
    invoice_pdf_url = Column(Text, nullable=True)
    hosted_invoice_url = Column(Text, nullable=True)
    period_start = Column(DateTime, nullable=True, index=True)
    period_end = Column(DateTime, nullable=True, index=True)
    due_at = Column(DateTime, nullable=True, index=True)
    paid_at = Column(DateTime, nullable=True, index=True)
    # DB column is `metadata` from migration 052; keep attribute as provider_metadata in app code.
    provider_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)


class BillingPaymentAttempt(Base):
    """Payment attempts for invoices/subscription renewals."""
    __tablename__ = "billing_payment_attempts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_attempt_id", name="uq_billing_payment_attempts_provider_attempt"),
        CheckConstraint(
            "status IN ('pending','succeeded','failed','requires_action','canceled')",
            name="ck_billing_payment_attempts_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("billing_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    provider_attempt_id = Column(String, nullable=True, index=True)
    provider_payment_id = Column(String, nullable=True, index=True)
    provider_subscription_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    currency = Column(String, nullable=False, default="USD")
    amount_minor = Column(Integer, nullable=True)
    failure_code = Column(String, nullable=True, index=True)
    failure_message = Column(Text, nullable=True)
    attempted_at = Column(DateTime, nullable=True, index=True)
    # DB column is `metadata` from migration 052; keep attribute as provider_metadata in app code.
    provider_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class CreditTopup(Base):
    """One-time purchased AI credit top-ups."""
    __tablename__ = "credit_topups"
    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id", name="uq_credit_topups_provider_payment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)  # dodo | polar
    provider_payment_id = Column(String, nullable=False, index=True)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="USD")
    credits_added = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    provider_metadata = Column(JSON, default=dict)


class BillingEvent(Base):
    """Normalized billing event audit trail."""
    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "delivery_id", name="uq_billing_events_provider_delivery"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=False, index=True)
    delivery_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=True, index=True)
    subscription_id = Column(String, nullable=True, index=True)
    invoice_id = Column(String, nullable=True, index=True)
    handled = Column(Boolean, default=False, index=True)
    error = Column(Text, nullable=True)
    payload = Column(JSON, default=dict)  # minimized normalized payload only; raw webhook bodies should not persist
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    processed_at = Column(DateTime, nullable=True, index=True)


class WebhookLog(Base):
    """Append-only log of incoming webhooks for health monitoring and audit."""
    __tablename__ = "webhook_logs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)        # "dodo" | "polar" | "gmail" | "outlook"
    event_type = Column(String, nullable=False, index=True)    # e.g. "subscription.created", "gmail_push"
    processed = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    user_id = Column(String, nullable=True, index=True)
    provider_customer_id = Column(String, nullable=True, index=True)
    subject_ref = Column(String, nullable=True, index=True)
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class WebhookDelivery(Base):
    """
    Dedupe table for webhook delivery IDs.

    Stores provider delivery IDs after successful processing so retried
    deliveries can be acknowledged idempotently.
    """
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("source", "delivery_id", name="uq_webhook_deliveries_source_delivery"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, index=True)  # "gmail" | "outlook" | "dodo" | "polar"
    delivery_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    provider_customer_id = Column(String, nullable=True, index=True)
    subject_ref = Column(String, nullable=True, index=True)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class ApiIdempotencyKey(Base):
    """
    Idempotency records for mutating API requests.

    Enforces exactly-once semantics for repeated client retries using
    Idempotency-Key headers on sensitive billing operations.
    """
    __tablename__ = "api_idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "route_key", "idempotency_key", name="uq_api_idempotency_user_route_key"),
        Index("ix_api_idempotency_expires", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    route_key = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, nullable=False, index=True)
    request_hash = Column(String, nullable=False, index=True)
    response_status = Column(Integer, nullable=False, default=0)
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


class UITelemetryEvent(Base):
    """Product telemetry events emitted from frontend interactions."""
    __tablename__ = "ui_telemetry_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    event_id = Column(String, nullable=True, index=True)
    event_name = Column(String, nullable=False, index=True)
    event_payload = Column(JSON, default=dict)
    page_path = Column(String, nullable=True, index=True)
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


class ChatModelCallMetric(Base):
    """Per-call chat model metrics for latency/prompt-cache decisioning."""
    __tablename__ = "chat_model_call_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)  # pseudonymous session hash only
    model = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, index=True)  # genai | orchestrator
    path = Column(String, nullable=False, index=True)  # native | fallback

    latency_ms = Column(Integer, nullable=False, default=0)
    prompt_chars = Column(Integer, nullable=False, default=0)
    response_chars = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    repeated_prefix_chars = Column(Integer, nullable=False, default=0)
    repeated_prefix_rate = Column(Float, nullable=False, default=0.0)

    tool_definitions_count = Column(Integer, nullable=False, default=0)
    tool_calls_count = Column(Integer, nullable=False, default=0)

    success = Column(Boolean, nullable=False, default=True)
    error_type = Column(String, nullable=True)


class CalendarWatchChannel(Base):
    """Active Google Calendar push notification watch channels.

    Each channel corresponds to one calendar being watched for one user.
    Channels must be explicitly stopped before renewal (unlike Gmail Pub/Sub).
    """
    __tablename__ = "calendar_watch_channels"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False, unique=True)  # UUID we generate, sent to Google
    resource_id = Column(String, nullable=False)              # Google's resource ID, needed to stop
    calendar_id = Column(String, nullable=False)              # Which calendar this channel watches
    expiration = Column(DateTime, nullable=False)             # When Google will stop sending notifications (UTC)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class OutlookWatchSubscription(Base):
    """Microsoft Graph subscriptions for Outlook mail/calendar change notifications."""
    __tablename__ = "outlook_watch_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    subscription_id = Column(String, nullable=False, unique=True)
    resource = Column(String, nullable=False)
    client_state = Column(String, nullable=False)
    expiration = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
