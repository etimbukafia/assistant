"""
Chat Service

CRUD operations for chat sessions, messages, and pending actions.
Handles session lifecycle including cleanup of expired sessions.

Processing Strategy: Optimistic Sync with Async Fallback
- Reflection mode: Always synchronous (immediate, warm responses)
- Action mode: Try sync first, fallback to async for:
  - Tool calls detected
  - Processing timeout (>8s)
  - High server load
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import uuid
import re
import logging
import time
import os

from sqlalchemy.orm import Session

from app.data.models import (
    ChatSession,
    ChatMessage,
    ChatPendingAction,
    Task,
    PrincipalMemory,
    TaskQueue,
    UserSettings,
    ContactContext,
    Message,
    VaultNote,
    Contact,
    CalendarEvent,
    EntityReference,
    ContextEntry,
)
from app.jobs.queue import queue_service
from .orchestrator import ChatOrchestrator
from .approval_intent import ApprovalIntentKind, PendingActionRef, parse_approval_intent
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.mention_context import MentionContextService
from app.services.warm_cache import get_warm_cache_service
from app.services.entity_cache_coordinator import EntityCacheCoordinator

logger = logging.getLogger(__name__)
cache_coordinator = EntityCacheCoordinator()

# Timeout for synchronous processing (seconds)
SYNC_TIMEOUT_SECONDS = 30.0

# Timeout for async messages stuck in "processing" state (TTL on read)
PROCESSING_TIMEOUT_MINUTES = 2
USER_TIMEOUT_MESSAGE = "I couldn't finish that in time. Please send it again."
USER_RETRY_MESSAGE = "I hit a temporary issue handling that. Please try again."
USER_JOB_NOT_FOUND_MESSAGE = "I couldn't find that request anymore. Please send it again."

# Keep sync-first as default so common tool flows (e.g. draft with @mention)
# do not depend on worker availability.
FORCE_ASYNC_TOOL_INTENT = os.getenv("CHAT_FORCE_ASYNC_TOOL_INTENT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class ProcessingStatus(str, Enum):
    """Chat message processing status."""
    COMPLETE = "complete"
    PROCESSING = "processing"
    FAILED = "failed"


@dataclass
class ChatResponse:
    """Unified response for chat messages."""
    status: ProcessingStatus
    message_id: Optional[int] = None
    job_id: Optional[str] = None
    response: Optional[str] = None
    pending_actions: Optional[List[Dict]] = None
    error: Optional[str] = None
    timing: Optional[Dict[str, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"status": self.status.value}
        if self.message_id:
            result["message_id"] = self.message_id
        if self.job_id:
            result["job_id"] = self.job_id
        if self.response:
            result["response"] = self.response
        if self.pending_actions:
            result["pending_actions"] = self.pending_actions
        if self.error:
            result["error"] = self.error
        return result


# Patterns that suggest tool usage will be needed
TOOL_INTENT_PATTERNS = [
    # Email operations
    r"\b(search|find|look for|show me).*(email|message|mail)",
    r"\b(draft|write|compose|reply).*(email|message|response)",
    r"\bemail.*(from|about|regarding)",

    # Task operations
    r"\b(create|add|make|new).*(task|todo|reminder)",
    r"\b(list|show|what).*(task|todo)",
    r"\bmark.*(done|complete|finished)",

    # Calendar operations
    r"\b(schedule|book|set up).*(meeting|call|appointment)",
    r"\b(calendar|availability|free time)",
    r"\bwhat.*meeting",

    # Memory operations
    r"\bremember.*(that|this|my)",
    r"\bprefer(ence)?",

    # General action keywords
    r"\b(update|change|modify|edit|delete|remove|cancel)",
]

# Compiled patterns for efficiency
_TOOL_INTENT_RE = [re.compile(p, re.IGNORECASE) for p in TOOL_INTENT_PATTERNS]
_EMAIL_DRAFT_RE = re.compile(r"\b(draft|write|compose|reply)\b.*\b(email|message|response)\b", re.IGNORECASE)
_EMAIL_SCOPE_HINT_RE = re.compile(
    r"(@\S+|\bthread\b|\bmessage\b|\breply to\b|\brespond to\b|\babout\b|\bregarding\b|\bfrom\b)",
    re.IGNORECASE,
)


def detect_tool_intent(message: str) -> bool:
    """
    Detect if a message likely requires tool usage.

    Used to decide between sync and async processing paths.
    Returns True if the message appears to need tools.
    """
    text = (message or "").strip()
    if not text:
        return False

    # Generic draft-email requests should stay on the sync path unless scoped.
    # Example (no tools needed): "Draft an email for me. It should say..."
    # Example (tools likely needed): "Draft a reply to @Sarah about @Q3 Budget"
    if _EMAIL_DRAFT_RE.search(text) and not _EMAIL_SCOPE_HINT_RE.search(text):
        return False

    for pattern in _TOOL_INTENT_RE:
        if pattern.search(text):
            return True
    return False 


class ChatService:
    """
    Service layer for chat operations.
    
    Responsibilities:
    - Session CRUD
    - Message management
    - Pending action approval/rejection
    - Session cleanup
    """
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
    
    # =========================================================================
    # Session Operations
    # =========================================================================
    
    def create_session(
        self, 
        session_type: str = "command",
        user_first_name: Optional[str] = None
    ) -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            session_type: 'command' (30 days) or 'reflection' (24 hours)
            user_first_name: User's first name (from JWT) for personalization
        """
        if session_type not in ("command", "reflection"):
            session_type = "command"
        
        # Initialize state with user info for personalization
        initial_state = {}
        if user_first_name:
            initial_state["user_first_name"] = user_first_name
        
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            session_type=session_type,
            title=None,  # Can be set later based on first message
            created_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
            state=initial_state
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID."""
        return self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == self.user_id
        ).first()
    
    def list_sessions(self, limit: int = 20, offset: int = 0) -> Tuple[List[ChatSession], int]:
        """List user's sessions, most recent first. Returns (sessions, total_count)."""
        query = self.db.query(ChatSession).filter(
            ChatSession.user_id == self.user_id
        ).order_by(ChatSession.last_activity_at.desc())

        total = query.count()
        sessions = query.offset(offset).limit(limit).all()
        return sessions, total
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True
    
    def update_session_title(self, session_id: str, title: str) -> Optional[ChatSession]:
        """Update session title."""
        session = self.get_session(session_id)
        if session:
            session.title = title
            self.db.commit()
        return session
    
    # =========================================================================
    # Message Operations
    # =========================================================================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None,
        auto_commit: bool = True,
    ) -> ChatMessage:
        """Add a message to a session."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
            message_metadata=metadata or {}
        )
        
        self.db.add(message)
        
        # Update session activity
        session = self.get_session(session_id)
        if session:
            session.last_activity_at = datetime.now(timezone.utc)

        if auto_commit:
            self.db.commit()
        else:
            # Flush assigns primary keys without paying full commit cost.
            self.db.flush()

        return message

    @staticmethod
    def _sanitize_mention_text(value: Optional[str], max_len: int = 200) -> str:
        if not value:
            return ""
        text = re.sub(r"[\r\n\t]+", " ", str(value))
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len]

    @staticmethod
    def _normalize_mention_lookup(value: Optional[str], max_len: int = 220) -> str:
        text = ChatService._sanitize_mention_text(value, max_len=max_len)
        if not text:
            return ""
        text = text.lstrip("@/").strip()
        # Trim punctuation often carried at end of typed mentions.
        text = text.strip(".,;:!?)]}\"'")
        return text

    def _resolve_mentions(self, mentions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve structured mention tokens into canonical targets."""
        resolved_contacts = []
        resolved_emails = []
        resolved_knowledge = []
        resolved_memory = []
        resolved_entities = []

        for mention in mentions or []:
            mtype = (mention.get("type") or mention.get("kind") or "").strip().lower()
            ref_id = self._normalize_mention_lookup(mention.get("ref_id") or mention.get("ref"))
            label = mention.get("label")
            label_lookup = self._normalize_mention_lookup(label)

            if mtype == "contact":
                email = None
                if "@" in ref_id:
                    email = self._sanitize_mention_text(ref_id.lower(), max_len=254)
                else:
                    contact = None
                    if ref_id:
                        contact = (
                            self.db.query(Contact)
                            .filter(
                                Contact.user_id == self.user_id,
                                (Contact.email == ref_id.lower())
                                | (Contact.name.ilike(ref_id))
                                | (Contact.name.ilike(f"%{ref_id}%")),
                            )
                            .first()
                        )
                    if not contact and label_lookup:
                        contact = (
                            self.db.query(Contact)
                            .filter(
                                Contact.user_id == self.user_id,
                                (Contact.name.ilike(label_lookup)) | (Contact.name.ilike(f"%{label_lookup}%")),
                            )
                            .first()
                        )
                    if contact:
                        email = (contact.email or "").lower()
                    if not email:
                        legacy_contact = None
                        if ref_id:
                            legacy_contact = self.db.query(ContactContext).filter(
                                ContactContext.user_id == self.user_id,
                                (ContactContext.contact_email == ref_id) |
                                (ContactContext.contact_name.ilike(ref_id)) |
                                (ContactContext.contact_name.ilike(f"%{ref_id}%"))
                            ).first()
                        if not legacy_contact and label_lookup:
                            legacy_contact = self.db.query(ContactContext).filter(
                                ContactContext.user_id == self.user_id,
                                (ContactContext.contact_name.ilike(label_lookup)) |
                                (ContactContext.contact_name.ilike(f"%{label_lookup}%"))
                            ).first()
                        if legacy_contact:
                            email = legacy_contact.contact_email
                if email:
                    safe_label = self._sanitize_mention_text(label or email, max_len=180)
                    resolved_contacts.append({"email": email, "label": safe_label or email})
                    resolved_entities.append({"kind": "contact", "ref": email, "label": safe_label or email})

            elif mtype == "email":
                # Prefer stable message id when provided
                msg_id = mention.get("metadata", {}).get("message_id")
                if not msg_id and ref_id.startswith("msg:"):
                    try:
                        msg_id = int(ref_id.split(":", 1)[1])
                    except (TypeError, ValueError):
                        msg_id = None
                msg = None
                if msg_id:
                    msg = self.db.query(Message).filter(
                        Message.id == msg_id,
                        Message.user_id == self.user_id
                    ).first()
                if not msg and ref_id:
                    safe_ref = self._sanitize_mention_text(ref_id, max_len=180)
                    msg = self.db.query(Message).filter(
                        Message.user_id == self.user_id,
                        Message.subject.ilike(f"%{safe_ref}%")
                    ).order_by(Message.received_at.desc()).first()
                if not msg and label_lookup:
                    msg = self.db.query(Message).filter(
                        Message.user_id == self.user_id,
                        Message.subject.ilike(f"%{label_lookup}%")
                    ).order_by(Message.received_at.desc()).first()
                if msg:
                    resolved_emails.append({
                        "message_id": msg.id,
                        "subject": self._sanitize_mention_text(msg.subject, max_len=220),
                        "sender": self._sanitize_mention_text(msg.sender, max_len=220),
                        "thread_id": msg.thread_id,
                    })
                    resolved_entities.append({
                        "kind": "message",
                        "ref": f"msg:{msg.id}",
                        "label": self._sanitize_mention_text(label or msg.subject or str(msg.id), max_len=220),
                    })
            elif mtype == "knowledge":
                note_id = mention.get("metadata", {}).get("note_id")
                note = None
                if note_id:
                    note = self.db.query(VaultNote).filter(
                        VaultNote.id == note_id,
                        VaultNote.user_id == self.user_id,
                        VaultNote.status == "active",
                    ).first()
                if not note and ref_id:
                    note = self.db.query(VaultNote).filter(
                        VaultNote.user_id == self.user_id,
                        VaultNote.status == "active",
                        (
                            VaultNote.slug.ilike(ref_id) |
                            VaultNote.title.ilike(f"%{ref_id}%")
                        )
                    ).order_by(VaultNote.updated_at.desc()).first()
                if note:
                    resolved_knowledge.append({
                        "note_id": note.id,
                        "slug": self._sanitize_mention_text(note.slug, max_len=120),
                        "title": self._sanitize_mention_text(note.title, max_len=220),
                        "note_type": self._sanitize_mention_text(note.note_type, max_len=64),
                    })
            elif mtype == "task":
                task = None
                if ref_id.isdigit():
                    task = self.db.query(Task).filter(
                        Task.user_id == self.user_id,
                        Task.id == int(ref_id)
                    ).first()
                if not task:
                    lookup = self._normalize_mention_lookup(label or ref_id, max_len=220)
                    if lookup:
                        task = self.db.query(Task).filter(
                            Task.user_id == self.user_id,
                            (Task.title.ilike(lookup)) | (Task.title.ilike(f"%{lookup}%"))
                        ).order_by(Task.updated_at.desc()).first()
                if task:
                    task_label = self._sanitize_mention_text(task.title or f"Task {task.id}", max_len=220)
                    resolved_entities.append(
                        {
                            "kind": "task",
                            "ref": str(task.id),
                            "label": task_label,
                        }
                    )
                elif ref_id:
                    resolved_entities.append(
                        {
                            "kind": "task",
                            "ref": self._sanitize_mention_text(ref_id, max_len=220),
                            "label": self._sanitize_mention_text(label or ref_id, max_len=220),
                        }
                    )
            elif mtype in {"thread", "event"}:
                if not ref_id and not label_lookup:
                    continue
                entity = None
                if ref_id:
                    entity = (
                        self.db.query(EntityReference)
                        .filter(
                            EntityReference.user_id == self.user_id,
                            EntityReference.entity_type == mtype,
                            (EntityReference.ref == ref_id)
                            | (EntityReference.display_name.ilike(ref_id))
                            | (EntityReference.display_name.ilike(f"%{ref_id}%"))
                        )
                        .order_by(EntityReference.updated_at.desc())
                        .first()
                    )
                if not entity and label_lookup:
                    entity = (
                        self.db.query(EntityReference)
                        .filter(
                            EntityReference.user_id == self.user_id,
                            EntityReference.entity_type == mtype,
                            (EntityReference.display_name.ilike(label_lookup))
                            | (EntityReference.display_name.ilike(f"%{label_lookup}%"))
                        )
                        .order_by(EntityReference.updated_at.desc())
                        .first()
                    )
                if not entity and mtype == "thread":
                    thread_query = self.db.query(Message).filter(
                        Message.user_id == self.user_id,
                    )
                    if label_lookup:
                        if ref_id:
                            thread_query = thread_query.filter(
                                (Message.thread_id == ref_id)
                                | (Message.subject.ilike(f"%{ref_id}%"))
                                | (Message.subject.ilike(f"%{label_lookup}%"))
                            )
                        else:
                            thread_query = thread_query.filter(
                                Message.subject.ilike(f"%{label_lookup}%")
                            )
                    else:
                        thread_query = thread_query.filter(
                            (Message.thread_id == ref_id)
                            | (Message.subject.ilike(f"%{ref_id}%"))
                        )
                    thread_match = thread_query.order_by(
                        Message.received_at.desc(), Message.created_at.desc()
                    ).first()
                    if thread_match and thread_match.thread_id:
                        entity = EntityReference(
                            user_id=self.user_id,
                            entity_type="thread",
                            ref=thread_match.thread_id,
                            display_name=(thread_match.subject or "").strip() or thread_match.thread_id,
                        )
                if not entity and mtype == "event":
                    event_match = None
                    if ref_id.isdigit():
                        event_match = (
                            self.db.query(CalendarEvent)
                            .filter(
                                CalendarEvent.user_id == self.user_id,
                                CalendarEvent.id == int(ref_id),
                            )
                            .first()
                        )
                    if not event_match:
                        event_lookup = label_lookup or ref_id
                        if event_lookup:
                            event_match = (
                                self.db.query(CalendarEvent)
                                .filter(
                                    CalendarEvent.user_id == self.user_id,
                                    CalendarEvent.title.ilike(f"%{event_lookup}%"),
                                )
                                .order_by(CalendarEvent.updated_at.desc(), CalendarEvent.start_time.asc())
                                .first()
                            )
                    if event_match:
                        entity = EntityReference(
                            user_id=self.user_id,
                            entity_type="event",
                            ref=str(event_match.id),
                            display_name=(event_match.title or "").strip() or str(event_match.id),
                        )
                if entity:
                    resolved_entities.append(
                        {
                            "kind": mtype,
                            "ref": self._sanitize_mention_text(entity.ref, max_len=220),
                            "label": self._sanitize_mention_text(label or entity.display_name or entity.ref, max_len=220),
                        }
                    )
                elif ref_id:
                    resolved_entities.append(
                        {
                            "kind": mtype,
                            "ref": self._sanitize_mention_text(ref_id, max_len=220),
                            "label": self._sanitize_mention_text(label or ref_id, max_len=220),
                        }
                    )
            elif mtype == "memory":
                entry = None
                entry_id = None
                if ref_id.startswith("ctx:"):
                    raw_id = ref_id.split(":", 1)[1]
                    if raw_id.isdigit():
                        entry_id = int(raw_id)
                elif ref_id.isdigit():
                    entry_id = int(ref_id)
                if entry_id:
                    entry = self.db.query(ContextEntry).filter(
                        ContextEntry.id == entry_id,
                        ContextEntry.user_id == self.user_id,
                    ).first()
                if entry:
                    resolved_memory.append(
                        {
                            "id": entry.id,
                            "type": self._sanitize_mention_text(entry.type, max_len=64),
                            "content": self._sanitize_mention_text(entry.content, max_len=500),
                            "entity_type": self._sanitize_mention_text(entry.entity_type, max_len=64),
                            "entity_id": self._sanitize_mention_text(entry.entity_id, max_len=220),
                            "status": self._sanitize_mention_text(getattr(entry, "status", None), max_len=32),
                            "importance_level": self._sanitize_mention_text(entry.importance_level, max_len=32),
                            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                        }
                    )

        return {
            "contacts": resolved_contacts,
            "emails": resolved_emails,
            "knowledge": resolved_knowledge,
            "memory": resolved_memory,
            "entities": resolved_entities,
        }

    def _parse_since_hint(self, content: str) -> Optional[datetime]:
        """
        Parse simple "since" hints in user text to drive recent_changes window.
        Supports:
          - "since YYYY-MM-DD"
          - "since yesterday"
          - "since today"
          - "since last week" / "past week"
          - "since last 7 days" / "past 7 days"
        Returns None when not recognized.
        """
        text = " ".join((content or "").lower().split())
        now = datetime.now(timezone.utc)

        iso_match = re.search(r"since\\s+(\\d{4}-\\d{2}-\\d{2})", text)
        if iso_match:
            try:
                return datetime.fromisoformat(iso_match.group(1)).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        if "since yesterday" in text:
            return now - timedelta(days=1)
        if "since today" in text:
            return datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        if "since last week" in text or "past week" in text:
            return now - timedelta(days=7)
        if re.search(r"since (last|past)\\s+7\\s+days", text):
            return now - timedelta(days=7)

        return None
    
    def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """
        Get messages for a session (with user_id verification).
        
        Also performs TTL-on-read cleanup: auto-expires messages stuck 
        in 'processing' state for longer than PROCESSING_TIMEOUT_MINUTES.
        """
        # Verify session ownership first
        session = self.get_session(session_id)
        if not session:
            return []
        
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()
        
        # TTL-on-read: auto-expire stuck processing messages
        timeout_cutoff = datetime.now(timezone.utc) - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)
        updated_any = False
        
        for msg in messages:
            metadata = msg.message_metadata or {}
            if (metadata.get("status") == "processing" and 
                msg.created_at < timeout_cutoff):
                # Expire this stuck message
                msg.content = USER_TIMEOUT_MESSAGE
                msg.message_metadata = {
                    **metadata,
                    "status": "timeout",
                    "error": USER_TIMEOUT_MESSAGE,
                    "internal_error": "Processing exceeded time limit",
                    "timed_out_at": datetime.now(timezone.utc).isoformat()
                }
                updated_any = True
                logger.warning(f"Auto-expired stuck message {msg.id} (created {msg.created_at})")
        
        if updated_any:
            self.db.commit()
        
        return messages
    
    # =========================================================================
    # Pending Action Operations
    # =========================================================================
    
    def get_pending_actions(self, session_id: str) -> List[ChatPendingAction]:
        """Get pending actions for a session (with user_id verification)."""
        # Verify session ownership first
        session = self.get_session(session_id)
        if not session:
            return []
        
        return self.db.query(ChatPendingAction).filter(
            ChatPendingAction.session_id == session_id,
            ChatPendingAction.status == "pending"
        ).order_by(ChatPendingAction.created_at.asc()).all()
    
    def get_pending_action(self, action_id: str) -> Optional[ChatPendingAction]:
        """Get a specific pending action."""
        action = self.db.query(ChatPendingAction).filter(
            ChatPendingAction.id == action_id
        ).first()
        
        # Verify ownership via session
        if action:
            session = self.get_session(action.session_id)
            if not session:
                return None
        
        return action
    
    def approve_action(self, action_id: str) -> Dict[str, Any]:
        """
        Approve and execute a pending action.
        
        Returns:
            Dict with 'success', 'result', and optionally 'error'
        """
        action = self.get_pending_action(action_id)
        if not action:
            return {"success": False, "error": "Action not found"}
        
        if action.status != "pending":
            return {"success": False, "error": f"Action already {action.status}"}
        
        try:
            result = self._execute_approved_action(action)
            action.status = "approved"
            self.db.commit()
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}")
            action.status = "failed"
            self.db.commit()
            return {"success": False, "error": str(e)}
    
    def reject_action(self, action_id: str) -> Dict[str, Any]:
        """Reject a pending action."""
        action = self.get_pending_action(action_id)
        if not action:
            return {"success": False, "error": "Action not found"}
        
        if action.status != "pending":
            return {"success": False, "error": f"Action already {action.status}"}
        
        action.status = "rejected"
        self.db.commit()
        return {"success": True}
    
    def _execute_approved_action(self, action: ChatPendingAction) -> Dict[str, Any]:
        """Execute an approved action based on its type."""
        action_type = action.action_type
        data = action.action_data
        
        if action_type == "create_task":
            return self._execute_create_task(data)
        elif action_type == "update_principal_memory":
            return self._execute_update_memory(data)
        elif action_type == "draft_reply":
            return self._execute_draft_reply(data)
        elif action_type == "add_to_calendar":
            return self._execute_add_calendar(data)
        elif action_type == "cancel_meeting":
            return self._execute_cancel_meeting(data)
        elif action_type == "reschedule_meeting":
            return self._execute_reschedule_meeting(data)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    def _execute_create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task from approved action."""
        deadline = None
        if data.get("due_date") or data.get("deadline"):
            try:
                deadline_value = data.get("deadline") or data.get("due_date")
                deadline = datetime.fromisoformat(deadline_value.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        task = Task(
            user_id=self.user_id,
            title=data.get("title", "New Task"),
            description=data.get("description", ""),
            priority=data.get("priority", "normal"),
            status="approved",
            task_type=data.get("task_type", "other"),
            task_signal=data.get("task_signal", "explicit"),
            deadline=deadline,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return {"task_id": task.id, "title": task.title}
    
    def _execute_update_memory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update principal memory from approved action."""
        key = data.get("key")
        value = data.get("value")
        context_type = data.get("context_type", "drafting")
        
        # Check if preference already exists
        existing = self.db.query(PrincipalMemory).filter(
            PrincipalMemory.user_id == self.user_id,
            PrincipalMemory.key == key,
            PrincipalMemory.context_type == context_type
        ).first()
        
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            memory = PrincipalMemory(
                user_id=self.user_id,
                key=key,
                value=value,
                context_type=context_type,
                source="chat"
            )
            self.db.add(memory)
        
        self.db.commit()
        return {"key": key, "value": value}
    
    def _execute_draft_reply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate and store a draft reply using CommunicationModule.
        """
        from app.agents.modules.communication import CommunicationModule
        from app.data.models import Message
        
        email_id = data.get("email_id")
        if not email_id:
            return {"success": False, "error": "No email_id provided"}
        
        # Verify email ownership
        email = self.db.query(Message).filter(
            Message.id == email_id,
            Message.user_id == self.user_id
        ).first()
        
        if not email:
            return {"success": False, "error": "Email not found"}
        
        # Use CommunicationModule to generate the draft
        from core.llm.config import LLMConfig
        comm_module = CommunicationModule(llm_config=LLMConfig.for_chat())
        
        result = comm_module.generate_reply(
            message_id=email_id,
            tone=data.get("tone", "professional"),
            intent=data.get("intent"),
            additional_context="\n".join(data.get("key_points", [])),
            db=self.db,
            user_id=self.user_id
        )
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to generate draft")
            }
        
        # Store draft in message metadata or return for frontend display
        return {
            "success": True,
            "email_id": email_id,
            "draft": result.get("draft"),
            "subject_line": result.get("subject_line"),
            "tone_used": result.get("tone_used"),
            "status": "draft_created",
            "note": "Draft ready for review and editing"
        }
    
    def _execute_add_calendar(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create calendar event."""
        from app.data.models import CalendarEvent

        if not data.get("start_time") or not data.get("end_time"):
            raise ValueError("start_time and end_time are required")

        try:
            start_time = datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(data["end_time"].replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid datetime format: {e}")

        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        
        event = CalendarEvent(
            user_id=self.user_id,
            title=data.get("title"),
            description=data.get("description", ""),
            start_time=start_time,
            end_time=end_time,
            participants=data.get("participants", []),
            status="pending",
            provider="local"
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        cache_coordinator.invalidate_event(
            tenant_id="default",
            user_id=self.user_id,
            event_id=str(event.id),
        )
        cache_coordinator.prewarm_action_chips(
            db=self.db,
            tenant_id="default",
            user_id=self.user_id,
        )
        
        return {"event_id": event.id, "title": event.title}
    
    def _execute_cancel_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a calendar event."""
        from app.data.models import CalendarEvent
        
        event_id = data.get("event_id")
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()
        
        if not event:
            raise ValueError("Event not found")
        
        event.status = "cancelled"
        self.db.commit()
        cache_coordinator.invalidate_event(
            tenant_id="default",
            user_id=self.user_id,
            event_id=str(event_id),
        )
        cache_coordinator.prewarm_action_chips(
            db=self.db,
            tenant_id="default",
            user_id=self.user_id,
        )
        
        return {"event_id": event_id, "status": "cancelled"}
    
    def _execute_reschedule_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Reschedule a calendar event."""
        from app.data.models import CalendarEvent
        
        event_id = data.get("event_id")
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()
        
        if not event:
            raise ValueError("Event not found")
        
        if not data.get("new_start_time") or not data.get("new_end_time"):
            raise ValueError("new_start_time and new_end_time are required")

        try:
            new_start = datetime.fromisoformat(data["new_start_time"].replace("Z", "+00:00"))
            new_end = datetime.fromisoformat(data["new_end_time"].replace("Z", "+00:00"))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid datetime format: {e}")

        if new_end <= new_start:
            raise ValueError("new_end_time must be after new_start_time")

        event.start_time = new_start
        event.end_time = new_end
        self.db.commit()
        cache_coordinator.invalidate_event(
            tenant_id="default",
            user_id=self.user_id,
            event_id=str(event_id),
        )
        cache_coordinator.prewarm_action_chips(
            db=self.db,
            tenant_id="default",
            user_id=self.user_id,
        )
        
        return {"event_id": event_id, "new_start_time": data["new_start_time"]}
    
    # =========================================================================
    # Cleanup Operations
    # =========================================================================
    
    def cleanup_expired_sessions(self) -> Dict[str, int]:
        """
        Delete expired sessions based on retention policy.
        
        - Reflection sessions: 24 hours
        - Command sessions: 30 days
        
        Returns:
            Dict with counts of deleted sessions by type
        """
        now = datetime.now(timezone.utc)
        reflection_cutoff = now - timedelta(hours=24)
        command_cutoff = now - timedelta(days=30)
        
        # Delete reflection sessions older than 24 hours
        reflection_deleted = self.db.query(ChatSession).filter(
            ChatSession.session_type == "reflection",
            ChatSession.last_activity_at < reflection_cutoff
        ).delete(synchronize_session=False)
        
        # Delete command sessions older than 30 days
        command_deleted = self.db.query(ChatSession).filter(
            ChatSession.session_type == "command",
            ChatSession.last_activity_at < command_cutoff
        ).delete(synchronize_session=False)
        
        self.db.commit()
        
        return {
            "reflection_deleted": reflection_deleted,
            "command_deleted": command_deleted
        }
    
    # =========================================================================
    # High-level Chat Flow
    # =========================================================================

    async def send_message(
        self,
        session_id: str,
        content: str,
        mentions: Optional[List[Dict[str, Any]]] = None
    ) -> ChatResponse:
        """
        Send a message and get AI response.

        Processing Strategy:
        - Reflection mode: Always synchronous (warm, immediate)
        - Action mode: Optimistic sync with async fallback
          - If tool intent detected → async immediately
          - Otherwise try sync with timeout → fallback to async

        Returns:
            ChatResponse with status, message/job info
        """
        session = self.get_session(session_id)
        if not session:
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error="Session not found"
            )

        approval_response = self._maybe_handle_text_approval(session, content)
        if approval_response is not None:
            return approval_response
        started_at = time.perf_counter()

        mentions = mentions or []
        mentions_started = time.perf_counter()
        resolved_mentions = self._resolve_mentions(mentions)
        mentions_ms = int((time.perf_counter() - mentions_started) * 1000)
        logger.info(
            "chat_mentions_resolved user=%s session=%s mentions_in=%s contacts=%s emails=%s knowledge=%s memory=%s entities=%s",
            self.user_id,
            session_id,
            len(mentions),
            len(resolved_mentions.get("contacts", [])),
            len(resolved_mentions.get("emails", [])),
            len(resolved_mentions.get("knowledge", [])),
            len(resolved_mentions.get("memory", [])),
            len(resolved_mentions.get("entities", [])),
        )
        mention_entities = resolved_mentions.get("entities", [])
        if mention_entities:
            prefetch_started = time.perf_counter()
            since_ts = self._parse_since_hint(content)
            mention_service = MentionContextService(
                db=self.db,
                warm_cache=get_warm_cache_service(),
                tenant_id="default",
                user_id=self.user_id,
                session_id=session_id,
            )
            prefetch = mention_service.prefetch_for_mentions(
                mentions=[
                    {
                        "kind": item.get("kind"),
                        "ref": item.get("ref"),
                        "label": item.get("label"),
                    }
                    for item in mention_entities
                ],
                since_ts=since_ts,
            )
            resolved_mentions["mention_prefetch"] = prefetch
            selected_entries = prefetch.get("selected_entries") or []
            unresolved_mentions = prefetch.get("unresolved_mentions") or []
            if selected_entries:
                get_hot_context_cache_service().merge_context_entries(
                    tenant_id="default",
                    user_id=self.user_id,
                    session_id=session_id,
                    entries=selected_entries,
                )
            logger.info(
                "chat_mentions_prefetch user=%s session=%s selected_entries=%s duration_ms=%s",
                self.user_id,
                session_id,
                len(selected_entries),
                int((time.perf_counter() - prefetch_started) * 1000),
            )
            if unresolved_mentions:
                logger.warning(
                    "chat_mentions_unresolved user=%s session=%s count=%s samples=%s",
                    self.user_id,
                    session_id,
                    len(unresolved_mentions),
                    unresolved_mentions[:3],
                )

        # Save user message
        persist_started = time.perf_counter()
        user_msg = self.add_message(
            session_id,
            "user",
            content,
            metadata={"mentions": mentions, "resolved_mentions": resolved_mentions},
            auto_commit=False,
        )
        get_hot_context_cache_service().append_message(
            tenant_id="default",
            user_id=self.user_id,
            session_id=session_id,
            role="user",
            content=content,
        )
        persist_ms = int((time.perf_counter() - persist_started) * 1000)

        # Auto-generate title from first message if not set
        if not session.title:
            # Clean up the content for title: remove newlines, extra spaces
            clean_content = " ".join(content.split())
            session.title = clean_content[:50] + ("..." if len(clean_content) > 50 else "")

        # REFLECTION MODE: Always synchronous
        if session.session_type == "reflection":
            process_started = time.perf_counter()
            result = await self._process_sync(session, content, user_msg.id, mention_context=resolved_mentions)
            timing = result.timing or {}
            logger.info(
                "chat_send_timing user=%s session=%s mode=reflection mentions_ms=%s persist_ms=%s process_ms=%s assemble_ms=%s prompt_ms=%s llm_ms=%s orch_ms=%s sync_persist_ms=%s total_ms=%s",
                self.user_id,
                session_id,
                mentions_ms,
                persist_ms,
                int((time.perf_counter() - process_started) * 1000),
                int(timing.get("context_assembly_ms", 0) or 0),
                int(timing.get("llm_prompt_ms", 0) or 0),
                int(timing.get("llm_ms", 0) or 0),
                int(timing.get("orchestration_ms", 0) or 0),
                int(timing.get("sync_persist_ms", 0) or 0),
                int((time.perf_counter() - started_at) * 1000),
            )
            return result

        # ACTION MODE: Sync-first with timeout fallback.
        # Optional legacy behavior can force intent-heavy turns async.
        if FORCE_ASYNC_TOOL_INTENT and detect_tool_intent(content):
            logger.info(
                "Tool intent detected and CHAT_FORCE_ASYNC_TOOL_INTENT enabled; using async path for session %s",
                session_id,
            )
            result = self._enqueue_async(
                session,
                content,
                user_msg.id,
                mentions=mentions,
                mention_context=resolved_mentions,
            )
            logger.info(
                "chat_send_timing user=%s session=%s mode=action path=async_intent mentions_ms=%s persist_ms=%s total_ms=%s",
                self.user_id,
                session_id,
                mentions_ms,
                persist_ms,
                int((time.perf_counter() - started_at) * 1000),
            )
            return result

        # Try synchronous processing with timeout
        process_started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                self._process_sync(session, content, user_msg.id, mention_context=resolved_mentions),
                timeout=SYNC_TIMEOUT_SECONDS
            )
            timing = result.timing or {}
            logger.info(
                "chat_send_timing user=%s session=%s mode=action path=sync mentions_ms=%s persist_ms=%s process_ms=%s assemble_ms=%s prompt_ms=%s llm_ms=%s orch_ms=%s sync_persist_ms=%s total_ms=%s",
                self.user_id,
                session_id,
                mentions_ms,
                persist_ms,
                int((time.perf_counter() - process_started) * 1000),
                int(timing.get("context_assembly_ms", 0) or 0),
                int(timing.get("llm_prompt_ms", 0) or 0),
                int(timing.get("llm_ms", 0) or 0),
                int(timing.get("orchestration_ms", 0) or 0),
                int(timing.get("sync_persist_ms", 0) or 0),
                int((time.perf_counter() - started_at) * 1000),
            )
            return result
        except asyncio.TimeoutError:
            logger.info(f"Sync timeout, falling back to async for session {session_id}")
            result = self._enqueue_async(
                session,
                content,
                user_msg.id,
                mentions=mentions,
                mention_context=resolved_mentions,
            )
            logger.info(
                "chat_send_timing user=%s session=%s mode=action path=sync_timeout_async mentions_ms=%s persist_ms=%s process_ms=%s total_ms=%s",
                self.user_id,
                session_id,
                mentions_ms,
                persist_ms,
                int((time.perf_counter() - process_started) * 1000),
                int((time.perf_counter() - started_at) * 1000),
            )
            return result

    def _maybe_handle_text_approval(
        self,
        session: ChatSession,
        content: str,
    ) -> Optional[ChatResponse]:
        """
        Handle pending-action approvals via user text instruction.

        Returns ChatResponse when handled; otherwise None.
        """
        pending = self.get_pending_actions(session.id)
        if not pending:
            return None

        refs = [
            PendingActionRef(id=item.id, index=idx + 1, action_type=item.action_type)
            for idx, item in enumerate(pending)
        ]
        intent = parse_approval_intent(content, refs)
        if intent.kind == ApprovalIntentKind.NONE:
            return None

        user_msg = self.add_message(
            session.id,
            "user",
            content,
            metadata={"approval_intent": intent.kind.value, "approval_reason": intent.reason},
            auto_commit=False,
        )
        get_hot_context_cache_service().append_message(
            tenant_id="default",
            user_id=self.user_id,
            session_id=session.id,
            role="user",
            content=content,
        )

        if intent.kind == ApprovalIntentKind.AMBIGUOUS:
            assistant_text = (
                "I found pending actions. Tell me what to run: "
                "\"approve all\", \"run 1 and 3\", \"skip 2\", or \"cancel\"."
            )
            assistant_msg = self.add_message(
                session.id,
                "assistant",
                assistant_text,
                metadata={"approval_status": "clarification_requested"},
                auto_commit=False,
            )
            get_hot_context_cache_service().append_message(
                tenant_id="default",
                user_id=self.user_id,
                session_id=session.id,
                role="assistant",
                content=assistant_text,
            )
            self.db.commit()
            return ChatResponse(
                status=ProcessingStatus.COMPLETE,
                message_id=assistant_msg.id,
                response=assistant_text,
                pending_actions=self._serialize_pending_actions(self.get_pending_actions(session.id)),
            )

        approve_ids = set(intent.approve_ids)
        reject_ids = set(intent.reject_ids)
        if intent.kind == ApprovalIntentKind.APPROVE_ALL:
            approve_ids = {item.id for item in pending}
        if intent.kind == ApprovalIntentKind.CANCEL_ALL:
            reject_ids = {item.id for item in pending}

        approved_labels: List[str] = []
        rejected_labels: List[str] = []
        failed_labels: List[str] = []

        for action in pending:
            label = self._pending_action_label(action)
            if action.id in reject_ids:
                result = self.reject_action(action.id)
                if result.get("success"):
                    rejected_labels.append(label)
                else:
                    failed_labels.append(label)
                continue
            if action.id in approve_ids:
                result = self.approve_action(action.id)
                if result.get("success"):
                    approved_labels.append(label)
                else:
                    failed_labels.append(label)

        remaining_pending = self.get_pending_actions(session.id)

        clauses: List[str] = []
        if approved_labels:
            done = ", ".join([f"\"{item}\"" for item in approved_labels])
            clauses.append(f"I've completed {done}.")
        if rejected_labels:
            skipped = ", ".join([f"\"{item}\"" for item in rejected_labels])
            clauses.append(f"I've skipped {skipped}.")
        if failed_labels:
            failed = ", ".join([f"\"{item}\"" for item in failed_labels])
            clauses.append(f"I couldn't finish {failed} yet.")
        if remaining_pending:
            remaining = ", ".join([f"\"{self._pending_action_label(item)}\"" for item in remaining_pending[:5]])
            clauses.append(f"I still have {remaining} pending. Tell me to proceed when ready.")
        if not clauses:
            clauses.append("No pending actions were changed.")

        assistant_text = " ".join(clauses)
        assistant_msg = self.add_message(
            session.id,
            "assistant",
            assistant_text,
            metadata={
                "approval_status": "applied",
                "approval_intent": intent.kind.value,
                "approved_count": len(approved_labels),
                "rejected_count": len(rejected_labels),
                "failed_count": len(failed_labels),
            },
            auto_commit=False,
        )
        get_hot_context_cache_service().append_message(
            tenant_id="default",
            user_id=self.user_id,
            session_id=session.id,
            role="assistant",
            content=assistant_text,
        )

        self.db.commit()
        logger.info(
            "chat_text_approval_applied user=%s session=%s intent=%s approved=%s rejected=%s failed=%s remaining=%s",
            self.user_id,
            session.id,
            intent.kind.value,
            len(approved_labels),
            len(rejected_labels),
            len(failed_labels),
            len(remaining_pending),
        )
        return ChatResponse(
            status=ProcessingStatus.COMPLETE,
            message_id=assistant_msg.id,
            response=assistant_text,
            pending_actions=self._serialize_pending_actions(remaining_pending),
        )

    @staticmethod
    def _pending_action_label(action: ChatPendingAction) -> str:
        data = action.action_data or {}
        action_type = (action.action_type or "action").replace("_", " ").strip()
        title = (data.get("title") or data.get("subject") or "").strip()
        if title:
            return f"{action_type}: {title}"
        return action_type

    @staticmethod
    def _serialize_pending_actions(actions: List[ChatPendingAction]) -> List[Dict[str, Any]]:
        return [
            {
                "id": action.id,
                "action_type": action.action_type,
                "action_data": action.action_data,
                "status": action.status,
                "message_id": action.message_id,
            }
            for action in actions
        ]

    async def _process_sync(
        self,
        session: ChatSession,
        content: str,
        user_message_id: int,
        mention_context: Optional[Dict[str, Any]] = None,
    ) -> ChatResponse:
        """
        Process message synchronously.

        Used for:
        - All reflection mode messages
        - Action mode messages that don't need tools
        """
        try:
            sync_started = time.perf_counter()
            # Get user's assistant name preference
            settings_started = time.perf_counter()
            user_settings = self.db.query(UserSettings).filter(
                UserSettings.user_id == self.user_id
            ).first()
            assistant_name = user_settings.assistant_name if user_settings else "Teeks"
            settings_ms = int((time.perf_counter() - settings_started) * 1000)

            # Get user's first name from session state
            session_state = session.state or {}
            user_name = session_state.get("user_first_name")

            orchestrator = ChatOrchestrator(
                self.db, self.user_id,
                assistant_name=assistant_name,
                user_name=user_name,
            )
            orchestration_started = time.perf_counter()
            result = await orchestrator.process_message(
                session,
                content,
                mention_context=mention_context or {},
            )
            orchestration_ms = int((time.perf_counter() - orchestration_started) * 1000)
            orchestrator_timing = result.get("timing", {}) or {}

            # Save assistant response
            write_started = time.perf_counter()
            assistant_msg = self.add_message(
                session.id,
                "assistant",
                result.get("response", ""),
                metadata={"state": result.get("state", {})},
                auto_commit=False,
            )
            get_hot_context_cache_service().append_message(
                tenant_id="default",
                user_id=self.user_id,
                session_id=session.id,
                role="assistant",
                content=assistant_msg.content,
            )
            write_ms = int((time.perf_counter() - write_started) * 1000)

            # Create pending actions
            pending_started = time.perf_counter()
            pending_actions = []
            for pa_data in result.get("pending_actions", []):
                pa = ChatPendingAction(
                    id=str(uuid.uuid4()),
                    session_id=session.id,
                    message_id=assistant_msg.id,
                    action_type=pa_data["action_type"],
                    action_data=pa_data["action_data"],
                    status="pending",
                    created_at=datetime.now(timezone.utc)
                )
                self.db.add(pa)
                pending_actions.append({
                    "id": pa.id,
                    "action_type": pa.action_type,
                    "action_data": pa.action_data,
                    "status": pa.status,
                    "message_id": pa.message_id
                })
            pending_ms = int((time.perf_counter() - pending_started) * 1000)

            commit_started = time.perf_counter()
            self.db.commit()
            commit_ms = int((time.perf_counter() - commit_started) * 1000)
            sync_persist_ms = write_ms + pending_ms + commit_ms
            total_sync_ms = int((time.perf_counter() - sync_started) * 1000)

            logger.info(
                "chat_sync_stage_timing user=%s session=%s settings_ms=%s orchestrator_ms=%s assemble_ms=%s prompt_ms=%s llm_ms=%s llm_calls=%s write_ms=%s pending_ms=%s commit_ms=%s total_sync_ms=%s",
                self.user_id,
                session.id,
                settings_ms,
                orchestration_ms,
                int(orchestrator_timing.get("context_assembly_ms", 0) or 0),
                int(orchestrator_timing.get("llm_prompt_ms", 0) or 0),
                int(orchestrator_timing.get("llm_ms", 0) or 0),
                int(orchestrator_timing.get("llm_calls", 0) or 0),
                write_ms,
                pending_ms,
                commit_ms,
                total_sync_ms,
            )

            return ChatResponse(
                status=ProcessingStatus.COMPLETE,
                message_id=assistant_msg.id,
                response=assistant_msg.content,
                pending_actions=pending_actions if pending_actions else None,
                timing={
                    "settings_ms": settings_ms,
                    "orchestration_ms": orchestration_ms,
                    "context_assembly_ms": int(orchestrator_timing.get("context_assembly_ms", 0) or 0),
                    "llm_prompt_ms": int(orchestrator_timing.get("llm_prompt_ms", 0) or 0),
                    "llm_ms": int(orchestrator_timing.get("llm_ms", 0) or 0),
                    "llm_calls": int(orchestrator_timing.get("llm_calls", 0) or 0),
                    "write_ms": write_ms,
                    "pending_ms": pending_ms,
                    "commit_ms": commit_ms,
                    "sync_persist_ms": sync_persist_ms,
                    "sync_total_ms": total_sync_ms,
                },
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                "chat_sync_processing_failed user=%s session=%s",
                self.user_id,
                session.id,
                exc_info=True,
            )
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error=USER_RETRY_MESSAGE
            )

    def _enqueue_async(
        self,
        session: ChatSession,
        content: str,
        user_message_id: int,
        mentions: Optional[List[Dict[str, Any]]] = None,
        mention_context: Optional[Dict[str, Any]] = None,
    ) -> ChatResponse:
        """
        Enqueue message for async processing.

        Creates a job in TaskQueue and returns job_id for polling.
        """
        job_id = str(uuid.uuid4())

        # Add placeholder assistant message with job tracking
        placeholder_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content="",  # Empty content, will be filled by worker
            created_at=datetime.now(timezone.utc),
            message_metadata={"job_id": job_id, "status": "processing"}
        )
        self.db.add(placeholder_msg)

        # Update session activity
        session.last_activity_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(placeholder_msg)

        # Enqueue the job
        queue_service.enqueue(
            task_type="process_chat_message",
            payload={
                "job_id": job_id,
                "session_id": session.id,
                "user_id": self.user_id,
                "content": content,
                "user_message_id": user_message_id,
                "assistant_message_id": placeholder_msg.id,
                "mentions": mentions or [],
                "mention_context": mention_context or {},
            },
            db=self.db
        )

        logger.info(f"Enqueued chat job {job_id} for session {session.id}")

        return ChatResponse(
            status=ProcessingStatus.PROCESSING,
            job_id=job_id,
            message_id=placeholder_msg.id
        )

    def get_job_status(self, job_id: str) -> ChatResponse:
        """
        Check the status of an async chat job.

        Returns:
            ChatResponse with current status and response if complete
        """
        # Find the message with this job_id
        # Filter by assistant role and recent creation to avoid scanning all messages.
        # Then match job_id in Python for SQLite compatibility (no JSON queries).
        timeout_window = datetime.now(timezone.utc) - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES * 5)
        recent_messages = self.db.query(ChatMessage).join(
            ChatSession, ChatMessage.session_id == ChatSession.id
        ).filter(
            ChatSession.user_id == self.user_id,
            ChatMessage.role == "assistant",
            ChatMessage.created_at >= timeout_window
        ).order_by(ChatMessage.created_at.desc()).limit(50).all()

        # Find message with matching job_id in metadata
        message = None
        for msg in recent_messages:
            metadata = msg.message_metadata or {}
            if metadata.get("job_id") == job_id:
                message = msg
                break

        if not message:
            logger.warning(
                "chat_job_not_found user=%s job_id=%s",
                self.user_id,
                job_id,
            )
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error=USER_JOB_NOT_FOUND_MESSAGE
            )

        metadata = message.message_metadata or {}

        # Check if still processing
        if metadata.get("status") == "processing":
            # TTL check: auto-expire if stuck too long
            timeout_cutoff = datetime.now(timezone.utc) - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)
            if message.created_at < timeout_cutoff:
                # Expire this stuck message
                message.content = USER_TIMEOUT_MESSAGE
                message.message_metadata = {
                    **metadata,
                    "status": "timeout",
                    "error": USER_TIMEOUT_MESSAGE,
                    "internal_error": "Processing exceeded time limit",
                    "timed_out_at": datetime.now(timezone.utc).isoformat()
                }
                self.db.commit()
                logger.warning(
                    "chat_job_timeout user=%s session=%s job_id=%s message_id=%s",
                    self.user_id,
                    message.session_id,
                    job_id,
                    message.id,
                )
                
                return ChatResponse(
                    status=ProcessingStatus.FAILED,
                    job_id=job_id,
                    message_id=message.id,
                    error=USER_TIMEOUT_MESSAGE
                )
            
            return ChatResponse(
                status=ProcessingStatus.PROCESSING,
                job_id=job_id,
                message_id=message.id
            )

        # Check if timed out (already expired by another path)
        if metadata.get("status") == "timeout":
            logger.warning(
                "chat_job_timeout_reported user=%s session=%s job_id=%s message_id=%s error=%s",
                self.user_id,
                message.session_id,
                job_id,
                message.id,
                metadata.get("error", "Processing timed out"),
            )
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                job_id=job_id,
                message_id=message.id,
                error=metadata.get("error", USER_TIMEOUT_MESSAGE)
            )

        # Check if failed
        if metadata.get("status") == "failed":
            logger.error(
                "chat_job_failed user=%s session=%s job_id=%s message_id=%s user_error=%s internal_error=%s",
                self.user_id,
                message.session_id,
                job_id,
                message.id,
                metadata.get("error", "Processing failed"),
                metadata.get("internal_error"),
            )
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                job_id=job_id,
                error=metadata.get("error", USER_RETRY_MESSAGE)
            )

        # Complete - return the response
        pending_actions = self.get_pending_actions_for_message(message.id)

        return ChatResponse(
            status=ProcessingStatus.COMPLETE,
            message_id=message.id,
            response=message.content,
            pending_actions=[
                {
                    "id": pa.id,
                    "action_type": pa.action_type,
                    "action_data": pa.action_data,
                    "status": pa.status,
                    "message_id": pa.message_id
                }
                for pa in pending_actions
            ] if pending_actions else None
        )

    def get_pending_actions_for_message(self, message_id: int) -> List[ChatPendingAction]:
        """Get pending actions for a specific message."""
        return self.db.query(ChatPendingAction).filter(
            ChatPendingAction.message_id == message_id,
            ChatPendingAction.status == "pending"
        ).all()

    # =========================================================================
    # Legacy method for backwards compatibility
    # =========================================================================

    async def send_message_legacy(
        self,
        session_id: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Legacy send_message method for backwards compatibility.

        Returns dict format expected by older clients.
        """
        response = await self.send_message(session_id, content)

        if response.status == ProcessingStatus.FAILED:
            return {"success": False, "error": response.error}

        if response.status == ProcessingStatus.PROCESSING:
            return {
                "success": True,
                "status": "processing",
                "job_id": response.job_id,
                "message_id": response.message_id
            }

        # Complete
        session = self.get_session(session_id)
        user_msg = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user"
        ).order_by(ChatMessage.created_at.desc()).first()

        assistant_msg = self.db.query(ChatMessage).get(response.message_id)

        return {
            "success": True,
            "user_message": {
                "id": user_msg.id if user_msg else None,
                "role": "user",
                "content": content,
                "created_at": user_msg.created_at.isoformat() if user_msg else None
            },
            "assistant_message": {
                "id": response.message_id,
                "role": "assistant",
                "content": response.response,
                "created_at": assistant_msg.created_at.isoformat() if assistant_msg else None
            },
            "pending_actions": response.pending_actions or []
        }
