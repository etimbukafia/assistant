"""
Chat Context Manager

Manages conversation state and context injection for AI Chat.
Integrates with ContextBuilder for memory systems.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.data.models import (
    ChatSession, ChatMessage, Message, Task, CalendarEvent,
    UserSettings, PrincipalMemory
)
from app.intelligence.context_builder import ContextBuilder 


@dataclass
class ConversationState:
    """
    State tracked across a conversation session.
    Stored in ChatSession.state as JSONB.
    """
    session_id: str = ""
    user_id: str = ""
    
    # Entity references (what are we talking about?)
    current_email_id: Optional[int] = None
    current_task_id: Optional[int] = None
    current_contact_id: Optional[int] = None
    current_thread_id: Optional[str] = None
    
    # Workflow (multi-step operations)
    active_workflow: Optional[str] = None  # "draft_reply", "create_task", etc.
    workflow_data: Dict[str, Any] = field(default_factory=dict)
    awaiting_input: Optional[str] = None  # "confirmation", "clarification"
    
    # Pending interactions
    pending_options: List[Dict] = field(default_factory=list)  # for disambiguation
    pending_confirmation: Optional[Dict] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        if not data:
            return cls()
        return cls(
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            current_email_id=data.get("current_email_id"),
            current_task_id=data.get("current_task_id"),
            current_contact_id=data.get("current_contact_id"),
            current_thread_id=data.get("current_thread_id"),
            active_workflow=data.get("active_workflow"),
            workflow_data=data.get("workflow_data", {}),
            awaiting_input=data.get("awaiting_input"),
            pending_options=data.get("pending_options", []),
            pending_confirmation=data.get("pending_confirmation")
        )


class ChatContextManager:
    """
    Manages context for chat sessions.
    
    Responsibilities:
    - Load/save conversation state
    - Build context for LLM prompts
    - Retrieve relevant work context (calendar, tasks, emails)
    - Token budgeting
    """
    
    # Token budget constants
    MAX_CONTEXT_TOKENS = 2000
    MAX_HISTORY_MESSAGES = 10
    CHARS_PER_TOKEN = 4  # Conservative estimate
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.context_builder = ContextBuilder(db, user_id)
    
    def get_session_state(self, session: ChatSession) -> ConversationState:
        """Load ConversationState from session."""
        return ConversationState.from_dict(session.state or {})
    
    def save_session_state(self, session: ChatSession, state: ConversationState):
        """Persist ConversationState to session."""
        session.state = state.to_dict()
        session.last_activity_at = datetime.now(timezone.utc)
        self.db.commit()
    
    def get_recent_messages(
        self, 
        session_id: str, 
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Get recent messages for context window."""
        limit = limit or self.MAX_HISTORY_MESSAGES
        
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(limit).all()
        
        # Reverse to chronological order
        messages = list(reversed(messages))
        
        return [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    
    def get_work_context(self, state: ConversationState) -> Dict[str, Any]:
        """
        Get current work context: calendar, urgent tasks, recent emails.
        Used to ground the AI in the user's current situation.
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        context = {
            "current_time": now.isoformat(),
            "today_calendar": [],
            "urgent_tasks": [],
            "recent_emails_needing_reply": []
        }
        
        # Today's calendar events
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == self.user_id,
            CalendarEvent.start_time >= today_start,
            CalendarEvent.start_time < today_end + timedelta(days=1)
        ).order_by(CalendarEvent.start_time).limit(5).all()
        
        context["today_calendar"] = [
            {
                "title": e.title,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "participants": e.participants or []
            }
            for e in events
        ]
        
        # Urgent/pending tasks
        tasks = self.db.query(Task).filter(
            Task.user_id == self.user_id,
            Task.status.in_(["pending", "in_progress"]),
            Task.priority.in_(["high", "urgent"])
        ).order_by(Task.due_date.asc().nullslast()).limit(5).all()
        
        context["urgent_tasks"] = [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "waiting_for": t.waiting_for_email
            }
            for t in tasks
        ]
        
        # Recent emails needing reply
        emails = self.db.query(Message).filter(
            Message.user_id == self.user_id,
            Message.needs_reply == True,
            Message.is_archived == False
        ).order_by(Message.received_at.desc()).limit(5).all()
        
        context["recent_emails_needing_reply"] = [
            {
                "id": m.id,
                "subject": m.subject,
                "sender": m.sender,
                "received_at": m.received_at.isoformat() if m.received_at else None
            }
            for m in emails
        ]
        
        return context
    
    def get_current_entity_context(self, state: ConversationState) -> Dict[str, Any]:
        """Get details about currently referenced entities."""
        context = {}
        
        if state.current_email_id:
            email = self.db.query(Message).filter(
                Message.id == state.current_email_id,
                Message.user_id == self.user_id  # Security: verify ownership
            ).first()
            if email:
                context["current_email"] = {
                    "id": email.id,
                    "subject": email.subject,
                    "sender": email.sender,
                    "body_preview": (email.decrypted_body or "")[:500],
                    "received_at": email.received_at.isoformat() if email.received_at else None
                }
        
        if state.current_task_id:
            task = self.db.query(Task).filter(
                Task.id == state.current_task_id,
                Task.user_id == self.user_id  # Security: verify ownership
            ).first()
            if task:
                context["current_task"] = {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "due_date": task.due_date.isoformat() if task.due_date else None
                }
        
        return context
    
    def build_prompt_context(
        self,
        session: ChatSession,
        state: ConversationState,
        context_type: str = "drafting"
    ) -> str:
        """
        Build the full context string for LLM prompt injection.
        Integrates memory systems via ContextBuilder.
        """
        parts = []
        
        # 1. Memory context (preferences, patterns)
        memory_context = self.context_builder.build_context(
            context_type=context_type,
            sender_email=None,  # Can be overridden if we have current email
            include_patterns=True
        )
        if memory_context:
            parts.append(f"User preferences: {memory_context}")
        
        # 2. Current entity context
        entity_context = self.get_current_entity_context(state)
        if entity_context.get("current_email"):
            email = entity_context["current_email"]
            parts.append(
                f"Currently discussing email from {email['sender']}: \"{email['subject']}\""
            )
        if entity_context.get("current_task"):
            task = entity_context["current_task"]
            parts.append(
                f"Currently discussing task: \"{task['title']}\" (status: {task['status']})"
            )
        
        # 3. Work context summary (if command mode)
        if session.session_type == "command":
            work_ctx = self.get_work_context(state)
            
            if work_ctx["today_calendar"]:
                event_count = len(work_ctx["today_calendar"])
                parts.append(f"User has {event_count} calendar events today/tomorrow.")
            
            if work_ctx["urgent_tasks"]:
                task_count = len(work_ctx["urgent_tasks"])
                parts.append(f"User has {task_count} urgent/high-priority tasks pending.")
            
            if work_ctx["recent_emails_needing_reply"]:
                email_count = len(work_ctx["recent_emails_needing_reply"])
                parts.append(f"{email_count} emails awaiting reply.")
        
        # 4. Workflow state
        if state.active_workflow:
            parts.append(f"Active workflow: {state.active_workflow}")
            if state.awaiting_input:
                parts.append(f"Awaiting: {state.awaiting_input}")
        
        # Apply token budget
        full_context = " ".join(parts)
        max_chars = self.MAX_CONTEXT_TOKENS * self.CHARS_PER_TOKEN
        
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars - 3] + "..."
        
        return full_context
    
    def update_entity_reference(
        self,
        state: ConversationState,
        email_id: Optional[int] = None,
        task_id: Optional[int] = None,
        thread_id: Optional[str] = None
    ) -> ConversationState:
        """Update which entities we're currently discussing."""
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
        """Start a multi-step workflow."""
        state.active_workflow = workflow_name
        state.workflow_data = initial_data or {}
        return state
    
    def complete_workflow(self, state: ConversationState) -> ConversationState:
        """Complete the current workflow."""
        state.active_workflow = None
        state.workflow_data = {}
        state.awaiting_input = None
        return state
