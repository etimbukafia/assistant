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
import json
import logging
import re

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
    ThreadState,
    ChatSession,
    ChatPendingAction,
    VaultProposal,
)

MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX = "__manual_tasks__"
MANUAL_TASK_PLACEHOLDER_MESSAGE_PREFIX = "__manual_tasks_placeholder__"
from app.security.tool_validator import validate_tool_args
from app.security.prompt_sanitizer import sanitize_with_detection
from app.security.security_logger import log_validation_failure
from app.services.vault import VaultService
from app.services.contact_brief import ContactBriefService
from app.services.contact_signals import ContactSignalsService
from app.services.contact_timeline import ContactTimelineService
from app.services.context_memory_policy import (
    apply_confidence_retrieval_filter,
    apply_historical_expiry_retrieval_filter,
    is_expiry_retrievable,
)
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.warm_cache import get_warm_cache_service
from app.services.warm_context_snapshot import (
    build_contact_snapshot,
    build_event_snapshot,
    build_message_snapshot,
    build_profile_snapshot,
    build_thread_snapshot,
)
from app.superpowers.email_drafting import DraftGenerationError, EmailDraftingService
from app.superpowers.meeting_brief import MeetingBriefService

logger = logging.getLogger(__name__)

HIDDEN_TOOLS = {
    "get_contact_context",
    "get_thread_history",
    "get_user_preferences",
    "get_event_context",
    "get_message_context",
    "get_task_context",
}

APPROVAL_QUERY_STOPWORDS = {
    "a",
    "about",
    "an",
    "any",
    "approve",
    "approved",
    "approval",
    "did",
    "do",
    "have",
    "is",
    "last",
    "me",
    "pending",
    "show",
    "status",
    "tell",
    "that",
    "the",
    "this",
    "we",
    "what",
    "when",
    "who",
    "with",
}


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
                description=(
                    "Search user's tasks. Filter by status, priority, or keyword. "
                    "Includes source email linkage metadata when available."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keyword search"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "done", "dismissed"]},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                        "limit": {"type": "integer", "default": 5},
                        "include_source_email": {"type": "boolean", "default": True},
                        "include_source_body": {
                            "type": "boolean",
                            "default": False,
                            "description": "Only for exact-wording requests; includes full source email body when available.",
                        },
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
                description="(Deprecated) Get relationship history and communication patterns for a contact. Prefer get_contact_brief.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer"},
                        "contact": {"type": "string"},
                        "email": {"type": "string"},
                        "name": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                        "include_non_active": {"type": "boolean", "default": False},
                    },
                },
            ),
            "get_contact_brief": ToolDefinition(
                name="get_contact_brief",
                description=(
                    "Get the active relationship brief for a contact, including summary, preferences, "
                    "open commitments, decisions, recent interactions, and signals."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer"},
                        "contact": {"type": "string"},
                        "email": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
            ),
            "get_contact_timeline": ToolDefinition(
                name="get_contact_timeline",
                description=(
                    "Get a chronological relationship timeline for a contact, combining recent interactions, "
                    "decisions, commitments, and upcoming meetings."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer"},
                        "contact": {"type": "string"},
                        "email": {"type": "string"},
                        "name": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                },
            ),
            "get_contact_signals": ToolDefinition(
                name="get_contact_signals",
                description=(
                    "Get deterministic relationship signals for a contact, such as stale follow-up, open commitments, "
                    "and upcoming meetings."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "integer"},
                        "contact": {"type": "string"},
                        "email": {"type": "string"},
                        "name": {"type": "string"},
                    },
                },
            ),
            "get_thread_history": ToolDefinition(
                name="get_thread_history",
                description="(Deprecated) Get thread-level decisions and commitments. Prefer context_search.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string"},
                        "thread": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                        "include_non_active": {"type": "boolean", "default": False},
                    },
                },
            ),
            "get_user_preferences": ToolDefinition(
                name="get_user_preferences",
                description="(Deprecated) Get preferences for tone/scheduling/working style. Prefer context_search.",
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
                description="(Deprecated) Get decisions, commitments, and related notes for an event. Prefer context_search.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "event": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                        "include_non_active": {"type": "boolean", "default": False},
                    },
                },
            ),
            "get_message_context": ToolDefinition(
                name="get_message_context",
                description="(Deprecated) Get context tied to a specific message. Prefer context_search.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string"},
                        "message": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                        "include_non_active": {"type": "boolean", "default": False},
                    },
                },
            ),
            "get_task_context": ToolDefinition(
                name="get_task_context",
                description="(Deprecated) Get context for a task (pending_approval or approved). Prefer context_search.",
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "task": {"type": "string"},
                        "limit": {"type": "integer", "default": 8},
                    },
                },
            ),
            "context_search": ToolDefinition(
                name="context_search",
                description=(
                    "Unified search over context entries (decisions, commitments, preferences, insights, risks) "
                    "for memory retrieval. Use filters instead of raw SQL."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keyword search across content/title"},
                        "entity_type": {
                            "type": "string",
                            "enum": ["contact", "thread", "event", "message", "task", "global", "executive"],
                        },
                        "entity_id": {"type": "string", "description": "Entity reference id"},
                        "types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["decision", "commitment", "preference", "risk", "insight"],
                            },
                        },
                        "status": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["active", "resolved", "dismissed", "archived", "stale"]},
                        },
                        "since": {"type": "string", "description": "ISO datetime; created after this"},
                        "until": {"type": "string", "description": "ISO datetime; created before this"},
                        "limit": {"type": "integer", "default": 10},
                        "include_non_active": {"type": "boolean", "default": False},
                    },
                },
            ),
            "entity_search": ToolDefinition(
                name="entity_search",
                description=(
                    "Unified entity search for contacts, threads, events, messages, and tasks. "
                    "Requires explicit entity_types filter. For task results, source email linkage metadata is included when available."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search string"},
                        "entity_types": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["contact", "thread", "event", "message", "task"]},
                        },
                        "limit": {"type": "integer", "default": 20},
                        "offset": {"type": "integer", "default": 0},
                        "recent_first": {"type": "boolean", "default": True},
                        "include_archived": {"type": "boolean", "default": False},
                        "include_source_body": {
                            "type": "boolean",
                            "default": False,
                            "description": "When true and entity_types includes task, include full source email body if available.",
                        },
                    },
                    "required": ["entity_types"],
                },
            ),
            "get_approval_history": ToolDefinition(
                name="get_approval_history",
                description=(
                    "Deterministically retrieve approval status/history across tasks, chat pending actions, "
                    "and vault proposals. Use for questions like did we approve X, was this approved, or who approved X."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Named item, vendor, project, or approval subject to search for."},
                        "limit": {"type": "integer", "default": 10},
                        "include_pending": {"type": "boolean", "default": True},
                        "include_rejected": {"type": "boolean", "default": True},
                        "since": {"type": "string", "description": "ISO datetime; approvals after this time."},
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
                description=(
                    "Draft a follow-up reply using thread/message/contact context. "
                    "Defaults to email style when thread/email signals are present; "
                    "otherwise returns a channel-neutral message draft."
                ),
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
                        "user_request": {"type": "string", "description": "Raw user ask; ensure explicit points are covered."},
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
                        "include_recent_context": {"type": "boolean", "default": False},
                    },
                },
            ),
            
            # Approval-gated tools
            "draft_reply": ToolDefinition(
                name="draft_reply",
                description=(
                    "Draft a reply to an email thread. User must approve before sending. "
                    "Provide email_id (integer) if known, or thread_id (string) to resolve the latest email in that thread."
                ),
                tool_type=ToolType.APPROVAL_GATED,
                parameters={
                    "type": "object",
                    "properties": {
                        "email_id": {"type": "integer", "description": "Integer ID of the specific email to reply to"},
                        "thread_id": {"type": "string", "description": "Thread ID — used to find the latest email when email_id is unknown"},
                        "tone": {"type": "string", "description": "Desired tone (professional, friendly, formal)"},
                        "key_points": {"type": "array", "items": {"type": "string"}, "description": "Points to include"}
                    },
                    "required": []
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
            if tool.name not in HIDDEN_TOOLS
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
            if tool.name not in HIDDEN_TOOLS
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
        include_source_email = bool(params.get("include_source_email", True))
        include_source_body = bool(params.get("include_source_body", False))
        
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
                "source_email": self._build_task_source_email_payload(t, include_body=include_source_body)
                if include_source_email
                else None,
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
        result = self._execute_get_contact_brief(params)
        if not result.success or not isinstance(result.data, dict):
            return result

        brief = result.data
        entries: List[Dict[str, Any]] = []
        summary = brief.get("summary") or {}
        headline = " ".join(str(summary.get("headline") or "").split()).strip()
        if headline:
            entries.append(
                {
                    "id": f"contact-brief:headline:{brief.get('contact_id')}",
                    "type": "insight",
                    "content": headline,
                    "entity_type": "contact",
                    "entity_id": brief.get("contact_email"),
                    "status": "active",
                }
            )

        for item in (brief.get("preferences") or [])[:2]:
            content = " ".join(str(item.get("content") or "").split()).strip()
            if content:
                entries.append(
                    {
                        "id": item.get("id"),
                        "type": "preference",
                        "content": content,
                        "entity_type": "contact",
                        "entity_id": brief.get("contact_email"),
                        "status": "active",
                    }
                )

        for item in (brief.get("commitments") or [])[:2]:
            content = " ".join(str(item.get("title") or "").split()).strip()
            if content:
                entries.append(
                    {
                        "id": item.get("id"),
                        "type": "commitment",
                        "content": content,
                        "entity_type": "contact",
                        "entity_id": brief.get("contact_email"),
                        "status": item.get("status") or "active",
                    }
                )

        self._merge_hot(entries)
        return ToolResult(
            success=True,
            data={
                "contact_email": brief.get("contact_email"),
                "contact_id": brief.get("contact_id"),
                "entries": entries,
                "brief": brief,
            },
            state_updates=result.state_updates,
        )

    def _execute_get_contact_brief(self, params: Dict[str, Any]) -> ToolResult:
        contact = self._resolve_contact_record(
            contact_id=params.get("contact_id"),
            contact=params.get("contact"),
            email=params.get("email"),
            name=params.get("name"),
        )
        if not contact:
            return ToolResult(success=False, error="contact_id/contact/email/name is required")

        brief = ContactBriefService(self.db, user_id=self.user_id).get_contact_brief(contact.id, consumer="chat_tool")
        if not brief:
            return ToolResult(success=False, error="Contact brief not found")

        data = self._serialize_contact_brief(contact, brief)
        return ToolResult(
            success=True,
            data=data,
            state_updates={"current_contact_id": contact.id},
        )

    def _execute_get_contact_timeline(self, params: Dict[str, Any]) -> ToolResult:
        contact, brief = self._resolve_contact_and_brief(params)
        if not contact or not brief:
            return ToolResult(success=False, error="contact_id/contact/email/name is required")

        limit = max(1, min(int(params.get("limit", 8)), 20))
        timeline_items = ContactTimelineService(self.db, user_id=self.user_id).get_contact_timeline(contact.id, limit=limit)
        timeline = [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "title": self._sanitize_prompt_contact_text(
                    item.get("title"),
                    field=f"timeline.{item.get('kind') or 'item'}",
                    contact_id=contact.id,
                ),
                "detail": self._sanitize_prompt_contact_text(
                    item.get("detail"),
                    field=f"timeline.{item.get('kind') or 'item'}_detail",
                    contact_id=contact.id,
                ),
                "occurred_at": self._iso_value(item.get("occurred_at")),
                "source_ref": item.get("source_ref"),
                "source_type": item.get("source_type"),
                "status": item.get("status"),
            }
            for item in (timeline_items or [])
        ]
        return ToolResult(
            success=True,
            data={
                "contact_id": contact.id,
                "contact_email": (contact.email or "").strip().lower() or None,
                "timeline": timeline,
            },
            state_updates={"current_contact_id": contact.id},
        )

    def _execute_get_contact_signals(self, params: Dict[str, Any]) -> ToolResult:
        contact, brief = self._resolve_contact_and_brief(params)
        if not contact or not brief:
            return ToolResult(success=False, error="contact_id/contact/email/name is required")

        signal_items = ContactSignalsService(self.db, user_id=self.user_id).get_contact_signals(contact.id, consumer="chat_tool")
        signals = [
            {
                "key": item.get("key"),
                "label": self._sanitize_prompt_contact_text(item.get("label"), field="signal.label", contact_id=contact.id),
                "message": self._sanitize_prompt_contact_text(item.get("detail"), field="signal.detail", contact_id=contact.id),
                "severity": item.get("severity"),
            }
            for item in (signal_items or [])[:6]
        ]
        return ToolResult(
            success=True,
            data={
                "contact_id": contact.id,
                "contact_email": (contact.email or "").strip().lower() or None,
                "signals": signals,
            },
            state_updates={"current_contact_id": contact.id},
        )

    def _execute_get_thread_history(self, params: Dict[str, Any]) -> ToolResult:
        thread_ref = self._resolve_entity_ref("thread", params.get("thread_id") or params.get("thread"))
        if not thread_ref:
            return ToolResult(success=False, error="thread_id/thread is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))
        include_non_active = bool(params.get("include_non_active", False))

        result = self._execute_context_search(
            {
                "entity_type": "thread",
                "entity_id": thread_ref,
                "types": ["decision", "commitment"],
                "limit": limit,
                "include_non_active": include_non_active,
            }
        )
        if result.success and isinstance(result.data, dict) and result.data.get("entries"):
            result.data["thread_id"] = thread_ref
            return result

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
                    "status": msg.status or "inbox",
                }
            for msg in thread_messages
        ]
        self._merge_hot(entries)
        return ToolResult(success=True, data={"thread_id": thread_ref, "entries": entries})

    def _execute_get_user_preferences(self, params: Dict[str, Any]) -> ToolResult:
        category = params.get("category", "general")
        limit = max(1, min(int(params.get("limit", 5)), 10))
        result = self._execute_context_search(
            {
                "entity_type": "executive",
                "types": ["preference", "preferences"],
                "limit": limit,
                "include_non_active": False,
            }
        )
        if not result.success or not isinstance(result.data, dict):
            return result
        if category and category != "general":
            cat = str(category).lower().strip()
            prefs = [p for p in result.data.get("entries", []) if self._preference_matches_category(p, cat)]
            result.data["entries"] = prefs[:limit]
        result.data["category"] = category
        return result

    def _execute_get_event_context(self, params: Dict[str, Any]) -> ToolResult:
        event_ref = self._resolve_entity_ref("event", params.get("event_id") or params.get("event"))
        if not event_ref:
            return ToolResult(success=False, error="event_id/event is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))
        include_non_active = bool(params.get("include_non_active", False))

        result = self._execute_context_search(
            {
                "entity_type": "event",
                "entity_id": event_ref,
                "types": ["decision", "commitment", "risk", "risks"],
                "limit": limit,
                "include_non_active": include_non_active,
            }
        )
        if result.success and isinstance(result.data, dict) and result.data.get("entries"):
            result.data["event_id"] = event_ref
            return result

        event = None
        if str(event_ref).isdigit():
            event = (
                self.db.query(CalendarEvent)
                .filter(
                    CalendarEvent.user_id == self.user_id,
                    CalendarEvent.id == int(str(event_ref)),
                )
                .first()
            )
        if not event:
            event = (
                self.db.query(CalendarEvent)
                .filter(
                    CalendarEvent.user_id == self.user_id,
                    CalendarEvent.external_event_id == str(event_ref),
                )
                .first()
            )
        entries = []
        if event:
            participants_raw = event.participants if isinstance(event.participants, list) else []
            participant_names: List[str] = []
            for p in participants_raw:
                if isinstance(p, dict):
                    name = " ".join(str(p.get("name") or "").split()).strip()
                    email = " ".join(str(p.get("email") or "").split()).strip()
                    if name or email:
                        participant_names.append(name or email)
                else:
                    value = " ".join(str(p).split()).strip()
                    if value:
                        participant_names.append(value)
            bits = [f"Event: {(event.title or '').strip() or f'Event {event.id}'}"]
            if event.start_time:
                bits.append(f"starts {event.start_time.isoformat()}")
            if event.end_time:
                bits.append(f"ends {event.end_time.isoformat()}")
            if (event.location or "").strip():
                bits.append(f"location: {event.location.strip()}")
            if participant_names:
                bits.append("participants: " + ", ".join(participant_names[:8]))
            entries = [
                {
                    "id": f"event:{event.id}:facts",
                    "type": "event_facts",
                    "content": " | ".join(bits),
                "entity_type": "event",
                "entity_id": str(event.id),
                "created_by": "Teeks",
                "created_at": (event.updated_at or event.start_time or event.created_at).isoformat()
                if (event.updated_at or event.start_time or event.created_at)
                else None,
                "status": event.status or "active",
            }
        ]
        self._merge_hot(entries)
        return ToolResult(success=True, data={"event_id": event_ref, "entries": entries})

    def _execute_get_message_context(self, params: Dict[str, Any]) -> ToolResult:
        message_ref = self._resolve_entity_ref("message", params.get("message_id") or params.get("message"))
        if not message_ref:
            return ToolResult(success=False, error="message_id/message is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))
        include_non_active = bool(params.get("include_non_active", False))
        result = self._execute_context_search(
            {
                "entity_type": "message",
                "entity_id": message_ref,
                "types": ["commitment", "decision", "risk", "risks"],
                "limit": limit,
                "include_non_active": include_non_active,
            }
        )
        if result.success and isinstance(result.data, dict):
            result.data["message_id"] = message_ref
        return result

    def _execute_get_task_context(self, params: Dict[str, Any]) -> ToolResult:
        task_identifier = (params.get("task_id") or params.get("task") or "").strip()
        if not task_identifier:
            return ToolResult(success=False, error="task_id/task is required")
        limit = max(1, min(int(params.get("limit", 8)), 10))

        # Use entity_search for tasks; context_search no longer handles tasks.
        result = self._execute_entity_search(
            {
                "query": task_identifier,
                "entity_types": ["task"],
                "limit": limit,
                "offset": 0,
                "recent_first": True,
                "include_archived": False,
            }
        )
        return result

    def _execute_context_search(self, params: Dict[str, Any]) -> ToolResult:
        query_text = " ".join(str(params.get("query") or "").split()).strip()
        entity_type = (params.get("entity_type") or "").strip().lower()
        entity_id = " ".join(str(params.get("entity_id") or "").split()).strip()
        types = params.get("types") or []
        status = params.get("status") or []
        include_non_active = bool(params.get("include_non_active", False))
        include_tasks = False
        limit = max(1, min(int(params.get("limit", 10)), 25))

        allowed_entity_types = {"contact", "thread", "event", "message", "task", "global", "executive"}
        if entity_type and entity_type not in allowed_entity_types:
            return ToolResult(success=False, error="entity_type is invalid")

        allowed_types = {
            "decision",
            "commitment",
            "preference",
            "risk",
            "insight",
        }
        normalized_types: list[str] = []
        for item in types:
            if item == "preference":
                normalized_types.append("preference")
            elif item == "risk":
                normalized_types.append("risk")
            elif item == "insight":
                normalized_types.append("insight")
            elif item == "preferences":
                normalized_types.append("preference")
            elif item in {"risks", "relationship", "relationships"}:
                normalized_types.append("insight" if item.startswith("relationship") else "risk")
            elif item in allowed_types:
                normalized_types.append(item)
        types = sorted(set(normalized_types))
        if entity_type == "contact" and not types:
            types = ["insight", "preference", "decision", "commitment", "risk"]

        allowed_status = {"active", "resolved", "dismissed", "archived", "stale"}
        status = [s for s in status if s in allowed_status]

        since_ts = self._parse_iso_timestamp(params.get("since"))
        until_ts = self._parse_iso_timestamp(params.get("until"))

        if entity_type and entity_id:
            if entity_type in {"thread", "event", "message", "task"}:
                resolved = self._resolve_entity_ref(entity_type, entity_id)
                if resolved:
                    entity_id = resolved
            if entity_type == "contact":
                resolved_contact = self._resolve_contact_email(contact=entity_id, email=entity_id, name=entity_id)
                if resolved_contact:
                    entity_id = resolved_contact

        now = datetime.now(timezone.utc)
        query = self.db.query(ContextEntry).filter(ContextEntry.user_id == self.user_id)
        query = apply_confidence_retrieval_filter(query)

        if entity_type:
            if entity_type in {"global", "executive"}:
                query = query.filter(ContextEntry.entity_type == "global")
            else:
                query = query.filter(ContextEntry.entity_type == entity_type)
        if entity_id:
            query = query.filter(ContextEntry.entity_id == entity_id)
        if types:
            query = query.filter(ContextEntry.type.in_(sorted(types)))

        if status:
            query = query.filter(ContextEntry.status.in_(sorted(status)))
        elif not include_non_active:
            query = query.filter(ContextEntry.status == "active")

        if since_ts:
            query = query.filter(ContextEntry.created_at >= since_ts)
        if until_ts:
            query = query.filter(ContextEntry.created_at <= until_ts)

        if not include_non_active:
            query = apply_historical_expiry_retrieval_filter(query, now=now)

        if query_text:
            safe_query = escape_like(query_text)
            query = query.filter(ContextEntry.content.ilike(f"%{safe_query}%", escape="\\"))

        rows = (
            query
            .order_by(ContextEntry.updated_at.desc(), ContextEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        entries = [self._serialize_context_entry(r) for r in rows]

        tasks_payload: List[Dict[str, Any]] = []
        if include_tasks or (entity_type == "task"):
            return ToolResult(
                success=False,
                error="Task search is handled by entity_search. Remove include_tasks/entity_type=task.",
            )

        self._merge_hot(entries)
        return ToolResult(
            success=True,
            data={
                "entries": entries,
                "tasks": tasks_payload,
                "query": query_text,
                "entity_type": entity_type or None,
                "entity_id": entity_id or None,
            },
        )

    def _execute_entity_search(self, params: Dict[str, Any]) -> ToolResult:
        query_text = " ".join(str(params.get("query") or "").split()).strip()
        entity_types = params.get("entity_types") or []
        limit = max(1, min(int(params.get("limit", 20)), 50))
        offset = max(0, int(params.get("offset", 0)))
        recent_first = bool(params.get("recent_first", True))
        include_archived = bool(params.get("include_archived", False))
        include_source_body = bool(params.get("include_source_body", False))

        allowed = {"contact", "thread", "event", "message", "task"}
        entity_types = [t for t in entity_types if t in allowed]
        if not entity_types:
            return ToolResult(success=False, error="entity_types is required")

        results: List[Dict[str, Any]] = []
        safe_query = escape_like(query_text) if query_text else ""

        if "contact" in entity_types:
            q = self.db.query(Contact).filter(Contact.user_id == self.user_id)
            if query_text:
                q = q.filter(
                    (func.lower(Contact.name).ilike(f"%{safe_query}%", escape="\\"))
                    | (func.lower(Contact.email).ilike(f"%{safe_query}%", escape="\\"))
                )
            contacts = (
                q.order_by(Contact.updated_at.desc(), Contact.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for c in contacts:
                label = (c.name or c.email or "Contact").strip()
                ref = (c.email or "").lower() if c.email else f"contact:{c.id}"
                results.append(
                    {
                        "kind": "contact",
                        "ref": ref,
                        "label": label,
                        "last_updated_at": (c.updated_at or c.created_at).isoformat() if (c.updated_at or c.created_at) else None,
                        "search_text": " ".join(filter(None, [c.name, c.email])),
                        "sample": (c.notes or "")[:140] if hasattr(c, "notes") else "",
                    }
                )

        if "thread" in entity_types:
            q = self.db.query(EntityReference).filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "thread",
            )
            q = q.filter(~EntityReference.ref.ilike(f"{MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX}%"))
            if query_text:
                q = q.filter(
                    func.lower(EntityReference.display_name).ilike(f"%{safe_query}%", escape="\\")
                    | func.lower(EntityReference.ref).ilike(f"%{safe_query}%", escape="\\")
                )
            refs = (
                q.order_by(EntityReference.updated_at.desc(), EntityReference.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for r in refs:
                results.append(
                    {
                        "kind": "thread",
                        "ref": r.ref,
                        "label": r.display_name or r.ref,
                        "last_updated_at": (r.updated_at or r.created_at).isoformat() if (r.updated_at or r.created_at) else None,
                        "search_text": " ".join(filter(None, [r.display_name, r.ref])),
                        "sample": (r.notes or "")[:140] if hasattr(r, "notes") else "",
                    }
                )
            # Fallback to recent threads from messages when no entity references exist.
            if not refs:
                mq = self.db.query(Message).filter(Message.user_id == self.user_id)
                mq = mq.filter(~Message.thread_id.ilike(f"{MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX}%"))
                mq = mq.filter(~Message.message_id.ilike(f"{MANUAL_TASK_PLACEHOLDER_MESSAGE_PREFIX}%"))
                if query_text:
                    mq = mq.filter(
                        Message.subject.ilike(f"%{safe_query}%", escape="\\")
                        | Message.thread_id.ilike(f"%{safe_query}%", escape="\\")
                    )
                msg_rows = (
                    mq.order_by(Message.received_at.desc(), Message.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                    .all()
                )
                seen_thread_ids = set()
                for msg in msg_rows:
                    if not msg.thread_id or msg.thread_id in seen_thread_ids:
                        continue
                    seen_thread_ids.add(msg.thread_id)
                    results.append(
                        {
                            "kind": "thread",
                            "ref": msg.thread_id,
                            "label": (msg.subject or msg.thread_id).strip(),
                            "last_updated_at": (msg.received_at or msg.created_at).isoformat()
                            if (msg.received_at or msg.created_at)
                            else None,
                            "search_text": " ".join(filter(None, [msg.subject, msg.thread_id])),
                            "sample": ((msg.summary or msg.decrypted_body or "")[:140]),
                        }
                    )

        if "event" in entity_types:
            q = self.db.query(EntityReference).filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "event",
            )
            if query_text:
                q = q.filter(
                    func.lower(EntityReference.display_name).ilike(f"%{safe_query}%", escape="\\")
                    | func.lower(EntityReference.ref).ilike(f"%{safe_query}%", escape="\\")
                )
            refs = (
                q.order_by(EntityReference.updated_at.desc(), EntityReference.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for r in refs:
                results.append(
                    {
                        "kind": "event",
                        "ref": r.ref,
                        "label": r.display_name or r.ref,
                        "last_updated_at": (r.updated_at or r.created_at).isoformat() if (r.updated_at or r.created_at) else None,
                        "search_text": " ".join(filter(None, [r.display_name, r.ref])),
                        "sample": (r.notes or "")[:140] if hasattr(r, "notes") else "",
                    }
                )
            # Fallback to calendar events when entity references are missing.
            if not refs:
                eq = self.db.query(CalendarEvent).filter(CalendarEvent.user_id == self.user_id)
                if query_text:
                    eq = eq.filter(CalendarEvent.title.ilike(f"%{safe_query}%", escape="\\"))
                events = (
                    eq.order_by(CalendarEvent.start_time.desc(), CalendarEvent.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                    .all()
                )
                for event in events:
                    ref_value = (event.external_event_id or str(event.id)).strip()
                    results.append(
                        {
                            "kind": "event",
                            "ref": ref_value,
                            "label": (event.title or ref_value).strip(),
                            "last_updated_at": (event.updated_at or event.start_time or event.created_at).isoformat()
                            if (event.updated_at or event.start_time or event.created_at)
                            else None,
                            "search_text": " ".join(filter(None, [event.title, ref_value])),
                            "sample": (event.location or "")[:140],
                        }
                    )

        if "message" in entity_types:
            q = self.db.query(Message).filter(Message.user_id == self.user_id)
            if not include_archived:
                q = q.filter(Message.status == "inbox")
            if query_text:
                q = q.filter(
                    Message.subject.ilike(f"%{safe_query}%", escape="\\")
                    | Message.sender.ilike(f"%{safe_query}%", escape="\\")
                )
            messages = (
                q.order_by(Message.received_at.desc(), Message.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for m in messages:
                label = (m.subject or "Message").strip()
                results.append(
                    {
                        "kind": "message",
                        "ref": str(m.id),
                        "label": label,
                        "last_updated_at": (m.updated_at or m.received_at or m.created_at).isoformat()
                        if (m.updated_at or m.received_at or m.created_at)
                        else None,
                        "search_text": " ".join(filter(None, [m.subject, m.sender])),
                        "sample": ((m.summary or m.decrypted_body or "")[:140]),
                    }
                )

        if "task" in entity_types:
            q = self.db.query(Task).filter(Task.user_id == self.user_id)
            if not include_archived:
                q = q.filter(Task.status.in_(["pending_approval", "approved", "in_progress"]))
            if query_text:
                q = q.filter(Task.title.ilike(f"%{safe_query}%", escape="\\"))
            tasks = (
                q.order_by(Task.updated_at.desc(), Task.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            for t in tasks:
                source_email = self._build_task_source_email_payload(t, include_body=include_source_body)
                source_search = ""
                if source_email:
                    source_search = " ".join(
                        filter(
                            None,
                            [
                                str(source_email.get("subject") or ""),
                                str(source_email.get("sender") or ""),
                                str(source_email.get("summary") or source_email.get("snippet") or ""),
                            ],
                        )
                    )
                results.append(
                    {
                        "kind": "task",
                        "ref": str(t.id),
                        "label": t.title,
                        "last_updated_at": (t.updated_at or t.created_at).isoformat() if (t.updated_at or t.created_at) else None,
                        "search_text": " ".join(filter(None, [t.title, source_search])).strip(),
                        "sample": (t.description or "")[:140],
                        "source_email": source_email,
                    }
                )

        if recent_first:
            results.sort(key=lambda item: item.get("last_updated_at") or "", reverse=True)

        return ToolResult(success=True, data={"items": results[:limit], "count": len(results[:limit])})

    def _execute_get_approval_history(self, params: Dict[str, Any]) -> ToolResult:
        query_text = " ".join(str(params.get("query") or "").split()).strip()
        include_pending = bool(params.get("include_pending", True))
        include_rejected = bool(params.get("include_rejected", True))
        limit = max(1, min(int(params.get("limit", 10)), 25))
        since_ts = self._parse_iso_timestamp(params.get("since"))
        search_terms = self._approval_search_terms(query_text)
        if not search_terms:
            return ToolResult(
                success=False,
                error="A specific approval subject is required for approval history lookup.",
            )

        items: List[Dict[str, Any]] = []

        task_query = self.db.query(Task).filter(Task.user_id == self.user_id)
        task_statuses = ["approved", "completed", "superseded"]
        if include_pending:
            task_statuses.append("pending_approval")
        if include_rejected:
            task_statuses.append("dismissed")
        task_query = task_query.filter(Task.status.in_(sorted(set(task_statuses))))
        if since_ts:
            task_query = task_query.filter(
                or_(
                    Task.approved_at >= since_ts,
                    Task.updated_at >= since_ts,
                    Task.created_at >= since_ts,
                )
            )
        tasks = (
            task_query
            .order_by(Task.approved_at.desc(), Task.updated_at.desc(), Task.created_at.desc())
            .limit(max(limit * 3, 20))
            .all()
        )
        for task in tasks:
            source_email = self._build_task_source_email_payload(task, include_body=False)
            text_blob = " ".join(
                filter(
                    None,
                    [
                        task.title or "",
                        task.description or "",
                        task.source_snippet or "",
                        json.dumps(task.related_people or [], ensure_ascii=True),
                        json.dumps(source_email or {}, ensure_ascii=True),
                    ],
                )
            )
            if not self._approval_text_matches(text_blob, search_terms):
                continue
            items.append(
                {
                    "source": "task",
                    "ref": str(task.id),
                    "title": (task.title or f"Task {task.id}").strip(),
                    "status": task.status,
                    "approved": bool(task.status == "approved" or task.approved_at),
                    "acted_at": (
                        task.approved_at or task.updated_at or task.created_at
                    ).isoformat() if (task.approved_at or task.updated_at or task.created_at) else None,
                    "summary": (task.description or task.source_snippet or "").strip()[:240] or None,
                    "thread_id": (task.thread_id or "").strip() or None,
                    "source_email": source_email,
                }
            )

        action_query = (
            self.db.query(ChatPendingAction)
            .join(ChatSession, ChatPendingAction.session_id == ChatSession.id)
            .filter(ChatSession.user_id == self.user_id)
        )
        action_statuses = ["approved"]
        if include_pending:
            action_statuses.append("pending")
        if include_rejected:
            action_statuses.append("rejected")
        action_query = action_query.filter(ChatPendingAction.status.in_(sorted(set(action_statuses))))
        if since_ts:
            action_query = action_query.filter(ChatPendingAction.created_at >= since_ts)
        actions = (
            action_query
            .order_by(ChatPendingAction.created_at.desc())
            .limit(max(limit * 3, 20))
            .all()
        )
        for action in actions:
            action_data = action.action_data or {}
            text_blob = " ".join(
                filter(
                    None,
                    [
                        action.action_type or "",
                        json.dumps(action_data, ensure_ascii=True, sort_keys=True),
                    ],
                )
            )
            if not self._approval_text_matches(text_blob, search_terms):
                continue
            items.append(
                {
                    "source": "chat_action",
                    "ref": action.id,
                    "title": self._approval_action_title(action),
                    "status": action.status,
                    "approved": action.status == "approved",
                    "acted_at": (
                        action.reviewed_at or action.created_at
                    ).isoformat() if (action.reviewed_at or action.created_at) else None,
                    "summary": self._truncate_approval_summary(json.dumps(action_data, ensure_ascii=True, sort_keys=True)),
                    "action_type": action.action_type,
                }
            )

        proposal_query = self.db.query(VaultProposal).filter(VaultProposal.user_id == self.user_id)
        proposal_statuses = ["approved"]
        if include_pending:
            proposal_statuses.append("pending")
        if include_rejected:
            proposal_statuses.append("rejected")
        proposal_query = proposal_query.filter(VaultProposal.status.in_(sorted(set(proposal_statuses))))
        if since_ts:
            proposal_query = proposal_query.filter(
                or_(
                    VaultProposal.reviewed_at >= since_ts,
                    VaultProposal.created_at >= since_ts,
                )
            )
        proposals = (
            proposal_query
            .order_by(VaultProposal.reviewed_at.desc(), VaultProposal.created_at.desc())
            .limit(max(limit * 2, 15))
            .all()
        )
        for proposal in proposals:
            proposal_data = proposal.proposed_data or {}
            text_blob = " ".join(
                filter(
                    None,
                    [
                        proposal.proposal_type or "",
                        proposal.diff_summary or "",
                        proposal.source_type or "",
                        proposal.source_id or "",
                        json.dumps(proposal_data, ensure_ascii=True, sort_keys=True),
                    ],
                )
            )
            if not self._approval_text_matches(text_blob, search_terms):
                continue
            items.append(
                {
                    "source": "vault_proposal",
                    "ref": str(proposal.id),
                    "title": self._approval_proposal_title(proposal),
                    "status": proposal.status,
                    "approved": proposal.status == "approved",
                    "acted_at": (
                        proposal.reviewed_at or proposal.created_at
                    ).isoformat() if (proposal.reviewed_at or proposal.created_at) else None,
                    "summary": self._truncate_approval_summary(proposal.diff_summary or json.dumps(proposal_data, ensure_ascii=True, sort_keys=True)),
                    "proposal_type": proposal.proposal_type,
                }
            )

        items.sort(key=lambda item: item.get("acted_at") or "", reverse=True)
        trimmed = items[:limit]
        return ToolResult(
            success=True,
            data={
                "items": trimmed,
                "count": len(trimmed),
                "query": query_text or None,
                "approved_count": sum(1 for item in trimmed if item.get("status") == "approved"),
                "pending_count": sum(1 for item in trimmed if item.get("status") in {"pending", "pending_approval"}),
                "rejected_count": sum(1 for item in trimmed if item.get("status") in {"rejected", "dismissed"}),
                "latest_match": trimmed[0] if trimmed else None,
            },
        )

    def _approval_search_terms(self, query_text: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9][a-z0-9._-]*", (query_text or "").lower())
        terms: List[str] = []
        seen = set()
        has_long_term = False
        filtered_tokens: List[str] = []
        for token in tokens:
            if token in APPROVAL_QUERY_STOPWORDS:
                continue
            filtered_tokens.append(token)
            if len(token) >= 2 or token.isdigit():
                has_long_term = True

        for token in filtered_tokens:
            if len(token) < 2 and not token.isdigit() and not has_long_term:
                continue
            if token in seen:
                continue
            seen.add(token)
            terms.append(token)
        return terms

    def _approval_text_matches(self, text_blob: str, search_terms: List[str]) -> bool:
        if not search_terms:
            return True
        lowered = " ".join(str(text_blob or "").lower().split())
        return all(term in lowered for term in search_terms)

    def _approval_action_title(self, action: ChatPendingAction) -> str:
        data = action.action_data or {}
        title = (
            data.get("title")
            or data.get("subject")
            or data.get("event_title")
            or data.get("email_subject")
            or action.action_type
            or "Approval action"
        )
        return " ".join(str(title).split()).strip()

    def _approval_proposal_title(self, proposal: VaultProposal) -> str:
        proposed_data = proposal.proposed_data or {}
        title = (
            proposed_data.get("title")
            or proposed_data.get("name")
            or proposed_data.get("slug")
            or proposal.diff_summary
            or proposal.proposal_type
            or f"Proposal {proposal.id}"
        )
        return " ".join(str(title).split()).strip()

    def _truncate_approval_summary(self, value: str, limit: int = 240) -> Optional[str]:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return None
        return text[:limit]

    def _build_task_source_email_payload(self, task: Task, include_body: bool = False) -> Optional[Dict[str, Any]]:
        source = getattr(task, "source_message", None)
        if not source and getattr(task, "message_id", None):
            source = (
                self.db.query(Message)
                .filter(
                    Message.user_id == self.user_id,
                    Message.id == task.message_id,
                )
                .first()
            )
        if not source:
            return None

        source_msg_id = (source.message_id or "").strip()
        source_thread_id = (source.thread_id or "").strip()
        task_thread_id = (task.thread_id or "").strip()
        if source_msg_id.startswith(MANUAL_TASK_PLACEHOLDER_MESSAGE_PREFIX):
            return None
        if source_thread_id.startswith(MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX):
            return None
        if task_thread_id.startswith(MANUAL_TASK_PLACEHOLDER_THREAD_PREFIX):
            return None

        decrypted = (source.decrypted_body or "").strip()
        summary = (source.summary or "").strip() or (task.source_snippet or "").strip()
        snippet = summary or (decrypted[:280] if decrypted else "")

        payload: Dict[str, Any] = {
            "message_id": source.id,
            "message_ref": source.message_id,
            "thread_id": source.thread_id,
            "subject": source.subject,
            "sender": source.sender,
            "received_at": source.received_at.isoformat() if source.received_at else None,
            "summary": summary or None,
            "snippet": snippet or None,
        }
        if include_body:
            payload["body"] = decrypted
        return payload

    def _execute_draft_email(self, params: Dict[str, Any]) -> ToolResult:
        service = EmailDraftingService(db=self.db, user_id=self.user_id)
        subject = (
            (params.get("subject") or "").strip()
            or (params.get("thread") or "").strip()
            or (params.get("intent") or "").strip()
            or "Follow-up"
        )
        safe_log = {
            "subject": subject,
            "intent": (params.get("intent") or "").strip(),
            "recipient": (params.get("recipient") or "").strip()[:200],
            "thread_id": (params.get("thread_id") or "").strip()[:200],
            "message_id": (params.get("message_id") or "").strip()[:200],
        }
        logger.info("draft_email_invoked %s", safe_log)
        try:
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
                user_request=params.get("user_request"),
            )
            return ToolResult(success=True, data=draft)
        except DraftGenerationError as exc:
            return ToolResult(success=False, error=str(exc) or "draft_generation_failed")

    def _user_safe_validation_error(self, tool_name: str) -> str:
        name = (tool_name or "").strip().lower()
        if name == "create_task":
            return "I need a task title to create that."
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
            include_recent_context=bool(params.get("include_recent_context", False)),
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
        row = self._find_unique_contact_by_exact_name(candidate_name)
        if row and row.email:
            return row.email.lower()
        return None

    def _resolve_contact_record(
        self,
        *,
        contact_id: Optional[Any] = None,
        contact: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Contact]:
        if contact_id not in (None, ""):
            try:
                resolved_id = int(contact_id)
            except (TypeError, ValueError):
                resolved_id = None
            if resolved_id is not None:
                row = (
                    self.db.query(Contact)
                    .filter(Contact.user_id == self.user_id, Contact.id == resolved_id)
                    .first()
                )
                if row:
                    return row

        email_norm = self._resolve_contact_email(contact=contact, email=email, name=name)
        if email_norm:
            return (
                self.db.query(Contact)
                .filter(Contact.user_id == self.user_id, func.lower(Contact.email) == email_norm)
                .first()
            )
        return None

    def _find_unique_contact_by_exact_name(self, lookup: str) -> Optional[Contact]:
        token = " ".join(str(lookup or "").split()).strip()
        if not token:
            return None
        rows = (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                func.lower(Contact.name) == token.lower(),
            )
            .limit(2)
            .all()
        )
        if len(rows) != 1:
            return None
        return rows[0]

    def _resolve_contact_and_brief(self, params: Dict[str, Any]) -> tuple[Optional[Contact], Optional[Dict[str, Any]]]:
        contact = self._resolve_contact_record(
            contact_id=params.get("contact_id"),
            contact=params.get("contact"),
            email=params.get("email"),
            name=params.get("name"),
        )
        if not contact:
            return None, None
        brief = ContactBriefService(self.db, user_id=self.user_id).get_contact_brief(contact.id, consumer="chat_tool")
        if not brief:
            return contact, None
        return contact, brief

    def _resolve_entity_ref(self, entity_type: str, identifier: Optional[str]) -> Optional[str]:
        query = " ".join(str(identifier or "").split()).strip().lstrip("@/")
        query = query.strip(".,;:!?)]}\"'")
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
                (func.lower(EntityReference.display_name) == query.lower())
                | EntityReference.display_name.ilike(f"%{query}%"),
            )
            .first()
        )
        if by_name:
            return by_name.ref
        return query

    def _parse_iso_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        raw = " ".join(str(value or "").split()).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    def _serialize_context_entry(self, row: ContextEntry) -> Dict[str, Any]:
        source_resolved = self._context_entry_source_resolved(
            entity_type=row.entity_type,
            entity_id=row.entity_id,
        )
        return {
            "id": row.id,
            "type": row.type,
            "content": row.content,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "source_resolved": source_resolved,
            "source_availability_note": self._context_entry_source_availability_note(
                entity_type=row.entity_type,
                source_resolved=source_resolved,
            ),
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "status": row.status,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }

    def _context_entry_source_resolved(self, *, entity_type: Optional[str], entity_id: Optional[str]) -> Optional[bool]:
        normalized_type = " ".join(str(entity_type or "").split()).strip().lower()
        normalized_id = " ".join(str(entity_id or "").split()).strip()
        if normalized_type in {"", "global", "executive"}:
            return None
        if not normalized_id:
            return None
        if normalized_type == "contact":
            query = self.db.query(Contact).filter(Contact.user_id == self.user_id)
            if normalized_id.isdigit():
                return query.filter(Contact.id == int(normalized_id)).first() is not None
            return query.filter(func.lower(Contact.email) == normalized_id.lower()).first() is not None
        if normalized_type == "thread":
            if (
                self.db.query(Message.id)
                .filter(Message.user_id == self.user_id, Message.thread_id == normalized_id)
                .first()
                is not None
            ):
                return True
            if (
                self.db.query(ThreadState.id)
                .filter(ThreadState.user_id == self.user_id, ThreadState.thread_id == normalized_id)
                .first()
                is not None
            ):
                return True
            return (
                self.db.query(EntityReference.id)
                .filter(
                    EntityReference.user_id == self.user_id,
                    EntityReference.entity_type == "thread",
                    EntityReference.ref == normalized_id,
                )
                .first()
            ) is not None
        if normalized_type == "message":
            query = self.db.query(Message.id).filter(Message.user_id == self.user_id)
            if normalized_id.isdigit() and query.filter(Message.id == int(normalized_id)).first() is not None:
                return True
            return query.filter(
                or_(Message.message_id == normalized_id, Message.external_message_id == normalized_id)
            ).first() is not None
        if normalized_type == "event":
            query = self.db.query(CalendarEvent.id).filter(CalendarEvent.user_id == self.user_id)
            if normalized_id.isdigit() and query.filter(CalendarEvent.id == int(normalized_id)).first() is not None:
                return True
            if query.filter(CalendarEvent.external_event_id == normalized_id).first() is not None:
                return True
            return (
                self.db.query(EntityReference.id)
                .filter(
                    EntityReference.user_id == self.user_id,
                    EntityReference.entity_type == "event",
                    EntityReference.ref == normalized_id,
                )
                .first()
            ) is not None
        if normalized_type == "task":
            if not normalized_id.isdigit():
                return False
            return (
                self.db.query(Task.id)
                .filter(Task.user_id == self.user_id, Task.id == int(normalized_id))
                .first()
            ) is not None
        return None

    def _context_entry_source_availability_note(
        self,
        *,
        entity_type: Optional[str],
        source_resolved: Optional[bool],
    ) -> Optional[str]:
        if source_resolved is not False:
            return None
        normalized_type = " ".join(str(entity_type or "").split()).strip().lower()
        if normalized_type == "thread":
            return "The source thread is no longer present in the inbox."
        if normalized_type == "message":
            return "The source message is no longer present in the inbox."
        if normalized_type == "event":
            return "The source event is no longer present on the calendar."
        if normalized_type == "task":
            return "The source task is no longer present."
        if normalized_type == "contact":
            return "The linked contact is no longer present."
        return "The original source is no longer present."

    def _serialize_contact_brief(self, contact: Contact, brief: Dict[str, Any]) -> Dict[str, Any]:
        summary = brief.get("summary") or {}
        return {
            "contact_id": contact.id,
            "contact_email": (contact.email or "").strip().lower() or None,
            "contact_name": self._sanitize_prompt_contact_text(contact.name, field="contact.name", contact_id=contact.id),
            "contact": {
                "id": contact.id,
                "name": self._sanitize_prompt_contact_text(contact.name, field="contact.name", contact_id=contact.id),
                "email": contact.email,
                "role": self._sanitize_prompt_contact_text(contact.role, field="contact.role", contact_id=contact.id),
                "organization": self._sanitize_prompt_contact_text(contact.organization, field="contact.organization", contact_id=contact.id),
                "category": self._sanitize_prompt_contact_text(contact.category, field="contact.category", contact_id=contact.id),
            },
            "summary": {
                "headline": self._sanitize_prompt_contact_text(summary.get("headline"), field="brief.headline", contact_id=contact.id),
                "manual_notes": self._sanitize_prompt_contact_text(summary.get("manual_notes"), field="brief.manual_notes", contact_id=contact.id),
                "preferred_tone": self._sanitize_prompt_contact_text(summary.get("preferred_tone"), field="brief.preferred_tone", contact_id=contact.id),
                "relationship_notes": self._sanitize_prompt_contact_list(summary.get("relationship_notes") or [], field="brief.relationship_note", contact_id=contact.id),
            },
            "preferences": [
                {
                    "id": item.get("id"),
                    "content": self._sanitize_prompt_contact_text(item.get("content"), field="brief.preference", contact_id=contact.id),
                }
                for item in (brief.get("preferences") or [])[:4]
            ],
            "commitments": [
                {
                    "id": item.get("id"),
                    "title": self._sanitize_prompt_contact_text(item.get("title"), field="brief.commitment", contact_id=contact.id),
                    "status": item.get("status"),
                    "due_at": item.get("due_at").isoformat() if hasattr(item.get("due_at"), "isoformat") else item.get("due_at"),
                }
                for item in (brief.get("commitments") or [])[:4]
            ],
            "decisions": [
                {
                    "id": item.get("id"),
                    "decision": self._sanitize_prompt_contact_text(item.get("decision"), field="brief.decision", contact_id=contact.id),
                    "created_at": item.get("created_at").isoformat() if hasattr(item.get("created_at"), "isoformat") else item.get("created_at"),
                }
                for item in (brief.get("decisions") or [])[:4]
            ],
            "recent_interactions": [
                {
                    "id": item.get("id"),
                    "subject": self._sanitize_prompt_contact_text(item.get("subject"), field="brief.interaction_subject", contact_id=contact.id),
                    "summary": self._sanitize_prompt_contact_text(item.get("summary"), field="brief.interaction_summary", contact_id=contact.id),
                    "occurred_at": item.get("occurred_at").isoformat() if hasattr(item.get("occurred_at"), "isoformat") else item.get("occurred_at"),
                    "thread_id": item.get("thread_id"),
                }
                for item in (brief.get("recent_interactions") or [])[:4]
            ],
            "signals": [
                {
                    "type": item.get("type"),
                    "message": self._sanitize_prompt_contact_text(item.get("message"), field="brief.signal", contact_id=contact.id),
                    "severity": item.get("severity"),
                }
                for item in (brief.get("signals") or [])[:4]
            ],
        }

    def _sanitize_prompt_contact_text(self, value: Any, *, field: str, contact_id: int) -> Optional[str]:
        text = str(value or "")
        if not text:
            return None
        result = sanitize_with_detection(text)
        if result.patterns_detected:
            logger.warning(
                "contact_tool_payload_sanitized contact_id=%s field=%s patterns=%s",
                contact_id,
                field,
                result.patterns_detected,
            )
        cleaned = " ".join(result.sanitized_text.split()).strip()
        return cleaned or None

    def _sanitize_prompt_contact_list(self, values: List[Any], *, field: str, contact_id: int) -> List[str]:
        cleaned: List[str] = []
        for value in values:
            item = self._sanitize_prompt_contact_text(value, field=field, contact_id=contact_id)
            if item:
                cleaned.append(item)
        return cleaned

    def _iso_value(self, value: Any) -> Optional[str]:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        text = str(value or "").strip()
        return text or None

    def _filter_context_entries(self, entries: List[Dict[str, Any]], include_non_active: bool) -> List[Dict[str, Any]]:
        """Filter out expired or non-active entries unless explicitly allowed."""
        now = datetime.now(timezone.utc)
        governed_statuses = {"active", "resolved", "stale", "archived", "forgotten"}
        filtered: List[Dict[str, Any]] = []
        for entry in entries or []:
            status = (entry.get("status") or "active").lower()
            if not is_expiry_retrievable(
                entry_type=entry.get("type"),
                expires_at=entry.get("expires_at"),
                now=now,
            ):
                continue
            if status not in governed_statuses:
                filtered.append(entry)
            elif status == "active" or include_non_active:
                filtered.append(entry)
        return filtered

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
        notes = [n for n in notes if (n.status or "active") == "active"]
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
        thread_id = params.get("thread_id")

        if email_id is not None:
            email = self.db.query(Message).filter(
                Message.id == email_id,
                Message.user_id == self.user_id,
            ).first()
        elif thread_id:
            # Resolve to the most recent email in the referenced thread
            email = (
                self.db.query(Message)
                .filter(Message.thread_id == thread_id, Message.user_id == self.user_id)
                .order_by(Message.received_at.desc())
                .first()
            )
        else:
            return ToolResult(success=False, error="Provide email_id or thread_id to identify the email")

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
                    "email_id": email.id,
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
