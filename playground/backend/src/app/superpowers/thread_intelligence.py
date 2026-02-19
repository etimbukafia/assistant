"""Thread intelligence action tool for playground inbox."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.data.models import ContextEntry, InboxMessage, InboxThread


class ThreadIntelligenceService:
    """Builds structured thread intelligence from inbox + context entries."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def analyze(self, thread_id: str) -> Dict[str, Any]:
        thread = (
            self.db.query(InboxThread)
            .filter(InboxThread.user_id == self.user_id, InboxThread.thread_id == thread_id)
            .first()
        )
        if not thread:
            return {
                "thread_id": thread_id,
                "summary": "Thread not found.",
                "needs_reply": False,
                "action_points": [],
                "decisions": [],
                "commitments": [],
                "risks": [],
                "participants": [],
                "message_count": 0,
                "latest_message_id": None,
                "context_entries": [],
            }

        messages = (
            self.db.query(InboxMessage)
            .filter(
                InboxMessage.user_id == self.user_id,
                InboxMessage.thread_id == thread_id,
            )
            .order_by(InboxMessage.sent_at.asc())
            .all()
        )
        message_ids = [m.message_id for m in messages]
        message_senders = [m.sender for m in messages if m.sender]

        context_entries = (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                or_(
                    (ContextEntry.entity_type == "thread") & (ContextEntry.entity_id == thread_id),
                    (ContextEntry.entity_type == "message") & (ContextEntry.entity_id.in_(message_ids if message_ids else [""])),
                ),
            )
            .order_by(ContextEntry.importance_level.desc(), ContextEntry.created_at.desc())
            .limit(40)
            .all()
        )

        decisions = [entry.content for entry in context_entries if entry.type == "decision"][:6]
        commitments = [entry.content for entry in context_entries if entry.type == "commitment"][:6]
        risks = [entry.content for entry in context_entries if entry.type == "insight"][:6]
        relationships = [entry.content for entry in context_entries if entry.type == "relationships"][:4]

        action_points = []
        action_points.extend(commitments[:3])
        action_points.extend(risks[:2])
        if not action_points and thread.snippet:
            action_points.append(thread.snippet)

        latest = messages[-1] if messages else None
        needs_reply = bool(latest and latest.direction == "inbound" and latest.needs_reply == 1 and thread.status != "closed")

        summary = self._summary(
            subject=thread.subject,
            needs_reply=needs_reply,
            decisions=decisions,
            commitments=commitments,
            risks=risks,
            relationships=relationships,
            message_count=len(messages),
        )

        participants = self._participants(messages)

        return {
            "thread_id": thread.thread_id,
            "subject": thread.subject,
            "summary": summary,
            "needs_reply": needs_reply,
            "action_points": action_points,
            "decisions": decisions,
            "commitments": commitments,
            "risks": risks,
            "relationships": relationships,
            "participants": participants,
            "message_count": len(messages),
            "latest_message_id": latest.message_id if latest else None,
            "latest_message_at": latest.sent_at.isoformat() if latest and latest.sent_at else None,
            "context_entries": [
                {
                    "id": entry.id,
                    "type": entry.type,
                    "content": entry.content,
                    "entity_type": entry.entity_type,
                    "entity_id": entry.entity_id,
                    "importance_level": entry.importance_level,
                }
                for entry in context_entries[:20]
            ],
            "quick_actions": [
                "draft_reply",
                "mark_done",
                "archive_thread",
            ],
            "sender_hints": list(OrderedDict.fromkeys(message_senders)),
        }

    def _participants(self, messages: List[InboxMessage]) -> List[str]:
        values: List[str] = []
        for message in messages:
            if message.sender:
                values.append(message.sender.strip())
            for recipient in (message.recipients or "").split(","):
                cleaned = recipient.strip()
                if cleaned:
                    values.append(cleaned)
        return list(OrderedDict.fromkeys(values))

    def _summary(
        self,
        subject: str,
        needs_reply: bool,
        decisions: List[str],
        commitments: List[str],
        risks: List[str],
        relationships: List[str],
        message_count: int,
    ) -> str:
        fragments = [f"{subject}: {message_count} messages"]
        if needs_reply:
            fragments.append("reply needed")
        if decisions:
            fragments.append(f"{len(decisions)} decisions")
        if commitments:
            fragments.append(f"{len(commitments)} commitments")
        if risks:
            fragments.append(f"{len(risks)} risks")
        if relationships:
            fragments.append("relationship context available")
        return ", ".join(fragments) + "."
