"""Playground schemas for diary resources."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ContextType(str, Enum):
    decision = "decision"
    commitment = "commitment"
    preferences = "preferences"
    insight = "insight"
    relationships = "relationships"


class EntityType(str, Enum):
    assistant = "assistant"
    contact = "contact"
    thread = "thread"
    message = "message"
    event = "event"
    executive = "executive"


class CreatedBy(str, Enum):
    teeks = "Teeks"
    you = "You"


class ImportanceLevel(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class EntryStatus(str, Enum):
    active = "active"
    resolved = "resolved"
    stale = "stale"
    archived = "archived"


class ContextEntryBase(BaseModel):
    user_id: str
    type: ContextType
    content: str
    entity_type: EntityType
    entity_id: Optional[str] = None
    created_by: CreatedBy
    created_at: datetime
    importance_level: ImportanceLevel = ImportanceLevel.normal
    status: EntryStatus = EntryStatus.active
    expires_at: Optional[datetime] = None


class ContextEntryCreate(BaseModel):
    user_id: str
    type: ContextType
    content: str
    entity_type: EntityType
    entity_id: Optional[str] = None
    created_by: CreatedBy
    importance_level: ImportanceLevel = ImportanceLevel.normal
    status: EntryStatus = EntryStatus.active
    expires_at: Optional[datetime] = None


class ContextEntryUpdate(BaseModel):
    content: Optional[str] = None
    importance_level: Optional[ImportanceLevel] = None
    status: Optional[EntryStatus] = None
    expires_at: Optional[datetime] = None


class ContextEntryResponse(ContextEntryBase):
    id: int

    class Config:
        from_attributes = True


class ContactBase(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    organization: Optional[str] = None
    notes: Optional[str] = None


class ContactResponse(ContactBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EntityReferenceType(str, Enum):
    thread = "thread"
    message = "message"
    event = "event"


class EntityReferenceBase(BaseModel):
    user_id: str
    entity_type: EntityReferenceType
    display_name: str
    ref: str
    notes: Optional[str] = None


class EntityReferenceCreate(EntityReferenceBase):
    pass


class EntityReferenceUpdate(BaseModel):
    display_name: Optional[str] = None
    ref: Optional[str] = None
    notes: Optional[str] = None


class EntityReferenceResponse(EntityReferenceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InboxThreadResponse(BaseModel):
    id: int
    user_id: str
    thread_id: str
    subject: str
    snippet: Optional[str] = None
    last_sender: Optional[str] = None
    last_received_at: datetime
    unread_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InboxMessageResponse(BaseModel):
    id: int
    user_id: str
    message_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: Optional[str] = None
    body_preview: Optional[str] = None
    sent_at: datetime
    direction: str
    needs_reply: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CalendarEventResponse(BaseModel):
    id: int
    user_id: str
    event_id: str
    subject: str
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[str] = None
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
