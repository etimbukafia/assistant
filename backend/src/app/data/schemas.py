from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any

class MessageBase(BaseModel):
    subject: str
    sender: str
    recipient: str
    body: str

class MessageCreate(MessageBase):
    message_id: str
    thread_id: str
    received_at: datetime

class TaskInMessage(BaseModel):
    """Simplified task schema for embedding in messages (no source_message to avoid circular ref)"""
    id: int
    message_id: int
    title: str
    description: Optional[str] = None
    source_snippet: Optional[str] = None
    task_type: str = Field(serialization_alias="type")
    priority: str
    status: str
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    reminder_context: Optional[Dict[str, Any]] = None
    scheduled_reminder_at: Optional[datetime] = None
    confidence_score: Optional[float] = Field(default=None, serialization_alias="confidence")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageResponse(MessageBase):
    id: int
    message_id: str
    thread_id: str
    received_at: datetime
    summary: Optional[str] = None
    needs_reply: Optional[bool] = None
    extracted_tasks: Optional[List[str]] = None
    extracted_dates: Optional[List[str]] = None
    extracted_people: Optional[List[str]] = None
    extracted_decisions: Optional[List[str]] = None
    draft_reply: Optional[str] = None
    processed: bool
    created_at: datetime
    tasks: Optional[List[TaskInMessage]] = None  # Related tasks from Task table

    model_config = ConfigDict(from_attributes=True)

class SyncResponse(BaseModel):
    synced_count: int
    processed_count: int
    message: str

class DraftReplyRequest(BaseModel):
    context: Optional[str] = None

class DraftReplyResponse(BaseModel):
    draft: str

class MessagesListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int


# ========================================
# User Settings Schemas
# ========================================

class UserSettingsResponse(BaseModel):
    id: int
    user_email: str
    auto_approve_tasks: bool
    task_detection_instructions: Optional[str] = None
    reminder_preferences: Dict[str, Any]
    enable_quick_reply_from_task: bool
    # Subscription fields
    subscription_tier: str = "trial"
    subscription_status: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    is_active: bool = False  # True if trial/pro is currently valid
    days_remaining: int = 0
    # Integration status
    initial_sync_completed: bool = False
    gmail_connected: bool = False
    calendar_connected: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdateRequest(BaseModel):
    auto_approve_tasks: Optional[bool] = None
    task_detection_instructions: Optional[str] = None
    reminder_preferences: Optional[Dict[str, Any]] = None
    enable_quick_reply_from_task: Optional[bool] = None


# ========================================
# Task Schemas
# ========================================

class TaskResponse(BaseModel):
    id: int
    message_id: int
    title: str
    description: Optional[str] = None
    source_snippet: Optional[str] = None

    # Primary fields with frontend-compatible aliases
    task_type: str = Field(serialization_alias="type")
    priority: str
    status: str

    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    reminder_context: Optional[Dict[str, Any]] = None
    scheduled_reminder_at: Optional[datetime] = None
    last_reminded_at: Optional[datetime] = None
    reminder_count: int
    snoozed_until: Optional[datetime] = None
    related_people: List[str]
    related_dates: List[str]

    confidence_score: Optional[float] = Field(default=None, serialization_alias="confidence")

    created_at: datetime
    updated_at: datetime
    source_message: Optional[MessageResponse] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TasksListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int


class TaskCreateRequest(BaseModel):
    """Request to create a task from extracted text or manually"""
    message_id: int
    title: str
    description: Optional[str] = None
    source_snippet: Optional[str] = None
    task_type: str = "explicit"
    priority: str = "normal"
    status: str = "approved"  # When user manually approves, it's already approved


class ManualTaskCreateRequest(BaseModel):
    """Request to create a standalone task (not linked to an email)"""
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    deadline: Optional[datetime] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    scheduled_reminder_at: Optional[datetime] = None


class TaskSnoozeRequest(BaseModel):
    snooze_until: datetime


# ========================================
# Scheduling & Calendar Schemas
# ========================================

class TimeSlotSchema(BaseModel):
    """A suggested time slot for scheduling"""
    start_time: datetime
    end_time: datetime
    has_conflict: bool = False
    conflict_details: Optional[str] = None


class SchedulingSuggestionResponse(BaseModel):
    """Response for a scheduling suggestion"""
    id: int
    thread_id: str
    message_id: int
    participants: List[str]
    suggested_slots: List[Dict[str, Any]]  # List of TimeSlot dicts
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    timezone: str
    meeting_type: str
    duration_minutes: int
    intent_type: str = "availability_request"
    source_text_snippet: Optional[str] = None
    draft_reply: Optional[str] = None
    draft_event_description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchedulingSuggestionSendRequest(BaseModel):
    """Request to send availability reply"""
    edited_reply: Optional[str] = None  # Uses draft if not provided


class CalendarEventCreateRequest(BaseModel):
    """Request to create a calendar event from a suggestion"""
    suggestion_id: int
    selected_slot_index: int = 0
    title: Optional[str] = None  # Uses default if not provided
    description: Optional[str] = None  # Uses draft if not provided
    location: Optional[str] = None


class CalendarEventResponse(BaseModel):
    """Response for a calendar event"""
    id: int
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    participants: List[str]
    timezone: str
    location: Optional[str] = None
    source_message_id: Optional[int] = None
    source_suggestion_id: Optional[int] = None
    provider: str
    external_event_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarAvailabilityRequest(BaseModel):
    """Request to check calendar availability"""
    start_time: datetime
    end_time: datetime
    calendar_ids: Optional[List[str]] = None


class CalendarAvailabilityResponse(BaseModel):
    """Response with busy time slots"""
    busy_slots: List[Dict[str, Any]]
    timezone: str


class CalendarSettingsResponse(BaseModel):
    """Calendar-related user settings"""
    default_meeting_duration: int
    preferred_meeting_times: str
    buffer_minutes: int
    working_hours_start: str
    working_hours_end: str
    default_timezone: str
    calendar_ids: List[str]


class CalendarSettingsUpdateRequest(BaseModel):
    """Request to update calendar settings"""
    default_meeting_duration: Optional[int] = None
    preferred_meeting_times: Optional[str] = None
    buffer_minutes: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    default_timezone: Optional[str] = None
    calendar_ids: Optional[List[str]] = None


class CalendarInfoResponse(BaseModel):
    """Basic calendar information"""
    id: str
    summary: str
    primary: bool = False
    access_role: str = "reader"


# ========================================
# Principal Memory Schemas (Executive Context Engine)
# ========================================

class PrincipalMemoryBase(BaseModel):
    """Base schema for principal memory preferences"""
    key: str
    value: str
    context_type: str  # drafting | scheduling | task_review


class PrincipalMemoryCreate(PrincipalMemoryBase):
    """Request to create a new preference"""
    source: str = "manual"  # manual | approved_suggestion


class PrincipalMemoryUpdate(BaseModel):
    """Request to update a preference"""
    value: Optional[str] = None
    context_type: Optional[str] = None


class PrincipalMemoryResponse(PrincipalMemoryBase):
    """Response for a principal memory entry"""
    id: int
    user_id: str
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrincipalMemoryListResponse(BaseModel):
    """List of all preferences"""
    preferences: List[PrincipalMemoryResponse]
    total: int


# ========================================
# Decision Pattern Schemas
# ========================================

class DecisionPatternResponse(BaseModel):
    """Response for an observed decision pattern"""
    id: int
    user_id: str
    pattern_key: str
    pattern_type: str
    context_type: str
    conditions: Optional[Dict[str, Any]] = None
    action: str
    occurrences: int
    confidence: float
    last_occurrence_at: datetime
    status: str  # observed | suggested | rejected | approved
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionPatternListResponse(BaseModel):
    """List of decision patterns"""
    patterns: List[DecisionPatternResponse]
    total: int


class DecisionPatternActionRequest(BaseModel):
    """Request to act on a pattern suggestion"""
    action: str  # approve | reject | not_now


# ========================================
# Contact Context Schemas
# ========================================

class ContactMetadata(BaseModel):
    """Auto-tracked contact metadata (factual, observable only)"""
    message_count: int = 0
    last_interaction_at: Optional[datetime] = None
    avg_response_latency_hours: Optional[float] = None
    primary_channel: str = "email"
    typical_time_of_day: Optional[str] = None  # morning | afternoon | evening
    urgency_frequency: int = 0


class ContactContextResponse(BaseModel):
    """Response for contact context"""
    id: int
    user_id: str
    contact_email: str
    contact_name: Optional[str] = None
    contact_metadata: Dict[str, Any]
    notes: Optional[str] = None
    category: Optional[str] = None  # vip | colleague | external | vendor
    preferred_tone: Optional[str] = None  # formal | neutral | casual
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactContextUpdateRequest(BaseModel):
    """Request to update contact context (manual fields only)"""
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    preferred_tone: Optional[str] = None


class ContactContextListResponse(BaseModel):
    """List of contact contexts"""
    contacts: List[ContactContextResponse]
    total: int


# ========================================
# Digest Schemas
# ========================================

class DigestTimeConfig(BaseModel):
    """Configuration for a specific digest type"""
    enabled: bool = True
    time: str = "08:00"  # HH:MM format
    include: List[str] = []  # What to include in this digest


class WeeklyDigestConfig(BaseModel):
    """Configuration for weekly review digest"""
    enabled: bool = True
    day: str = "monday"  # Day of week
    time: str = "09:00"
    include: List[str] = []


class DigestPreferences(BaseModel):
    """User preferences for digest generation and delivery"""
    enabled: bool = False
    morning_briefing: Optional[DigestTimeConfig] = None
    end_of_day: Optional[DigestTimeConfig] = None
    weekly_review: Optional[WeeklyDigestConfig] = None
    delivery_channel: str = "email"  # email | telegram | push


class DigestStatsResponse(BaseModel):
    """Stats included in a digest"""
    urgent_count: Optional[int] = None
    due_today_count: Optional[int] = None
    threads_needing_reply_count: Optional[int] = None
    events_count: Optional[int] = None
    pending_approval_count: Optional[int] = None
    completed_count: Optional[int] = None
    pending_count: Optional[int] = None
    overdue_count: Optional[int] = None
    tomorrow_events_count: Optional[int] = None


class DigestResponse(BaseModel):
    """Response for a generated digest"""
    id: int
    user_id: str
    user_email: str
    digest_type: str  # morning_briefing | end_of_day | weekly_review
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    content: Dict[str, Any]  # Structured digest content
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    delivery_channel: str
    delivery_status: str  # pending | sent | failed
    delivered_at: Optional[datetime] = None
    delivery_error: Optional[str] = None
    task_count: int = 0
    thread_count: int = 0
    event_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DigestsListResponse(BaseModel):
    """List of digests"""
    digests: List[DigestResponse]
    total: int
