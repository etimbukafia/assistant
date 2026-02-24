from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

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
    task_signal: Optional[str] = None
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
    extracted_tasks: Optional[List[Any]] = None
    extracted_dates: Optional[List[str]] = None
    extracted_people: Optional[List[str]] = None
    extracted_decisions: Optional[List[Any]] = None
    draft_reply: Optional[str] = None
    processed: bool
    created_at: datetime
    tasks: Optional[List[TaskInMessage]] = None  # Related tasks from Task table

    model_config = ConfigDict(from_attributes=True)

class ThreadStateResponse(BaseModel):
    """Thread-level AI state for the detail view"""
    summary: Optional[str] = None
    open_tasks: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    participants: List[Dict[str, Any]] = []
    action_points: List[str] = []
    needs_reply: bool = False
    message_count: int = 0
    last_action: Optional[str] = None
    last_action_by: Optional[str] = None

class ThreadMessageResponse(BaseModel):
    """A single message within a thread detail view"""
    id: int
    sender: str
    subject: Optional[str] = None
    body: str
    summary: Optional[str] = None
    received_at: datetime
    status: str = "inbox"
    scheduling_intent: bool = False
    scheduling_intent_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SyncResponse(BaseModel):
    synced_count: int
    processed_count: int
    message: str

class DraftReplyRequest(BaseModel):
    context: Optional[str] = None

class DraftReplyResponse(BaseModel):
    draft: str

class SendReplyRequest(BaseModel):
    body: str
    to: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    subject: Optional[str] = None

class SendReplyResponse(BaseModel):
    sent: bool
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    error: Optional[str] = None

class MessagesListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int


# ========================================
# User Settings Schemas
# ========================================

class UserSettingsResponse(BaseModel):
    id: int
    user_email: str
    notification_email: Optional[str] = None
    auto_approve_tasks: bool
    task_detection_instructions: Optional[str] = None
    reminder_preferences: Dict[str, Any]
    notification_preferences: Dict[str, Any] = {}
    enable_quick_reply_from_task: bool
    # Subscription fields
    subscription_tier: str = "trial"
    subscription_status: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    is_active: bool = False  # True if trial/pro is currently valid
    days_remaining: int = 0
    
    # Personalization & Onboarding
    assistant_name: str = "Teeks"
    onboarding_completed: bool = False

    # Integration status
    initial_sync_completed: bool = False
    initial_sync_failed: bool = False
    gmail_connected: bool = False
    calendar_connected: bool = False
    default_calendar_id: Optional[str] = None
    auto_briefing_enabled: Optional[bool] = None
    briefing_hours_before: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdateRequest(BaseModel):
    auto_approve_tasks: Optional[bool] = None
    task_detection_instructions: Optional[str] = None
    reminder_preferences: Optional[Dict[str, Any]] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    enable_quick_reply_from_task: Optional[bool] = None
    assistant_name: Optional[str] = None
    notification_email: Optional[str] = None
    default_calendar_id: Optional[str] = None
    auto_briefing_enabled: Optional[bool] = None
    briefing_hours_before: Optional[int] = None


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
    task_signal: Optional[str] = None
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
    deadline: Optional[datetime] = Field(default=None, serialization_alias="deadline_at")
    deadline_source: Optional[str] = None
    deadline_user_confirmed: Optional[bool] = None

    confidence_score: Optional[float] = Field(default=None, serialization_alias="confidence")

    created_at: datetime
    updated_at: datetime
    source_message: Optional[MessageResponse] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TaskListItem(BaseModel):
    """Slim task schema for list endpoints (no source_message payload)."""
    id: int
    message_id: int
    title: str
    description: Optional[str] = None
    source_snippet: Optional[str] = None

    task_type: str = Field(serialization_alias="type")
    task_signal: Optional[str] = None
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
    deadline: Optional[datetime] = Field(default=None, serialization_alias="deadline_at")
    deadline_source: Optional[str] = None
    deadline_user_confirmed: Optional[bool] = None

    confidence_score: Optional[float] = Field(default=None, serialization_alias="confidence")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TasksListResponse(BaseModel):
    tasks: List[TaskListItem]
    total: int


class TaskCreateRequest(BaseModel):
    """Request to create a task from extracted text or manually"""
    message_id: int
    title: str
    description: Optional[str] = None
    source_snippet: Optional[str] = None
    task_type: str = "other"
    task_signal: str = "explicit"
    priority: str = "normal"
    status: str = "approved"  # When user manually approves, it's already approved


class ManualTaskCreateRequest(BaseModel):
    """Request to create a standalone task (not linked to an email)"""
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    deadline: Optional[datetime] = None
    status: str = "approved"


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    scheduled_reminder_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    deadline_confirmed: Optional[bool] = Field(default=None, validation_alias="confirm_deadline")
    mark_urgent: Optional[bool] = None
    clear_deadline: Optional[bool] = None


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


class ThreadDetailResponse(BaseModel):
    """Full thread detail for the Thread Intelligence View"""
    thread_state: ThreadStateResponse
    messages: List[ThreadMessageResponse]
    tasks: List[TaskListItem] = []
    scheduling_suggestions: List[SchedulingSuggestionResponse] = []


class SchedulingSuggestionSendRequest(BaseModel):
    """Request to send availability reply"""
    edited_reply: Optional[str] = None  # Uses draft if not provided


class SchedulingIntentResponse(BaseModel):
    """Response for a scheduling intent (lean record, no pre-generated slots)"""
    id: int
    user_id: str
    message_id: Optional[int] = None
    thread_id: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    intent_type: str
    intent_summary: Optional[str] = None
    meeting_title: Optional[str] = None
    meeting_date: Optional[date] = None
    matched_event_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchedulingIntentsListResponse(BaseModel):
    intents: List[SchedulingIntentResponse]
    total: int


class OrchestratorRunRequest(BaseModel):
    """Optional user context note passed to CalendarOrchestrator"""
    user_note: Optional[str] = None


class OrchestratorRunResponse(BaseModel):
    """Ephemeral result from CalendarOrchestrator — not stored"""
    suggested_slots: List[Dict[str, Any]]  # [{start_time, end_time, label}]
    draft_reply: str
    reasoning: Optional[str] = None  # brief explanation of slot choices


class IntentSendRequest(BaseModel):
    """Request to send a scheduling reply (and optionally create a calendar event)"""
    edited_reply: Optional[str] = None
    slot_index: Optional[int] = None  # if adding to calendar at the same time


class CalendarEventCreateRequest(BaseModel):
    """Request to create a calendar event from a suggestion"""
    suggestion_id: int
    selected_slot_index: int = 0
    title: Optional[str] = None  # Uses default if not provided
    description: Optional[str] = None  # Uses draft if not provided
    location: Optional[str] = None


class CalendarEventManualCreateRequest(BaseModel):
    """Request to create a calendar event directly (not from suggestion)"""
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    notes: Optional[str] = None
    participants: Optional[List[str]] = None
    all_day: Optional[bool] = False
    timezone: Optional[str] = None
    location: Optional[str] = None
    calendar_id: Optional[str] = None
    label: Optional[str] = None  # meeting | personal | travel | deadline | other


class CalendarEventUpdateRequest(BaseModel):
    """Request to update a calendar event"""
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    participants: Optional[List[str]] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    calendar_id: Optional[str] = None
    label: Optional[str] = None  # meeting | personal | travel | deadline | other


class CalendarEventResponse(BaseModel):
    """Response for a calendar event"""
    id: int
    title: str
    description: Optional[str] = None
    notes: Optional[str] = None
    all_day: Optional[bool] = None
    start_time: datetime
    end_time: datetime
    participants: List[str]
    timezone: str
    location: Optional[str] = None
    source_message_id: Optional[int] = None
    source_suggestion_id: Optional[int] = None
    provider: str
    external_event_id: Optional[str] = None
    calendar_id: Optional[str] = None
    label: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    briefing: Optional[Dict[str, Any]] = None
    briefing_generated_at: Optional[datetime] = None
    briefing_scheduled_for: Optional[datetime] = None
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
    default_calendar_id: Optional[str] = None
    auto_briefing_enabled: Optional[bool] = None
    briefing_hours_before: Optional[int] = None


class CalendarSettingsUpdateRequest(BaseModel):
    """Request to update calendar settings"""
    default_meeting_duration: Optional[int] = None
    preferred_meeting_times: Optional[str] = None
    buffer_minutes: Optional[int] = None
    working_hours_start: Optional[str] = None
    working_hours_end: Optional[str] = None
    default_timezone: Optional[str] = None
    calendar_ids: Optional[List[str]] = None  # Which calendars to sync (empty = all)
    default_calendar_id: Optional[str] = None
    auto_briefing_enabled: Optional[bool] = None
    briefing_hours_before: Optional[int] = None


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
    promoted: bool = False
    vault_note_id: Optional[int] = None
    aliases: List[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactContextUpdateRequest(BaseModel):
    """Request to update contact context (manual fields only)"""
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    preferred_tone: Optional[str] = None
    aliases: Optional[List[str]] = None


class ContactContextListResponse(BaseModel):
    """List of contact contexts"""
    contacts: List[ContactContextResponse]
    total: int



# ========================================
# Structured Memory / Diary Schemas
# ========================================

class ContextType(str, Enum):
    decision = "decision"
    commitment = "commitment"
    preferences = "preferences"
    risks = "risks"
    relationships = "relationships"


class ContextEntityType(str, Enum):
    global_ = "global"
    contact = "contact"
    thread = "thread"
    message = "message"
    event = "event"
    task = "task"


class ContextCreatedBy(str, Enum):
    teeks = "Teeks"
    you = "You"


class ContextImportanceLevel(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class ContextEntryStatus(str, Enum):
    active = "active"
    resolved = "resolved"
    stale = "stale"
    archived = "archived"


class ContextEntryBase(BaseModel):
    user_id: str
    type: ContextType
    content: str
    entity_type: ContextEntityType = ContextEntityType.global_
    entity_id: Optional[str] = None
    linked_to: Optional[str] = None
    created_by: ContextCreatedBy
    created_at: datetime
    importance_level: ContextImportanceLevel = ContextImportanceLevel.normal
    status: ContextEntryStatus = ContextEntryStatus.active
    expires_at: Optional[datetime] = None


class DiaryEntryLinkSchema(BaseModel):
    entity_type: str
    entity_id: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class ContextEntryCreate(BaseModel):
    type: ContextType
    content: str
    entity_type: ContextEntityType = ContextEntityType.global_
    entity_id: Optional[str] = None
    linked_to: Optional[str] = None
    created_by: ContextCreatedBy = ContextCreatedBy.you
    importance_level: ContextImportanceLevel = ContextImportanceLevel.normal
    status: ContextEntryStatus = ContextEntryStatus.active
    expires_at: Optional[datetime] = None
    links: List[DiaryEntryLinkSchema] = []


class ContextEntryUpdate(BaseModel):
    content: Optional[str] = None
    importance_level: Optional[ContextImportanceLevel] = None
    status: Optional[ContextEntryStatus] = None
    expires_at: Optional[datetime] = None


class ContextEntryResponse(ContextEntryBase):
    id: int
    updated_at: datetime
    links: List[DiaryEntryLinkSchema] = []

    model_config = ConfigDict(from_attributes=True)


class ContactCreate(BaseModel):
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None  # vip, colleague, external, vendor


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None  # vip, colleague, external, vendor


class ContactResponse(BaseModel):
    id: int
    user_id: str
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntityReferenceType(str, Enum):
    thread = "thread"
    message = "message"
    event = "event"


class EntityReferenceCreate(BaseModel):
    entity_type: EntityReferenceType
    display_name: str
    ref: str
    notes: Optional[str] = None


class EntityReferenceUpdate(BaseModel):
    display_name: Optional[str] = None
    ref: Optional[str] = None
    notes: Optional[str] = None


class EntityReferenceResponse(BaseModel):
    id: int
    user_id: str
    entity_type: EntityReferenceType
    display_name: str
    ref: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MentionSuggestionResponse(BaseModel):
    kind: str
    ref: str
    label: str
    display_label: Optional[str] = None
    subtitle: Optional[str] = None


# ========================================
# Vault Schemas
# ========================================

class VaultNoteCreate(BaseModel):
    note_type: str
    title: str
    body: str = ""
    frontmatter: Dict[str, Any] = {}
    canonical_email: Optional[str] = None
    source: str = "manual"
    confidence: float = 1.0


class VaultNoteUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    frontmatter: Optional[Dict[str, Any]] = None
    pinned: Optional[bool] = None
    status: Optional[str] = None


class VaultNoteResponse(BaseModel):
    id: int
    user_id: str
    slug: str
    note_type: str
    title: str
    frontmatter: Dict[str, Any]
    body: str
    canonical_email: Optional[str] = None
    aliases: List[str] = []
    source: str
    confidence: float
    status: str
    pinned: bool
    created_at: datetime
    updated_at: datetime
    last_referenced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VaultNotesListResponse(BaseModel):
    notes: List[VaultNoteResponse]
    total: int


class VaultProposalResponse(BaseModel):
    id: int
    user_id: str
    target_note_id: Optional[int] = None
    proposal_type: str
    proposed_data: Dict[str, Any]
    diff_summary: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    dedupe_key: Optional[str] = None
    confidence: float
    priority: str
    status: str
    rejection_reason: Optional[str] = None
    rejection_category: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VaultProposalsListResponse(BaseModel):
    proposals: List[VaultProposalResponse]
    total: int


class VaultProposalRejectRequest(BaseModel):
    reason: Optional[str] = None
    category: str = Field(pattern="^(not_relevant|duplicate|inaccurate|too_minor|other)$")


class VaultStatsResponse(BaseModel):
    proposal_acceptance_rate: float = 0.0
    proposals_pending: int = 0
    proposals_stale_count: int = 0
    context_hit_rate: float = 0.0
    total_notes: int = 0
    notes_by_type: Dict[str, int] = {}
    avg_proposals_per_day: float = 0.0
    top_rejection_categories: List[Dict[str, Any]] = []


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


# ========================================
# Notification & Device Token Schemas
# ========================================

class DeviceTokenRegisterRequest(BaseModel):
    """Register an Expo push token for the authenticated user"""
    expo_push_token: str
    device_name: Optional[str] = None
    platform: Optional[str] = None

class DeviceTokenResponse(BaseModel):
    id: int
    expo_push_token: str
    device_name: Optional[str] = None
    platform: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NotificationResponse(BaseModel):
    id: int
    title: str
    body: Optional[str] = None
    category: str
    priority: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
    unread_count: int

class UnreadCountResponse(BaseModel):
    unread_count: int

class MarkReadRequest(BaseModel):
    notification_ids: List[int]


# ========================================
# Telemetry Schemas
# ========================================

class TelemetryEventInput(BaseModel):
    event_id: Optional[str] = None
    event_name: str
    event_payload: Dict[str, Any] = {}
    page_path: Optional[str] = None
    session_id: Optional[str] = None
    client_ts: Optional[datetime] = None


class TelemetryBatchRequest(BaseModel):
    events: List[TelemetryEventInput]


class TelemetryIngestResponse(BaseModel):
    accepted: int
    deduped: int = 0


class TelemetryFunnelResponse(BaseModel):
    chip_clicked: int = 0
    message_sent: int = 0
    action_approved: int = 0
    click_to_send_rate: float = 0.0
    send_to_approve_rate: float = 0.0
    click_to_approve_rate: float = 0.0


class TelemetryDailyCount(BaseModel):
    date: str
    chip_clicked: int = 0
    message_sent: int = 0
    action_approved: int = 0


class TelemetryDashboardResponse(BaseModel):
    days: int
    total_events: int = 0
    event_counts: Dict[str, int] = {}
    funnel: TelemetryFunnelResponse
    daily: List[TelemetryDailyCount] = []


# ========================================
# Focus / Daily Goals Schemas
# ========================================

class GoalItem(BaseModel):
    text: str
    completed: bool = False


class DailyFocusResponse(BaseModel):
    id: Optional[int] = None
    focus_date: str
    goals: List[GoalItem] = []
    frog_task_id: Optional[int] = None
    frog_task: Optional[TaskResponse] = None
    weekly_target: Optional[str] = None
    goals_completed: int = 0
    goals_total: int = 0

    model_config = ConfigDict(from_attributes=True)


class DailyFocusUpdateRequest(BaseModel):
    goals: Optional[List[GoalItem]] = None
    frog_task_id: Optional[int] = None
    weekly_target: Optional[str] = None


class WeeklySummaryResponse(BaseModel):
    week_start: str
    week_end: str
    weekly_target: Optional[str] = None
    days: List[DailyFocusResponse] = []
    total_goals_set: int = 0
    total_goals_completed: int = 0
    tasks_completed_this_week: int = 0




