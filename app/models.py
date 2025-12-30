from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Float, ForeignKey
from datetime import datetime, timezone
from .database import Base
from core.queue.models import create_task_queue_model

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    thread_id = Column(String, index=True)
    subject = Column(String)
    sender = Column(String)
    recipient = Column(String)
    body = Column(Text)
    received_at = Column(DateTime)

    # AI-generated fields
    summary = Column(Text, nullable=True)
    needs_reply = Column(Boolean, nullable=True)
    extracted_tasks = Column(JSON, nullable=True)
    extracted_dates = Column(JSON, nullable=True)
    extracted_people = Column(JSON, nullable=True)
    extracted_decisions = Column(JSON, nullable=True)
    draft_reply = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    processed = Column(Boolean, default=False)
    status = Column(String, default="inbox", index=True)  # inbox | done | archived

    # Data Lifecycle fields
    content_expired = Column(Boolean, default=False, index=True)  # True when body deleted after retention period
    source_deleted = Column(Boolean, default=False, index=True)   # True when Gmail reports message deleted
    body_encrypted = Column(Boolean, default=False)  # True when body is encrypted at rest

    @property
    def decrypted_body(self) -> str:
        """Get decrypted body content, handling encryption and expiration"""
        if not self.body:
            return ""
        if self.content_expired:
            return "[Content expired]"
        if self.body_encrypted:
            from .encryption import decrypt_body
            return decrypt_body(self.body)
        return self.body

class GmailAccount(Base):
    __tablename__ = "gmail_accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)

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

# Create TaskQueue model using reusable factory from core/queue
TaskQueue = create_task_queue_model(Base)


class UserSettings(Base):
    """User preferences for task management, reminders, and calendar"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, unique=True, index=True)

    # Task Detection
    auto_approve_tasks = Column(Boolean, default=False)
    task_detection_instructions = Column(Text, nullable=True)

    # Reminder Preferences (JSON)
    reminder_preferences = Column(JSON, default=lambda: {
        "max_reminders_per_day": 10,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "default_reminder_offset_hours": 24
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

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Task(Base):
    """Structured tasks extracted from messages with smart reminders"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    # Link to source message (REQUIRED)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)

    # Task Details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source_snippet = Column(Text, nullable=True)  # Context snippet from email explaining why this task exists

    # Task Type/Category
    task_type = Column(String, index=True)  # explicit, implied_followup, waiting_for, meeting_prep
    priority = Column(String, default="normal")  # low, normal, high, urgent

    # Approval Workflow
    status = Column(String, default="pending_approval", index=True)
    # Status options: pending_approval, approved, dismissed, completed, snoozed
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
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

    # Metadata
    confidence_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TaskReminder(Base):
    """History of reminders sent for tasks"""
    __tablename__ = "task_reminders"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)

    reminded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reminder_type = Column(String)  # scheduled, urgent_nudge, digest
    delivered = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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
    related_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)

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
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)

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
    Calendar events created from confirmed scheduling suggestions.
    Our database is the source of truth, not the calendar provider.
    """
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)

    # Event details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)  # AI-generated from email context
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    participants = Column(JSON, default=list)  # List of attendee emails
    timezone = Column(String, default="UTC")  # IANA format
    location = Column(String, nullable=True)  # Meeting link or physical location

    # Relations
    source_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    source_suggestion_id = Column(Integer, ForeignKey("scheduling_suggestions.id"), nullable=True, index=True)

    # External calendar integration
    provider = Column(String, default="google")  # google (MVP only)
    external_event_id = Column(String, nullable=True, index=True)  # ID from Google Calendar API

    # Status: pending | created | failed
    status = Column(String, default="pending", index=True)
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

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
