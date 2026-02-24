"""Playground chat tool registry.

Modeled after backend/src/app/chat/tools.py with focus on context retrieval tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

from google.genai import types as genai_types
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, EntityReference
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
from app.superpowers.thread_intelligence import ThreadIntelligenceService

logger = logging.getLogger(__name__)


class ToolType(Enum):
    READ_ONLY = "read_only"
    ACTION = "action"


@dataclass
class ToolDefinition:
    name: str
    description: str
    tool_type: ToolType
    parameters: Dict[str, Any]


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    state_updates: Optional[Dict[str, Any]] = None
    pending_action: Optional[Dict[str, Any]] = None


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]


class ToolValidationError(ValueError):
    """Raised when a tool call does not satisfy its declared parameter schema."""


class ChatToolRegistry:
    """Registry and executor for context retrieval tools."""

    def __init__(
        self,
        db: Session,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        session_id: str = "default",
    ):
        if user_id is None and tenant_id not in {"", "default"}:
            # Backward-compatible positional signature: ChatToolRegistry(db, user_id)
            user_id = tenant_id
            tenant_id = "default"
        self.db = db
        self.tenant_id = tenant_id or "default"
        self.user_id = user_id or "anonymous"
        self.session_id = session_id
        self._tools = self._register_tools()

    def _register_tools(self) -> Dict[str, ToolDefinition]:
        return {
            "get_contact_context": ToolDefinition(
                name="get_contact_context",
                description=(
                    "Get relationship history and communication patterns for a contact. "
                    "Use when the user references a person or asks what someone committed/decided."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "contact": {
                            "type": "string",
                            "description": "Contact identifier: email or display name",
                        },
                        "email": {"type": "string", "description": "Contact email"},
                        "name": {"type": "string", "description": "Contact display name"},
                        "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            "get_thread_history": ToolDefinition(
                name="get_thread_history",
                description=(
                    "Get thread-level history for decisions, commitments, and related context. "
                    "Use for recap/status/what was decided questions."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "thread": {"type": "string", "description": "Thread id or display name"},
                        "thread_id": {"type": "string", "description": "Thread identifier"},
                        "limit": {"type": "integer", "default": 8, "minimum": 1, "maximum": 10},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            "get_user_preferences": ToolDefinition(
                name="get_user_preferences",
                description=(
                    "Get user preferences relevant to drafting/scheduling/tone. "
                    "Use when drafting replies or planning meetings."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["tone", "scheduling", "working_hours", "general"],
                            "default": "general",
                        },
                        "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
                    },
                    "required": ["category"],
                    "additionalProperties": False,
                },
            ),
            "get_event_context": ToolDefinition(
                name="get_event_context",
                description=(
                    "Get event-specific context such as decisions, commitments, and related notes. "
                    "Use when the user references a calendar event or meeting."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "event": {"type": "string", "description": "Event id or display name"},
                        "event_id": {"type": "string", "description": "Calendar event identifier"},
                        "limit": {"type": "integer", "default": 8, "minimum": 1, "maximum": 10},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            "get_message_context": ToolDefinition(
                name="get_message_context",
                description=(
                    "Get message-scoped context such as commitments, decisions, and risks tied to a message."
                ),
                tool_type=ToolType.READ_ONLY,
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message id or display name"},
                        "message_id": {"type": "string", "description": "Message identifier"},
                        "limit": {"type": "integer", "default": 8, "minimum": 1, "maximum": 10},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            "draft_email": ToolDefinition(
                name="draft_email",
                description=(
                    "Action tool: draft an email using intent plus thread/message/contact context. "
                    "Use for drafting or rewriting replies."
                ),
                tool_type=ToolType.ACTION,
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "intent": {"type": "string"},
                        "recipient": {"type": "string"},
                        "sender_name": {"type": "string", "description": "Name to use in the email sign-off"},
                        "thread_id": {"type": "string"},
                        "message_id": {"type": "string"},
                        "thread": {"type": "string"},
                        "message": {"type": "string"},
                        "context": {"type": "object"},
                    },
                    "required": ["subject", "intent"],
                    "additionalProperties": False,
                },
            ),
            "generate_meeting_brief": ToolDefinition(
                name="generate_meeting_brief",
                description=(
                    "Action tool: generate a meeting brief using event id (preferred) or meeting subject."
                ),
                tool_type=ToolType.ACTION,
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "meeting_subject": {"type": "string"},
                        "participant_ids": {"type": "array", "items": {"type": "string"}},
                        "include_recent_context": {"type": "boolean", "default": True},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
            "generate_thread_intelligence": ToolDefinition(
                name="generate_thread_intelligence",
                description=(
                    "Action tool: generate thread intelligence summary, action points, decisions, commitments, and risks."
                ),
                tool_type=ToolType.ACTION,
                parameters={
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string"},
                        "thread": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            ),
        }

    def list_definitions(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def list_definitions_for_prompt(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "tool_type": t.tool_type.value,
            }
            for t in self._tools.values()
        ]

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Compatibility shape with backend chat orchestrator."""
        definitions: List[Dict[str, Any]] = []
        for tool in self._tools.values():
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return definitions

    def list_function_declarations(self) -> List[genai_types.FunctionDeclaration]:
        declarations: List[genai_types.FunctionDeclaration] = []
        for tool in self._tools.values():
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters_json_schema=tool.parameters,
                )
            )
        return declarations

    def is_action_tool(self, name: str) -> bool:
        tool = self._tools.get((name or "").strip())
        return bool(tool and tool.tool_type == ToolType.ACTION)

    def execute_tool(self, call: ToolCall | str, arguments: Optional[Dict[str, Any]] = None) -> ToolResult:
        if isinstance(call, ToolCall):
            tool_name = call.name
            tool_args = call.arguments
        else:
            tool_name = (call or "").strip()
            tool_args = arguments or {}

        if tool_name not in self._tools:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        handlers = {
            "get_contact_context": self._get_contact_context,
            "get_thread_history": self._get_thread_history,
            "get_user_preferences": self._get_user_preferences,
            "get_event_context": self._get_event_context,
            "get_message_context": self._get_message_context,
            "draft_email": self._draft_email,
            "generate_meeting_brief": self._generate_meeting_brief,
            "generate_thread_intelligence": self._generate_thread_intelligence,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"No handler for tool: {tool_name}")

        try:
            tool = self._tools[tool_name]
            validated_args = self._validate_and_normalize_args(tool, tool_args or {})
            return handler(**validated_args)
        except ToolValidationError as exc:
            return ToolResult(success=False, error=f"Invalid tool arguments: {exc}")
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _validate_and_normalize_args(self, tool: ToolDefinition, args: Dict[str, Any]) -> Dict[str, Any]:
        schema = tool.parameters or {}
        if schema.get("type") != "object":
            raise ToolValidationError(f"{tool.name}: parameters schema must be type=object")
        if not isinstance(args, dict):
            raise ToolValidationError(f"{tool.name}: arguments must be an object")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        allow_extra = bool(schema.get("additionalProperties", True))

        unknown = sorted(set(args.keys()) - set(properties.keys()))
        if unknown and not allow_extra:
            raise ToolValidationError(f"{tool.name}: unknown arguments: {', '.join(unknown)}")

        missing = sorted([name for name in required if name not in args])
        if missing:
            raise ToolValidationError(f"{tool.name}: missing required arguments: {', '.join(missing)}")

        normalized: Dict[str, Any] = {}

        for name, prop_schema in properties.items():
            if name in args:
                value = args[name]
            elif "default" in prop_schema:
                value = prop_schema["default"]
            else:
                continue

            self._validate_value(name=name, value=value, schema=prop_schema)
            normalized[name] = value

        if allow_extra:
            for name, value in args.items():
                if name not in normalized:
                    normalized[name] = value

        return normalized

    def _validate_value(self, name: str, value: Any, schema: Dict[str, Any]) -> None:
        expected_type = schema.get("type")
        if expected_type == "string":
            if not isinstance(value, str):
                raise ToolValidationError(f"{name}: expected string")
        elif expected_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ToolValidationError(f"{name}: expected integer")
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            if minimum is not None and value < minimum:
                raise ToolValidationError(f"{name}: must be >= {minimum}")
            if maximum is not None and value > maximum:
                raise ToolValidationError(f"{name}: must be <= {maximum}")
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                raise ToolValidationError(f"{name}: expected boolean")
        elif expected_type == "array":
            if not isinstance(value, list):
                raise ToolValidationError(f"{name}: expected array")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for idx, item in enumerate(value):
                    self._validate_value(name=f"{name}[{idx}]", value=item, schema=item_schema)
        elif expected_type == "object":
            if not isinstance(value, dict):
                raise ToolValidationError(f"{name}: expected object")

        enum = schema.get("enum")
        if enum is not None and value not in enum:
            raise ToolValidationError(f"{name}: must be one of {enum}")

    def _get_scoped_snapshot(self, scope: str, builder) -> Dict[str, Any]:
        warm_cache = get_warm_cache_service()
        snapshot = warm_cache.get_or_build(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            scope=scope,
            builder=builder,
        )
        return snapshot

    def _from_warm_snapshot(self, context_type: str, limit: int) -> List[Dict[str, Any]]:
        snapshot = self._get_scoped_snapshot(
            scope="profile",
            builder=lambda: build_profile_snapshot(self.db, self.user_id),
        )
        by_type = snapshot.get("by_type", {})
        result = list(by_type.get(context_type, []))[: max(1, min(limit, 10))]
        logger.info(
            "context_tool_snapshot tenant=%s user=%s session=%s scope=%s type=%s entries=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            "profile",
            context_type,
            len(result),
        )
        return result

    def _merge_hot(self, entries: List[Dict[str, Any]]) -> None:
        hot_cache = get_hot_context_cache_service()
        hot_cache.merge_context_entries(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=self.session_id,
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
            return row.email.lower() if row and row.email else email_norm

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

        row = (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                Contact.name.ilike(f"%{candidate_name}%"),
            )
            .order_by(Contact.updated_at.desc())
            .first()
        )
        if row and row.email:
            return row.email.lower()
        return None

    def _resolve_entity_ref(
        self,
        entity_type: str,
        identifier: Optional[str],
    ) -> Optional[str]:
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

        partial = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == entity_type,
                or_(
                    EntityReference.display_name.ilike(f"%{query}%"),
                    EntityReference.ref.ilike(f"%{query}%"),
                ),
            )
            .order_by(EntityReference.updated_at.desc())
            .first()
        )
        if partial:
            return partial.ref
        return query

    def _get_contact_context(
        self,
        contact: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 5,
    ) -> ToolResult:
        email_norm = self._resolve_contact_email(contact=contact, email=email, name=name)
        if not email_norm:
            return ToolResult(success=False, error="contact/email/name is required")

        snapshot = self._get_scoped_snapshot(
            scope=f"contact:{email_norm}",
            builder=lambda: build_contact_snapshot(self.db, self.user_id, email_norm),
        )
        by_type = snapshot.get("by_type", {}) or {}
        filtered = list(by_type.get("relationships", []))[: max(1, min(limit, 10))]

        if not filtered:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    ContextEntry.type == "relationships",
                    ContextEntry.entity_type == "contact",
                    or_(
                        ContextEntry.entity_id.ilike(email_norm),
                        ContextEntry.content.ilike(f"%{email_norm}%"),
                    ),
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(max(1, min(limit, 10)))
                .all()
            )
            filtered = [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "created_by": r.created_by,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "importance_level": r.importance_level,
                }
                for r in rows
            ]
            source = "db_fallback"
        else:
            source = "warm_snapshot"

        self._merge_hot(filtered)
        logger.info(
            "context_tool_result tenant=%s user=%s session=%s tool=get_contact_context scope=%s source=%s entries=%s contact=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            f"contact:{email_norm}",
            source,
            len(filtered),
            email_norm,
        )
        return ToolResult(success=True, data={"contact": email_norm, "entries": filtered})

    def _get_thread_history(
        self,
        thread_id: Optional[str] = None,
        thread: Optional[str] = None,
        limit: int = 8,
    ) -> ToolResult:
        thread_norm = self._resolve_entity_ref("thread", thread_id or thread)
        if not thread_norm:
            return ToolResult(success=False, error="thread_id/thread is required")

        snapshot = self._get_scoped_snapshot(
            scope=f"thread:{thread_norm}",
            builder=lambda: build_thread_snapshot(self.db, self.user_id, thread_norm),
        )
        by_type = snapshot.get("by_type", {}) or {}
        items = []
        for type_key in ["decision", "commitment"]:
            items.extend(by_type.get(type_key, []))
        items = items[: max(1, min(limit, 10))]
        source = "warm_snapshot"

        if not items:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    or_(
                        (ContextEntry.entity_type == "thread") & (ContextEntry.entity_id == thread_norm),
                        (ContextEntry.type.in_(["decision", "commitment"])) & (ContextEntry.content.ilike(f"%{thread_norm}%")),
                    ),
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(max(1, min(limit, 10)))
                .all()
            )
            items = [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "created_by": r.created_by,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "importance_level": r.importance_level,
                }
                for r in rows
            ]
            source = "db_fallback"

        self._merge_hot(items)
        logger.info(
            "context_tool_result tenant=%s user=%s session=%s tool=get_thread_history scope=%s source=%s entries=%s thread_id=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            f"thread:{thread_norm}",
            source,
            len(items),
            thread_norm,
        )
        return ToolResult(success=True, data={"thread_id": thread_norm, "entries": items})

    def _get_user_preferences(self, category: str = "general", limit: int = 5) -> ToolResult:
        preferences = self._from_warm_snapshot("preferences", limit=max(1, min(limit, 10)))

        if category and category != "general":
            cat = category.lower().strip()
            filtered = [p for p in preferences if _preference_matches_category(p, cat)]
        else:
            filtered = preferences

        self._merge_hot(filtered)
        logger.info(
            "context_tool_result tenant=%s user=%s session=%s tool=get_user_preferences source=warm_snapshot entries=%s category=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            len(filtered),
            category,
        )
        return ToolResult(success=True, data={"category": category, "entries": filtered})

    def _get_event_context(
        self,
        event_id: Optional[str] = None,
        event: Optional[str] = None,
        limit: int = 8,
    ) -> ToolResult:
        event_norm = self._resolve_entity_ref("event", event_id or event)
        if not event_norm:
            return ToolResult(success=False, error="event_id/event is required")

        snapshot = self._get_scoped_snapshot(
            scope=f"event:{event_norm}",
            builder=lambda: build_event_snapshot(self.db, self.user_id, event_norm),
        )
        by_type = snapshot.get("by_type", {}) or {}
        items = []
        for type_key in ["decision", "commitment", "insight", "relationships"]:
            items.extend(by_type.get(type_key, []))
        items = items[: max(1, min(limit, 10))]
        source = "warm_snapshot"

        if not items:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    (ContextEntry.entity_type == "event") & (ContextEntry.entity_id == event_norm),
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(max(1, min(limit, 10)))
                .all()
            )
            items = [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "created_by": r.created_by,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "importance_level": r.importance_level,
                }
                for r in rows
            ]
            source = "db_fallback"

        self._merge_hot(items)
        logger.info(
            "context_tool_result tenant=%s user=%s session=%s tool=get_event_context scope=%s source=%s entries=%s event_id=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            f"event:{event_norm}",
            source,
            len(items),
            event_norm,
        )
        return ToolResult(success=True, data={"event_id": event_norm, "entries": items})

    def _get_message_context(
        self,
        message_id: Optional[str] = None,
        message: Optional[str] = None,
        limit: int = 8,
    ) -> ToolResult:
        message_norm = self._resolve_entity_ref("message", message_id or message)
        if not message_norm:
            return ToolResult(success=False, error="message_id/message is required")

        snapshot = self._get_scoped_snapshot(
            scope=f"message:{message_norm}",
            builder=lambda: build_message_snapshot(self.db, self.user_id, message_norm),
        )
        by_type = snapshot.get("by_type", {}) or {}
        items = []
        for type_key in ["commitment", "decision", "insight", "relationships", "preferences"]:
            items.extend(by_type.get(type_key, []))
        items = items[: max(1, min(limit, 10))]
        source = "warm_snapshot"

        if not items:
            rows = (
                self.db.query(ContextEntry)
                .filter(
                    ContextEntry.user_id == self.user_id,
                    (ContextEntry.entity_type == "message") & (ContextEntry.entity_id == message_norm),
                )
                .order_by(ContextEntry.created_at.desc())
                .limit(max(1, min(limit, 10)))
                .all()
            )
            items = [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "created_by": r.created_by,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "importance_level": r.importance_level,
                }
                for r in rows
            ]
            source = "db_fallback"

        self._merge_hot(items)
        logger.info(
            "context_tool_result tenant=%s user=%s session=%s tool=get_message_context scope=%s source=%s entries=%s message_id=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            f"message:{message_norm}",
            source,
            len(items),
            message_norm,
        )
        return ToolResult(success=True, data={"message_id": message_norm, "entries": items})

    def _draft_email(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str] = None,
        sender_name: Optional[str] = None,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        thread: Optional[str] = None,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        service = EmailDraftingService(db=self.db, user_id=self.user_id)
        draft = service.draft(
            subject=subject,
            intent=intent,
            recipient=recipient,
            sender_name=sender_name,
            thread_id=thread_id,
            message_id=message_id,
            thread=thread,
            message=message,
            context=context,
        )
        logger.info(
            "action_tool_result tenant=%s user=%s session=%s tool=draft_email subject=%s thread_id=%s message_id=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            subject,
            draft.get("thread_id"),
            draft.get("message_id"),
        )
        return ToolResult(success=True, data=draft)

    def _generate_meeting_brief(
        self,
        event_id: Optional[str] = None,
        meeting_subject: Optional[str] = None,
        participant_ids: Optional[List[str]] = None,
        include_recent_context: bool = True,
    ) -> ToolResult:
        if not (event_id or meeting_subject):
            return ToolResult(success=False, error="event_id or meeting_subject is required")

        service = MeetingBriefService(db=self.db, user_id=self.user_id)
        brief = service.build_brief(
            event_id=event_id,
            meeting_subject=meeting_subject,
            participant_ids=participant_ids,
            include_recent_context=include_recent_context,
        )
        logger.info(
            "action_tool_result tenant=%s user=%s session=%s tool=generate_meeting_brief event_id=%s meeting_subject=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            event_id,
            meeting_subject,
        )
        return ToolResult(success=True, data=brief)

    def _generate_thread_intelligence(
        self,
        thread_id: Optional[str] = None,
        thread: Optional[str] = None,
    ) -> ToolResult:
        thread_norm = self._resolve_entity_ref("thread", thread_id or thread)
        if not thread_norm:
            return ToolResult(success=False, error="thread_id/thread is required")
        service = ThreadIntelligenceService(db=self.db, user_id=self.user_id)
        intelligence = service.analyze(thread_id=thread_norm)
        logger.info(
            "action_tool_result tenant=%s user=%s session=%s tool=generate_thread_intelligence thread_id=%s",
            self.tenant_id,
            self.user_id,
            self.session_id,
            thread_norm,
        )
        return ToolResult(success=True, data=intelligence)


def _preference_matches_category(item: Dict[str, Any], category: str) -> bool:
    content = (item.get("content") or "").lower()
    if not content:
        return False

    if category == "general":
        return True
    if category == "tone":
        return any(token in content for token in {"tone", "voice", "style", "wording", "framing"})
    if category == "scheduling":
        return any(token in content for token in {"schedule", "meeting", "calendar", "availability", "time slot"})
    if category == "working_hours":
        return any(token in content for token in {"working hours", "hours", "morning", "afternoon", "timezone"})
    return category in content
