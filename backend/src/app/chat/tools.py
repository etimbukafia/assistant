"""
Chat Tools Registry

Defines the tools available to the chat AI.
Read-only tools execute immediately.
Approval-gated tools create pending actions for user confirmation.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import (
    Message,
    Task,
    CalendarEvent,
    PrincipalMemory,
    Contact,
    ContextEntry,
    EntityReference,
)
from app.security.tool_validator import validate_tool_args
from app.security.security_logger import log_validation_failure
from app.services.vault import VaultService
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.warm_cache import get_warm_cache_service
from app.services.warm_context_snapshot import (
    build_contact_snapshot,
    build_event_snapshot,
    build_message_snapshot,
    build_profile_snapshot,
    build_thread_snapshot,
)
from app.superpowers.email_drafting import EmailDraftingService
from app.superpowers.meeting_brief import MeetingBriefService

logger = logging.getLogger(__name__)


def escape_like(value: str) -> str:
    """Escape special LIKE characters to prevent SQL LIKE wildcard injection."""
    return value.replace("%", r"\%").replace("_", r"\_")


class ToolType(Enum):
    READ_ONLY = "read_only"  # No HITL required
    APPROVAL_GATED = "approval_gated"  # Creates pending action for user approval
    ACTION = "action"  # Executes immediately (playground-style action tools)


@dataclass
class ToolDefinition:
    """Definition of a chat tool."""
    name: str
    description: str
    tool_type: ToolType
    parameters: Dict[str, Any]  # JSON schema for parameters
    high_risk: bool = False  # Requires extra confirmation UI


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    state_updates: Optional[Dict[str, Any]] = None  # Updates to ConversationState
    pending_action: Optional[Dict[str, Any]] = None  # For approval-gated tools


class ChatToolRegistry:
    """
    Registry of tools available to the chat AI.
    
    Usage:
        registry = ChatToolRegistry(db, user_id)
        
        # Get tool definitions for LLM
        tools = registry.get_tool_definitions()
        
        # Execute a tool
        result = registry.execute_tool("search_emails", {"query": "from:john"})
    """
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self._tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, ToolDefinition]:
        """Register all available tools."""
        return {
            # Read-only tools
            "search_emails": ToolDefinition(
                name="search_emails",
                description="Search user's emails by query. Returns matching email summaries.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (supports from:, subject:, has:reply)"},
                        "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5}
                    },
                    "required": ["query"]
                }
            ),
            "search_tasks": ToolDefinition(
                name="search_tasks",
                description="Search user's tasks. Filter by status, priority, or keyword.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keyword search"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "done", "dismissed"]},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                        "limit": {"type": "integer", "default": 5}
                    }
                }
            ),
            "get_calendar": ToolDefinition(
                name="get_calendar",
                description="Get calendar events for a date range.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "days_ahead": {"type": "integer", "description": "Days to look ahead (default 7)", "default": 7},
                        "include_past": {"type": "boolean", "description": "Include past events today", "default": False}
                    }
                }
            ),
            "get_email_details": ToolDefinition(
                name="get_email_details",
                description="Get full details of a specific email by ID.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "email_id": {"type": "integer", "description": "ID of the email to retrieve"}
                    },
                    "required": ["email_id"]
                }
            ),
            "get_thread_summary": ToolDefinition(
                name="get_thread_summary",
                description="Get a summary of an email thread.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string", "description": "Thread ID to summarize"}
                    },
                    "required": ["thread_id"]
                }
            ),
            "get_contact_context": ToolDefinition(
                name="get_contact_context",
                description="Get relationship history and communication patterns for a contact.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "contact": {"type": "string"},
                        "email": {"type": "string"},
                        "name": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                },
            ),
            "get_thread_history": ToolDefinition(
                name="get_thread_history",
                description="Get thread-level decisions and commitments.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string"},
                        "thread": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                },
            ),
            "get_user_preferences": ToolDefinition(
                name="get_user_preferences",
                description="Get preferences for tone/scheduling/working style.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["tone", "scheduling", "working_hours", "general"], "default": "general"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["category"],
                },
            ),
            "get_event_context": ToolDefinition(
                name="get_event_context",
                description="Get decisions, commitments, and related notes for an event.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "event": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                },
            ),
            "get_message_context": ToolDefinition(
                name="get_message_context",
                description="Get context tied to a specific message.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string"},
                        "message": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                },
            ),
            "search_vault": ToolDefinition(
                name="search_vault",
                description="Search knowledge vault notes by query and optional note type.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "note_type": {"type": "string", "enum": ["person", "project", "meeting", "decision", "commitment"]},
                        "limit": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            ),
            "get_vault_note": ToolDefinition(
                name="get_vault_note",
                description="Get a vault note by slug or ID.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "note_id": {"type": "integer"}
                    }
                }
            ),
            "draft_email": ToolDefinition(
                name="draft_email",
                description="Draft an email using thread/message/contact context.",
                tool_type=ToolType.ACTION,
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "intent": {"type": "string"},
                        "recipient": {"type": "string"},
                        "sender_name": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "message_id": {"type": "string"},
                        "thread": {"type": "string"},
                        "message": {"type": "string"},
                        "context": {"type": "object"},
                    },
                },
            ),
            "generate_meeting_brief": ToolDefinition(
                name="generate_meeting_brief",
                description="Generate a meeting brief by event ID or subject.",
                tool_type=ToolType.ACTION,
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "meeting_subject": {"type": "string"},
                        "participant_ids": {"type": "array", "items": {"type": "string"}},
                        "include_recent_context": {"type": "boolean", "default": True},
                    },
                },
            ),
            
            # Approval-gated tools
            "draft_reply": ToolDefinition(
                name="draft_reply",
                description="Draft a reply to an email. User must approve before sending.",
                tool_type=ToolType.APPROVAL_GATED,
                parameters={
                    "type": "object",
                    "properties": {
                        "email_id": {"type": "integer", "description": "ID of email to reply to"},
                        "tone": {"type": "string", "description": "Desired tone (professional, friendly, formal)"},
                        "key_points": {"type": "array", "items": {"type": "string"}, "description": "Points to include"}
                    },
                    "required": ["email_id"]
                }
            ),
            "create_task": ToolDefinition(
                name="create_task",
                description="Create a new task for the user. User must approve.",
                tool_type=ToolType.APPROVAL_GATED,
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title"},
                        "description": {"type": "string", "description": "Task description"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                        "due_date": {"type": "string", "description": "Due date (ISO format)"}
                    },
                    "required": ["title"]
                }
            ),
            "update_principal_memory": ToolDefinition(
                name="update_principal_memory",
                description="Save a user preference or fact. User must approve.",
                tool_type=ToolType.APPROVAL_GATED,
                parameters={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Preference key (e.g., 'tone', 'sign_off')"},
                        "value": {"type": "string", "description": "Preference value"},
                        "context_type": {"type": "string", "enum": ["drafting", "scheduling", "task_review"]}
                    },
                    "required": ["key", "value", "context_type"]
                }
            ),
            "add_to_calendar": ToolDefinition(
                name="add_to_calendar",
                description="Create a calendar event. User must approve.",
                tool_type=ToolType.APPROVAL_GATED,
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "start_time": {"type": "string", "description": "ISO datetime"},
                        "end_time": {"type": "string", "description": "ISO datetime"},
                        "participants": {"type": "array", "items": {"type": "string"}},
                        "description": {"type": "string"}
                    },
                    "required": ["title", "start_time", "end_time"]
                }
            ),
            "cancel_meeting": ToolDefinition(
                name="cancel_meeting",
                description="Cancel a calendar event. HIGH RISK - requires explicit confirmation.",
                tool_type=ToolType.APPROVAL_GATED,
                high_risk=True,
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "integer", "description": "ID of event to cancel"},
                        "reason": {"type": "string", "description": "Reason for cancellation"},
                        "notify_attendees": {"type": "boolean", "default": True}
                    },
                    "required": ["event_id"]
                }
            ),
            "reschedule_meeting": ToolDefinition(
                name="reschedule_meeting",
                description="Reschedule a calendar event to a new time. User must approve.",
                tool_type=ToolType.APPROVAL_GATED,
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "integer"},
                        "new_start_time": {"type": "string", "description": "New start time (ISO)"},
                        "new_end_time": {"type": "string", "description": "New end time (ISO)"},
                        "reason": {"type": "string"}
                    },
                    "required": ["event_id", "new_start_time", "new_end_time"]
                }
            )
        }
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in self._tools.values()
        ]

    def list_function_declarations(self) -> List[Dict[str, Any]]:
        """Get tool definitions in lightweight function declaration shape."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    def is_action_tool(self, name: str) -> bool:
        tool = self._tools.get((name or "").strip())
        return bool(tool and tool.tool_type == ToolType.ACTION)
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self._tools.get(name)
    
    def execute_tool(self, name: str, parameters: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool with argument validation.

        For read-only tools, executes immediately.
        For approval-gated tools, prepares a pending action.
        """
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        # Validate and sanitize parameters
        validation = validate_tool_args(name, parameters, tool.parameters)
        if not validation.valid:
            # Log validation failures for security monitoring
            for error in validation.errors:
                log_validation_failure(
                    user_id=self.user_id,
                    tool_name=name,
                    field=error.split(":")[0] if ":" in error else "unknown",
                    error=error
                )
            user_safe_error = self._user_safe_validation_error(name)
            return ToolResult(
                success=False,
                error=user_safe_error,
            )

        # Use sanitized arguments
        sanitized_params = validation.sanitized_args

        try:
            # Route to appropriate handler with sanitized params
            handler = getattr(self, f"_execute_{name}", None)
            if handler:
                return handler(sanitized_params)
            else:
                return ToolResult(success=False, error=f"No handler for tool: {name}")
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return ToolResult(success=False, error=self._user_safe_validation_error(name))
    
    # =========================================================================
    # Read-only tool implementations
    # =========================================================================
    
    def _execute_search_emails(self, params: Dict[str, Any]) -> ToolResult:
        """Search emails."""
        query = params.get("query", "")
        limit = min(params.get("limit", 5), 20)  # Cap at 20
        
        # Build query
        db_query = self.db.query(Message).filter(
            Message.user_id == self.user_id
        )

        # Parse simple query syntax
        if "from:" in query:
            from_parts = query.split("from:")[1].split()
            if from_parts:
                sender = from_parts[0]
                safe_sender = escape_like(sender)
                db_query = db_query.filter(Message.sender.ilike(f"%{safe_sender}%", escape="\\"))
                query = query.replace(f"from:{sender}", "").strip()

        if "subject:" in query:
            subject_parts = query.split("subject:")[1].split()
            if subject_parts:
                subject = subject_parts[0]
                safe_subject = escape_like(subject)
                db_query = db_query.filter(Message.subject.ilike(f"%{safe_subject}%", escape="\\"))
                query = query.replace(f"subject:{subject}", "").strip()
        
        # Remaining text is keyword search
        if query.strip():
            safe_query = escape_like(query.strip())
            db_query = db_query.filter(
                Message.subject.ilike(f"%{safe_query}%", escape="\\") |
                Message.body.ilike(f"%{safe_query}%", escape="\\")
            )
        
        emails = db_query.order_by(Message.received_at.desc()).limit(limit).all()
        
        results = [
            {
                "id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "needs_reply": e.needs_reply,
                "preview": (e.decrypted_body or "")[:150]
            }
            for e in emails
        ]
        
        return ToolResult(success=True, data={"emails": results, "count": len(results)})
    
    def _execute_search_tasks(self, params: Dict[str, Any]) -> ToolResult:
        """Search tasks."""
        query = params.get("query", "")
        status = params.get("status")
        priority = params.get("priority")
        limit = params.get("limit", 5)
        
        db_query = self.db.query(Task).filter(Task.user_id == self.user_id)
        
        if status:
            db_query = db_query.filter(Task.status == status)
        if priority:
            db_query = db_query.filter(Task.priority == priority)
        if query:
            safe_query = escape_like(query)
            db_query = db_query.filter(
                Task.title.ilike(f"%{safe_query}%", escape="\\") |
                Task.description.ilike(f"%{safe_query}%", escape="\\")
            )
        
        tasks = db_query.order_by(Task.created_at.desc()).limit(limit).all()
        
        results = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "due_date": (
                    getattr(t, "deadline", None).isoformat()
                    if getattr(t, "deadline", None)
                    else (getattr(t, "due_date", None).isoformat() if getattr(t, "due_date", None) else None)
                ),
            }
            for t in tasks
        ]
        
        return ToolResult(success=True, data={"tasks": results, "count": len(results)})
    
    def _execute_get_calendar(self, params: Dict[str, Any]) -> ToolResult:
        """Get calendar events."""
        days_ahead = params.get("days_ahead", 7)
        include_past = params.get("include_past", False)
        
        now = datetime.now(timezone.utc)
        
        if include_past:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now
        
        end = start + timedelta(days=days_ahead)
        
        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == self.user_id,
            CalendarEvent.start_time >= start,
            CalendarEvent.start_time < end
        ).order_by(CalendarEvent.start_time).limit(20).all()
        
        results = [
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat() if e.start_time else None,
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "participants": e.participants or [],
                "location": e.location
            }
            for e in events
        ]
        
        return ToolResult(success=True, data={"events": results, "count": len(results)})
    
    def _execute_get_email_details(self, params: Dict[str, Any]) -> ToolResult:
        """Get full email details."""
        email_id = params.get("email_id")
        
        email = self.db.query(Message).filter(
            Message.id == email_id,
            Message.user_id == self.user_id
        ).first()
        
        if not email:
            return ToolResult(success=False, error="Email not found")
        
        return ToolResult(
            success=True,
            data={
                "id": email.id,
                "subject": email.subject,
                "sender": email.sender,
                "received_at": email.received_at.isoformat() if email.received_at else None,
                "body": email.decrypted_body or email.body,
                "needs_reply": email.needs_reply,
                "thread_id": email.thread_id
            },
            state_updates={"current_email_id": email.id, "current_thread_id": email.thread_id}
        )
    
    def _execute_get_thread_summary(self, params: Dict[str, Any]) -> ToolResult:
        """Get thread summary."""
        thread_id = params.get("thread_id")
        
        messages = self.db.query(Message).filter(
            Message.thread_id == thread_id,
            Message.user_id == self.user_id
        ).order_by(Message.received_at.asc()).all()
        
        if not messages:
            return ToolResult(success=False, error="Thread not found")
        
        summary = {
            "thread_id": thread_id,
            "message_count": len(messages),
            "participants": list(set(m.sender for m in messages)),
            "subject": messages[0].subject,
            "started_at": messages[0].received_at.isoformat() if messages[0].received_at else None,
            "last_message_at": messages[-1].received_at.isoformat() if messages[-1].received_at else None,
            "messages": [
                {
                    "sender": m.sender,
                    "preview": (m.decrypted_body or "")[:200],
                    "received_at": m.received_at.isoformat() if m.received_at else None
                }
                for m in messages[-5:]  # Last 5 messages
            ]
        }
        
        return ToolResult(
            success=True,
            data=summary,
            state_updates={"current_thread_id": thread_id}
        )

    def _execute_get_contact_context(self, params: Dict[str, Any]) -> ToolResult:
        contact_email = self._resolve_contact_email(
            contact=params.get("contact"),
            email=params.get("email"),
            name=params.get("name"),
        )
        if not contact_email:
            return ToolResult(success=False, error="contact/email/name is required")
        limit = max(1, min(int(params.get("limit", 5)), 10))

        snapshot = self._get_scoped_snapshot(
            scope=f"contact:{contact_email}",
            builder=lambda: build_contact_snapshot(self.db, self.user_id, contact_email),
        )
        entries = list((snapshot.get("by_type", {}) or {}).get("relationships", []))[:limit]
        if not entries:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    ContextEntry.entity_type == "contact",
                    ContextEntry.entity_id == contact_email,
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(limit)
                .all()
            )
            entries = [self._serialize_context_entry(r) for r in rows]

        self._merge_hot(entries)
        return ToolResult(success=True, data={"contact": contact_email, "entries": entries})

    def _execute_get_thread_history(self, params: Dict[str, Any]) -> ToolResult:
        thread_ref = self._resolve_entity_ref("thread", params.get("thread_id") or params.get("thread"))
        if not thread_ref:
            return ToolResult(success=False, error="thread_id/thread is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))

        snapshot = self._get_scoped_snapshot(
            scope=f"thread:{thread_ref}",
            builder=lambda: build_thread_snapshot(self.db, self.user_id, thread_ref),
        )
        by_type = snapshot.get("by_type", {}) or {}
        entries = (by_type.get("decision", []) + by_type.get("commitment", []))[:limit]
        if not entries:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    ContextEntry.entity_type == "thread",
                    ContextEntry.entity_id == thread_ref,
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(limit)
                .all()
            )
            entries = [self._serialize_context_entry(r) for r in rows]

        if not entries:
            thread_messages = (
                self.db.query(Message)
                .filter(
                    Message.user_id == self.user_id,
                    Message.thread_id == thread_ref,
                )
                .order_by(Message.received_at.desc(), Message.created_at.desc())
                .limit(limit)
                .all()
            )
            entries = [
                {
                    "id": f"thread_msg:{msg.id}",
                    "type": "thread_excerpt",
                    "content": f"{(msg.sender or '').strip() or 'Unknown sender'}: {((msg.summary or msg.decrypted_body or msg.subject or '').strip())[:260]}",
                    "entity_type": "thread",
                    "entity_id": thread_ref,
                    "created_by": "Teeks",
                    "created_at": msg.received_at.isoformat() if msg.received_at else None,
                    "importance_level": "normal",
                    "status": msg.status or "inbox",
                }
                for msg in thread_messages
            ]

        self._merge_hot(entries)
        return ToolResult(success=True, data={"thread_id": thread_ref, "entries": entries})

    def _execute_get_user_preferences(self, params: Dict[str, Any]) -> ToolResult:
        category = params.get("category", "general")
        limit = max(1, min(int(params.get("limit", 5)), 10))
        snapshot = self._get_scoped_snapshot(
            scope="profile",
            builder=lambda: build_profile_snapshot(self.db, self.user_id),
        )
        preferences = list((snapshot.get("by_type", {}) or {}).get("preferences", []))[:limit]
        if category and category != "general":
            cat = str(category).lower().strip()
            preferences = [p for p in preferences if self._preference_matches_category(p, cat)]
        self._merge_hot(preferences)
        return ToolResult(success=True, data={"category": category, "entries": preferences})

    def _execute_get_event_context(self, params: Dict[str, Any]) -> ToolResult:
        event_ref = self._resolve_entity_ref("event", params.get("event_id") or params.get("event"))
        if not event_ref:
            return ToolResult(success=False, error="event_id/event is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))
        snapshot = self._get_scoped_snapshot(
            scope=f"event:{event_ref}",
            builder=lambda: build_event_snapshot(self.db, self.user_id, event_ref),
        )
        by_type = snapshot.get("by_type", {}) or {}
        entries = (by_type.get("decision", []) + by_type.get("commitment", []) + by_type.get("risks", []))[:limit]
        if not entries:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    ContextEntry.entity_type == "event",
                    ContextEntry.entity_id == event_ref,
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(limit)
                .all()
            )
            entries = [self._serialize_context_entry(r) for r in rows]
        self._merge_hot(entries)
        return ToolResult(success=True, data={"event_id": event_ref, "entries": entries})

    def _execute_get_message_context(self, params: Dict[str, Any]) -> ToolResult:
        message_ref = self._resolve_entity_ref("message", params.get("message_id") or params.get("message"))
        if not message_ref:
            return ToolResult(success=False, error="message_id/message is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))
        snapshot = self._get_scoped_snapshot(
            scope=f"message:{message_ref}",
            builder=lambda: build_message_snapshot(self.db, self.user_id, message_ref),
        )
        by_type = snapshot.get("by_type", {}) or {}
        entries = (by_type.get("commitment", []) + by_type.get("decision", []) + by_type.get("risks", []))[:limit]
        if not entries:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    ContextEntry.entity_type == "message",
                    ContextEntry.entity_id == message_ref,
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(limit)
                .all()
            )
            entries = [self._serialize_context_entry(r) for r in rows]
        self._merge_hot(entries)
        return ToolResult(success=True, data={"message_id": message_ref, "entries": entries})

    def _execute_draft_email(self, params: Dict[str, Any]) -> ToolResult:
        service = EmailDraftingService(db=self.db, user_id=self.user_id)
        subject = (
            (params.get("subject") or "").strip()
            or (params.get("thread") or "").strip()
            or (params.get("intent") or "").strip()
            or "Follow-up"
        )
        draft = service.draft(
            subject=subject,
            intent=params.get("intent", ""),
            recipient=params.get("recipient"),
            sender_name=params.get("sender_name"),
            thread_id=params.get("thread_id"),
            message_id=params.get("message_id"),
            thread=params.get("thread"),
            message=params.get("message"),
            context=params.get("context"),
        )
        return ToolResult(success=True, data=draft)

    def _user_safe_validation_error(self, tool_name: str) -> str:
        name = (tool_name or "").strip().lower()
        if name == "draft_email":
            return "I couldn't draft that email yet."
        if name == "generate_meeting_brief":
            return "I couldn't prepare that meeting brief yet."
        return "I couldn't complete that action yet."

    def _execute_generate_meeting_brief(self, params: Dict[str, Any]) -> ToolResult:
        service = MeetingBriefService(db=self.db, user_id=self.user_id)
        brief = service.build_brief(
            event_id=params.get("event_id"),
            meeting_subject=params.get("meeting_subject"),
            participant_ids=params.get("participant_ids"),
            include_recent_context=bool(params.get("include_recent_context", True)),
        )
        return ToolResult(success=True, data=brief)

    def _get_scoped_snapshot(self, scope: str, builder) -> Dict[str, Any]:
        warm_cache = get_warm_cache_service()
        return warm_cache.get_or_build(
            tenant_id="default",
            user_id=self.user_id,
            scope=scope,
            builder=builder,
        )

    def _merge_hot(self, entries: List[Dict[str, Any]]) -> None:
        get_hot_context_cache_service().merge_context_entries(
            tenant_id="default",
            user_id=self.user_id,
            session_id="default",
            entries=entries,
        )

    def _resolve_contact_email(
        self,
        contact: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[str]:
        raw = (email or contact or "").strip()
        if raw and "@" in raw:
            email_norm = raw.lower()
            row = (
                self.db.query(Contact)
                .filter(
                    Contact.user_id == self.user_id,
                    func.lower(Contact.email) == email_norm,
                )
                .first()
            )
            return (row.email or "").lower() if row and row.email else email_norm

        candidate_name = (name or contact or "").strip()
        if not candidate_name:
            return None
        row = (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                func.lower(Contact.name) == candidate_name.lower(),
            )
            .first()
        )
        if row and row.email:
            return row.email.lower()
        return None

    def _resolve_entity_ref(self, entity_type: str, identifier: Optional[str]) -> Optional[str]:
        query = (identifier or "").strip()
        if not query:
            return None
        exact = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == entity_type,
                EntityReference.ref == query,
            )
            .first()
        )
        if exact:
            return exact.ref
        by_name = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == entity_type,
                func.lower(EntityReference.display_name) == query.lower(),
            )
            .first()
        )
        if by_name:
            return by_name.ref
        return query

    def _serialize_context_entry(self, row: ContextEntry) -> Dict[str, Any]:
        return {
            "id": row.id,
            "type": row.type,
            "content": row.content,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "importance_level": row.importance_level,
            "status": row.status,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }

    def _preference_matches_category(self, item: Dict[str, Any], category: str) -> bool:
        content = (item.get("content") or "").lower()
        if category == "general":
            return True
        if category == "tone":
            return any(token in content for token in {"tone", "voice", "style", "wording", "framing"})
        if category == "scheduling":
            return any(token in content for token in {"schedule", "meeting", "calendar", "availability", "time slot"})
        if category == "working_hours":
            return any(token in content for token in {"working hours", "hours", "morning", "afternoon", "timezone"})
        return category in content

    def _execute_search_vault(self, params: Dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        note_type = params.get("note_type")
        limit = min(params.get("limit", 5), 20)
        service = VaultService(self.db, self.user_id)
        notes = service.search_notes(query=query, note_type=note_type, limit=limit)
        return ToolResult(
            success=True,
            data={
                "notes": [
                    {
                        "id": n.id,
                        "slug": n.slug,
                        "note_type": n.note_type,
                        "title": n.title,
                        "body_preview": (n.body or "")[:200],
                    }
                    for n in notes
                ],
                "count": len(notes),
            }
        )

    def _execute_get_vault_note(self, params: Dict[str, Any]) -> ToolResult:
        service = VaultService(self.db, self.user_id)
        note = None
        if params.get("note_id"):
            note = service.get_note(params["note_id"])
        elif params.get("slug"):
            note = service.get_note_by_slug(params["slug"])
        if not note:
            return ToolResult(success=False, error="Vault note not found")
        return ToolResult(
            success=True,
            data={
                "id": note.id,
                "slug": note.slug,
                "note_type": note.note_type,
                "title": note.title,
                "frontmatter": note.frontmatter or {},
                "body": note.body or "",
            }
        )

    # =========================================================================
    # Approval-gated tool implementations (create pending actions)
    # =========================================================================
    
    def _execute_draft_reply(self, params: Dict[str, Any]) -> ToolResult:
        """Prepare a draft reply for approval."""
        email_id = params.get("email_id")
        
        email = self.db.query(Message).filter(
            Message.id == email_id,
            Message.user_id == self.user_id
        ).first()
        
        if not email:
            return ToolResult(success=False, error="Email not found")
        
        # This creates a pending action - the actual draft generation
        # happens when approved, using CommunicationModule
        return ToolResult(
            success=True,
            data={"message": "Draft reply prepared for approval"},
            pending_action={
                "action_type": "draft_reply",
                "action_data": {
                    "email_id": email_id,
                    "email_subject": email.subject,
                    "email_sender": email.sender,
                    "tone": params.get("tone", "professional"),
                    "key_points": params.get("key_points", [])
                }
            }
        )
    
    def _execute_create_task(self, params: Dict[str, Any]) -> ToolResult:
        """Prepare task creation for approval."""
        return ToolResult(
            success=True,
            data={"message": "Task prepared for approval"},
            pending_action={
                "action_type": "create_task",
                "action_data": {
                    "title": params.get("title"),
                    "description": params.get("description", ""),
                    "priority": params.get("priority", "medium"),
                    "due_date": params.get("due_date")
                }
            }
        )
    
    def _execute_update_principal_memory(self, params: Dict[str, Any]) -> ToolResult:
        """Prepare preference update for approval."""
        return ToolResult(
            success=True,
            data={"message": "Preference update prepared for approval"},
            pending_action={
                "action_type": "update_principal_memory",
                "action_data": {
                    "key": params.get("key"),
                    "value": params.get("value"),
                    "context_type": params.get("context_type", "drafting")
                }
            }
        )
    
    def _execute_add_to_calendar(self, params: Dict[str, Any]) -> ToolResult:
        """Prepare calendar event for approval."""
        return ToolResult(
            success=True,
            data={"message": "Calendar event prepared for approval"},
            pending_action={
                "action_type": "add_to_calendar",
                "action_data": {
                    "title": params.get("title"),
                    "start_time": params.get("start_time"),
                    "end_time": params.get("end_time"),
                    "participants": params.get("participants", []),
                    "description": params.get("description", "")
                }
            }
        )
    
    def _execute_cancel_meeting(self, params: Dict[str, Any]) -> ToolResult:
        """Prepare meeting cancellation for approval (HIGH RISK)."""
        event_id = params.get("event_id")
        
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()
        
        if not event:
            return ToolResult(success=False, error="Event not found")
        
        return ToolResult(
            success=True,
            data={"message": "Meeting cancellation prepared for approval (HIGH RISK)"},
            pending_action={
                "action_type": "cancel_meeting",
                "action_data": {
                    "event_id": event_id,
                    "event_title": event.title,
                    "start_time": event.start_time.isoformat() if event.start_time else None,
                    "participants": event.participants or [],
                    "reason": params.get("reason", ""),
                    "notify_attendees": params.get("notify_attendees", True)
                }
            }
        )
    
    def _execute_reschedule_meeting(self, params: Dict[str, Any]) -> ToolResult:
        """Prepare meeting reschedule for approval."""
        event_id = params.get("event_id")
        
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()
        
        if not event:
            return ToolResult(success=False, error="Event not found")
        
        return ToolResult(
            success=True,
            data={"message": "Meeting reschedule prepared for approval"},
            pending_action={
                "action_type": "reschedule_meeting",
                "action_data": {
                    "event_id": event_id,
                    "event_title": event.title,
                    "current_start_time": event.start_time.isoformat() if event.start_time else None,
                    "new_start_time": params.get("new_start_time"),
                    "new_end_time": params.get("new_end_time"),
                    "reason": params.get("reason", "")
                }
            }
        )
