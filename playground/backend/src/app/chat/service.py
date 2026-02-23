"""Playground chat service with production-like API contracts + stream support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from app.chat.orchestrator import ChatOrchestrator
from app.data.models import ChatMessage, ChatPendingAction, ChatSession, ContextEntry
from app.services.hot_context_cache import get_hot_context_cache_service
from app.services.mention_context import MentionContextService
from app.services.warm_cache import get_warm_cache_service


class ProcessingStatus(str, Enum):
    COMPLETE = "complete"
    PROCESSING = "processing"
    FAILED = "failed"


@dataclass
class ChatResponse:
    status: ProcessingStatus
    message_id: Optional[int] = None
    job_id: Optional[str] = None
    response: Optional[str] = None
    pending_actions: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    timing: Optional[Dict[str, int]] = None


class ChatService:
    """Session/message CRUD and orchestrated send-message flow."""

    def __init__(self, db: Session, user_id: str, tenant_id: str = "default"):
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id

    # =========================================================================
    # Session operations
    # =========================================================================

    def create_session(
        self,
        session_type: str = "command",
        user_first_name: Optional[str] = None,
    ) -> ChatSession:
        now = datetime.utcnow()
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            session_type=(session_type or "command"),
            title=None,
            created_at=now,
            last_activity_at=now,
            state={"user_first_name": user_first_name} if user_first_name else {},
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, limit: int = 20, offset: int = 0) -> Tuple[List[ChatSession], int]:
        q = self.db.query(ChatSession).filter(ChatSession.user_id == self.user_id)
        total = q.count()
        rows = (
            q.order_by(ChatSession.last_activity_at.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return rows, total

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == self.user_id)
            .first()
        )

    def delete_session(self, session_id: str) -> bool:
        row = self.get_session(session_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    # =========================================================================
    # Message + pending action operations
    # =========================================================================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        auto_commit: bool = True,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow(),
            message_metadata=metadata or {},
        )
        self.db.add(message)

        session = self.get_session(session_id)
        if session is not None:
            session.last_activity_at = datetime.utcnow()

        if auto_commit:
            self.db.commit()
            self.db.refresh(message)
        else:
            self.db.flush()
        return message

    def get_messages(self, session_id: str, limit: int = 50, offset: int = 0) -> List[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 500)))
            .all()
        )

    def get_pending_actions(self, session_id: str) -> List[ChatPendingAction]:
        return (
            self.db.query(ChatPendingAction)
            .filter(
                ChatPendingAction.session_id == session_id,
                ChatPendingAction.status == "pending",
            )
            .order_by(ChatPendingAction.created_at.asc())
            .all()
        )

    def get_pending_actions_for_message(self, message_id: int) -> List[ChatPendingAction]:
        return (
            self.db.query(ChatPendingAction)
            .filter(ChatPendingAction.message_id == message_id, ChatPendingAction.status == "pending")
            .order_by(ChatPendingAction.created_at.asc())
            .all()
        )

    # =========================================================================
    # Send message (sync)
    # =========================================================================

    async def send_message(
        self,
        session_id: str,
        content: str,
        mentions: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResponse:
        session = self.get_session(session_id)
        if not session:
            return ChatResponse(status=ProcessingStatus.FAILED, error="Session not found")

        mention_context = self._resolve_mentions(mentions or [], session_id=session_id)

        user_msg = self.add_message(
            session_id=session_id,
            role="user",
            content=content,
            metadata={"mentions": mentions or []},
            auto_commit=False,
        )
        get_hot_context_cache_service().append_message(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=session_id,
            role="user",
            content=content,
        )

        try:
            orchestrator = ChatOrchestrator(
                self.db,
                self.user_id,
                tenant_id=self.tenant_id,
                assistant_name="Teeks",
                user_name=(session.state or {}).get("user_first_name") or "you",
            )
            result = await orchestrator.process_message(
                session=session,
                user_message=content,
                mention_context=mention_context,
            )
        except Exception:
            self.db.rollback()
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error="I couldn't complete that right now. Please try again.",
            )

        assistant_msg = self.add_message(
            session_id=session_id,
            role="assistant",
            content=result.response,
            metadata={
                "tool_outputs": result.tool_outputs,
                "deferred_actions": result.deferred_actions,
                "timing": result.timing,
            },
            auto_commit=False,
        )

        get_hot_context_cache_service().append_message(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=session_id,
            role="assistant",
            content=result.response,
        )
        if result.deferred_actions:
            get_hot_context_cache_service().set_deferred_actions(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                session_id=session_id,
                actions=result.deferred_actions,
                max_items=20,
            )

        pending_rows = self._persist_pending_actions(
            session_id=session_id,
            message_id=assistant_msg.id,
            pending_actions=result.pending_actions,
        )
        self.db.commit()

        return ChatResponse(
            status=ProcessingStatus.COMPLETE,
            message_id=assistant_msg.id,
            response=result.response,
            pending_actions=pending_rows,
            timing=result.timing,
        )

    # =========================================================================
    # Send message (stream)
    # =========================================================================

    async def stream_message(
        self,
        session_id: str,
        content: str,
        mentions: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        session = self.get_session(session_id)
        if not session:
            yield self._stream_event(
                session_id=session_id,
                message_id=None,
                event_type="error",
                payload={"message": "Session not found"},
            )
            return

        mention_context = self._resolve_mentions(mentions or [], session_id=session_id)

        user_msg = self.add_message(
            session_id=session_id,
            role="user",
            content=content,
            metadata={"mentions": mentions or []},
            auto_commit=False,
        )
        self.db.commit()

        get_hot_context_cache_service().append_message(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=session_id,
            role="user",
            content=content,
        )

        queue: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue()

        async def emit_internal(event: Dict[str, Any]) -> None:
            event_type = str(event.get("type") or "state")
            payload = dict(event)
            payload.pop("type", None)
            await queue.put(
                self._stream_event(
                    session_id=session_id,
                    message_id=None,
                    event_type=event_type,
                    payload=payload,
                )
            )

        async def run_orchestration() -> None:
            try:
                orchestrator = ChatOrchestrator(
                    self.db,
                    self.user_id,
                    tenant_id=self.tenant_id,
                    assistant_name="Teeks",
                    user_name=(session.state or {}).get("user_first_name") or "you",
                )
                result = await orchestrator.process_message(
                    session=session,
                    user_message=content,
                    mention_context=mention_context,
                    event_emitter=emit_internal,
                )

                assistant_msg = self.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=result.response,
                    metadata={
                        "tool_outputs": result.tool_outputs,
                        "deferred_actions": result.deferred_actions,
                        "timing": result.timing,
                    },
                    auto_commit=False,
                )

                get_hot_context_cache_service().append_message(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    session_id=session_id,
                    role="assistant",
                    content=result.response,
                )
                if result.deferred_actions:
                    get_hot_context_cache_service().set_deferred_actions(
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        session_id=session_id,
                        actions=result.deferred_actions,
                        max_items=20,
                    )

                pending_rows = self._persist_pending_actions(
                    session_id=session_id,
                    message_id=assistant_msg.id,
                    pending_actions=result.pending_actions,
                )
                self.db.commit()

                await queue.put(
                    self._stream_event(
                        session_id=session_id,
                        message_id=assistant_msg.id,
                        event_type="complete",
                        payload={
                            "response": result.response,
                            "pending_actions": pending_rows,
                            "timing": result.timing,
                        },
                    )
                )
            except Exception:
                self.db.rollback()
                await queue.put(
                    self._stream_event(
                        session_id=session_id,
                        message_id=None,
                        event_type="error",
                        payload={"message": "I couldn't complete that right now. Please try again."},
                    )
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_orchestration())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            await task

    # =========================================================================
    # Jobs + approvals
    # =========================================================================

    def get_job_status(self, job_id: str) -> ChatResponse:
        return ChatResponse(
            status=ProcessingStatus.FAILED,
            job_id=job_id,
            error="Job not found",
        )

    def approve_action(self, action_id: str) -> Dict[str, Any]:
        action = (
            self.db.query(ChatPendingAction)
            .join(ChatSession, ChatPendingAction.session_id == ChatSession.id)
            .filter(ChatPendingAction.id == action_id, ChatSession.user_id == self.user_id)
            .first()
        )
        if not action:
            return {"success": False, "error": "Action not found"}
        action.status = "approved"
        self.db.commit()
        return {"success": True, "action_id": action_id}

    def reject_action(self, action_id: str) -> Dict[str, Any]:
        action = (
            self.db.query(ChatPendingAction)
            .join(ChatSession, ChatPendingAction.session_id == ChatSession.id)
            .filter(ChatPendingAction.id == action_id, ChatSession.user_id == self.user_id)
            .first()
        )
        if not action:
            return {"success": False, "error": "Action not found"}
        action.status = "rejected"
        self.db.commit()
        return {"success": True, "action_id": action_id}

    # =========================================================================
    # Internals
    # =========================================================================

    def _resolve_mentions(self, mentions: List[Dict[str, Any]], session_id: str) -> Dict[str, Any]:
        entity_mentions: List[Dict[str, str]] = []
        memory_entries: List[Dict[str, Any]] = []
        entities: List[Dict[str, Any]] = []

        for mention in mentions or []:
            kind = str(mention.get("kind") or mention.get("type") or "").strip().lower()
            ref = str(mention.get("ref") or "").strip()
            label = str(mention.get("label") or ref).strip()
            if not kind or not ref:
                continue

            if kind == "memory":
                entry_id = None
                if ref.startswith("memory:") and ref.split(":", 1)[1].isdigit():
                    entry_id = int(ref.split(":", 1)[1])
                elif ref.isdigit():
                    entry_id = int(ref)
                if entry_id:
                    row = (
                        self.db.query(ContextEntry)
                        .filter(ContextEntry.id == entry_id, ContextEntry.user_id == self.user_id)
                        .first()
                    )
                    if row:
                        memory_entries.append(
                            {
                                "id": row.id,
                                "type": row.type,
                                "content": row.content,
                                "entity_type": row.entity_type,
                                "entity_id": row.entity_id,
                                "created_by": row.created_by,
                                "created_at": row.created_at.isoformat() if row.created_at else None,
                                "importance_level": row.importance_level,
                                "status": row.status,
                            }
                        )
                continue

            if kind in {"contact", "thread", "event", "message"}:
                entity_mentions.append({"kind": kind, "ref": ref, "label": label})
                entities.append({"kind": kind, "ref": ref, "label": label})

        mention_service = MentionContextService(
            db=self.db,
            warm_cache=get_warm_cache_service(),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            session_id=session_id,
        )
        mention_prefetch = mention_service.prefetch_for_mentions(entity_mentions) if entity_mentions else {
            "resolved_mentions": [],
            "unresolved_mentions": [],
            "entities": [],
            "selected_entries": [],
        }
        selected_entries = list(mention_prefetch.get("selected_entries", [])) + memory_entries
        if selected_entries:
            get_hot_context_cache_service().merge_context_entries(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                session_id=session_id,
                entries=selected_entries,
            )

        return {
            "contacts": [],
            "emails": [],
            "knowledge": [],
            "memory": memory_entries,
            "entities": entities,
            "selected_entries": selected_entries,
            "mention_prefetch": mention_prefetch,
        }

    def _persist_pending_actions(
        self,
        session_id: str,
        message_id: int,
        pending_actions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for action in pending_actions or []:
            row = ChatPendingAction(
                id=str(uuid.uuid4()),
                session_id=session_id,
                message_id=message_id,
                action_type=str(action.get("action_type") or "action"),
                action_data=dict(action.get("action_data") or {}),
                status="pending",
                created_at=datetime.utcnow(),
            )
            self.db.add(row)
            self.db.flush()
            out.append(
                {
                    "id": row.id,
                    "action_type": row.action_type,
                    "action_data": row.action_data,
                    "status": row.status,
                    "message_id": row.message_id,
                }
            )
        return out

    def _stream_event(
        self,
        session_id: str,
        message_id: Optional[int],
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "event_id": str(uuid.uuid4()),
            "session_id": session_id,
            "message_id": message_id,
            "type": event_type,
            "payload": payload,
            "ts": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def format_sse(event: Dict[str, Any]) -> str:
        event_type = str(event.get("type") or "message")
        payload = json.dumps(event, ensure_ascii=False)
        return f"event: {event_type}\ndata: {payload}\n\n"
