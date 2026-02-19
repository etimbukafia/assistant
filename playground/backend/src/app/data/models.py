"""Playground models for diary, inbox, and calendar resources."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, UniqueConstraint, Index, text
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class ContextEntry(Base):
    __tablename__ = "context_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    type = Column(String, nullable=False)
    content = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    importance_level = Column(String, nullable=False, default="normal")
    status = Column(String, nullable=False, default="active")
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('decision','commitment','preferences','insight','relationships')",
            name="ck_context_entries_type",
        ),
        CheckConstraint(
            "entity_type IN ('assistant','contact','thread','message','event','executive')",
            name="ck_context_entries_entity_type",
        ),
        CheckConstraint(
            "created_by IN ('Teeks','You')",
            name="ck_context_entries_created_by",
        ),
        CheckConstraint(
            "importance_level IN ('low','normal','high')",
            name="ck_context_entries_importance_level",
        ),
        CheckConstraint(
            "status IN ('active','resolved','stale','archived')",
            name="ck_context_entries_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            "ContextEntry(id={0.id}, user_id={0.user_id}, type={0.type}, "
            "entity_type={0.entity_type}, entity_id={0.entity_id})"
        ).format(self)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    name = Column(String(collation="NOCASE"), nullable=False)
    email = Column(String(collation="NOCASE"), nullable=True)
    role = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "uq_contacts_user_email",
            "user_id",
            "email",
            unique=True,
            sqlite_where=text("email IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            "Contact(id={0.id}, user_id={0.user_id}, name={0.name}, email={0.email})"
        ).format(self)


class EntityReference(Base):
    __tablename__ = "entity_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    display_name = Column(String(collation="NOCASE"), nullable=False)
    ref = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('thread','message','event')",
            name="ck_entity_references_type",
        ),
        UniqueConstraint("user_id", "entity_type", "display_name", name="uq_entity_refs_user_type_name"),
        UniqueConstraint("user_id", "entity_type", "ref", name="uq_entity_refs_user_type_ref"),
    )

    def __repr__(self) -> str:
        return (
            "EntityReference(id={0.id}, user_id={0.user_id}, type={0.entity_type}, "
            "display_name={0.display_name}, ref={0.ref})"
        ).format(self)


class InboxThread(Base):
    __tablename__ = "inbox_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    snippet = Column(String, nullable=True)
    last_sender = Column(String, nullable=True)
    last_received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    unread_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uq_inbox_threads_user_thread"),
        CheckConstraint("status IN ('open','waiting','closed')", name="ck_inbox_threads_status"),
    )

    def __repr__(self) -> str:
        return (
            "InboxThread(id={0.id}, user_id={0.user_id}, thread_id={0.thread_id}, "
            "subject={0.subject})"
        ).format(self)


class InboxMessage(Base):
    __tablename__ = "inbox_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    message_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    recipients = Column(String, nullable=True)
    body_preview = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    direction = Column(String, nullable=False, default="inbound")
    needs_reply = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_inbox_messages_user_message"),
        CheckConstraint("direction IN ('inbound','outbound','draft')", name="ck_inbox_messages_direction"),
    )

    def __repr__(self) -> str:
        return (
            "InboxMessage(id={0.id}, user_id={0.user_id}, message_id={0.message_id}, "
            "thread_id={0.thread_id})"
        ).format(self)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)
    attendees = Column(String, nullable=True)
    start_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String, nullable=False, default="confirmed")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_calendar_events_user_event"),
        CheckConstraint("status IN ('confirmed','tentative','cancelled')", name="ck_calendar_events_status"),
    )

    def __repr__(self) -> str:
        return (
            "CalendarEvent(id={0.id}, user_id={0.user_id}, event_id={0.event_id}, "
            "subject={0.subject})"
        ).format(self)
