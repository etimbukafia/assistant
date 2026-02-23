"""
Chat Context Manager (Playground Placeholder)

Mirrors production signatures with no-op implementations.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
import logging
from sqlalchemy.orm import Session

from app.data.models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """
    State tracked across a conversation session.
    Stored in ChatSession.state as JSONB.
    """
    session_id: str = ""
    user_id: str = ""

    user_first_name: Optional[str] = None

    current_email_id: Optional[int] = None
    current_task_id: Optional[int] = None
    current_contact_id: Optional[int] = None
    current_thread_id: Optional[str] = None

    active_workflow: Optional[str] = None
    workflow_data: Dict[str, Any] = field(default_factory=dict)
    awaiting_input: Optional[str] = None

    pending_options: List[Dict] = field(default_factory=list)
    pending_confirmation: Optional[Dict] = None
    deferred_actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        if not data:
            return cls()
        return cls(
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            user_first_name=data.get("user_first_name"),
            current_email_id=data.get("current_email_id"),
            current_task_id=data.get("current_task_id"),
            current_contact_id=data.get("current_contact_id"),
            current_thread_id=data.get("current_thread_id"),
            active_workflow=data.get("active_workflow"),
            workflow_data=data.get("workflow_data", {}),
            awaiting_input=data.get("awaiting_input"),
            pending_options=data.get("pending_options", []),
            pending_confirmation=data.get("pending_confirmation"),
            deferred_actions=data.get("deferred_actions", []),
        )


class ChatContextManager:
    """Placeholder for chat context management."""

    MAX_CONTEXT_TOKENS = 3000
    MAX_HISTORY_MESSAGES = 10
    CHARS_PER_TOKEN = 4

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_session_state(self, session: ChatSession) -> ConversationState:
        return ConversationState.from_dict(session.state or {})

    def save_session_state(self, session: ChatSession, state: ConversationState):
        session.state = state.to_dict()
        session.last_activity_at = datetime.now(timezone.utc)

    def get_recent_messages(self, session_id: str, limit: int = None) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit or self.MAX_HISTORY_MESSAGES)
            .all()
        )
        rows = list(reversed(rows))
        return [{"role": row.role, "content": row.content} for row in rows]

    def get_work_context(self, state: ConversationState) -> Dict[str, Any]:
        _ = state
        return {
            "current_time": datetime.now(timezone.utc).isoformat(),
            "today_calendar": [],
            "urgent_tasks": [],
            "recent_emails_needing_reply": [],
        }

    def get_current_entity_context(self, state: ConversationState) -> Dict[str, Any]:
        _ = state
        return {}

    def build_prompt_context(
        self,
        session: ChatSession,
        state: ConversationState,
        context_type: str = "drafting"
    ) -> str:
        _ = (session, state, context_type)
        return "[playground] chat prompt context"

    def update_entity_reference(
        self,
        state: ConversationState,
        email_id: Optional[int] = None,
        task_id: Optional[int] = None,
        thread_id: Optional[str] = None
    ) -> ConversationState:
        if email_id is not None:
            state.current_email_id = email_id
        if task_id is not None:
            state.current_task_id = task_id
        if thread_id is not None:
            state.current_thread_id = thread_id
        return state

    def start_workflow(
        self,
        state: ConversationState,
        workflow_name: str,
        initial_data: Dict[str, Any] = None
    ) -> ConversationState:
        state.active_workflow = workflow_name
        state.workflow_data = initial_data or {}
        return state

    def complete_workflow(self, state: ConversationState) -> ConversationState:
        state.active_workflow = None
        state.workflow_data = {}
        state.awaiting_input = None
        return state
