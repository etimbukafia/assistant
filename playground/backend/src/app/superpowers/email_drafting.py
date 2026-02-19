"""Email drafting action tool implementation for playground."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.genai import types as genai_types
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, EntityReference, InboxMessage, InboxThread
from app.services.genai_client import get_client


logger = logging.getLogger(__name__)


class EmailDraftingService:
    """Drafts emails from thread/message context and user preferences."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def draft(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str] = None,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        thread: Optional[str] = None,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        thread_ref = self._resolve_thread_ref(thread_id or thread)
        message_ref = self._resolve_message_ref(message_id or message)
        recipient_email = self._resolve_recipient(recipient)

        from_context = context or {}
        if not thread_ref:
            thread_ref = self._resolve_thread_ref(from_context.get("thread_id"))
        if not message_ref:
            message_ref = self._resolve_message_ref(from_context.get("message_id"))
        if not recipient_email:
            recipient_email = self._resolve_recipient(from_context.get("recipient"))
        if thread_ref and not message_ref:
            latest = (
                self.db.query(InboxMessage)
                .filter(InboxMessage.user_id == self.user_id, InboxMessage.thread_id == thread_ref)
                .order_by(InboxMessage.sent_at.desc())
                .first()
            )
            if latest:
                message_ref = latest.message_id
        if message_ref and not thread_ref:
            msg = (
                self.db.query(InboxMessage)
                .filter(InboxMessage.user_id == self.user_id, InboxMessage.message_id == message_ref)
                .first()
            )
            if msg:
                thread_ref = msg.thread_id

        thread_entries = self._query_entries("thread", thread_ref, limit=8, only_active=True, recent_hours=24) if thread_ref else []
        message_entries = self._query_entries("message", message_ref, limit=6, only_active=True, recent_hours=24) if message_ref else []
        contact_entries = (
            self._query_entries(
                "contact",
                recipient_email,
                limit=4,
                allowed_types={"preferences"},
                only_active=True,
            )
            if recipient_email
            else []
        )
        assistant_preferences = self._query_profile_preferences("assistant", limit=5)
        executive_preferences = self._query_profile_preferences("executive", limit=5)

        context_lines = self._build_context_lines(
            thread_entries=thread_entries,
            message_entries=message_entries,
            contact_entries=contact_entries,
            assistant_preferences=assistant_preferences,
            executive_preferences=executive_preferences,
        )
        source_message = self._resolve_source_message(thread_ref=thread_ref, message_ref=message_ref)
        body = self._generate_draft_body(
            subject=subject,
            intent=intent,
            recipient=recipient_email,
            context_lines=context_lines,
            source_message=source_message,
        )

        return {
            "subject": subject,
            "intent": intent,
            "recipient": recipient_email,
            "thread_id": thread_ref,
            "message_id": message_ref,
            "body": body,
            "context_entries": context_lines,
        }

    def _resolve_source_message(
        self,
        thread_ref: Optional[str],
        message_ref: Optional[str],
    ) -> Optional[InboxMessage]:
        if message_ref:
            msg = (
                self.db.query(InboxMessage)
                .filter(
                    InboxMessage.user_id == self.user_id,
                    InboxMessage.message_id == message_ref,
                )
                .first()
            )
            if msg:
                return msg

        if thread_ref:
            return (
                self.db.query(InboxMessage)
                .filter(
                    InboxMessage.user_id == self.user_id,
                    InboxMessage.thread_id == thread_ref,
                )
                .order_by(InboxMessage.sent_at.desc())
                .first()
            )
        return None

    def _generate_draft_body(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        context_lines: List[Dict[str, Any]],
        source_message: Optional[InboxMessage],
    ) -> str:
        client = get_client()
        if client is None:
            logger.warning("email_draft_llm_unavailable user=%s reason=missing_google_api_key", self.user_id)
            return self._render_draft_body(
                subject=subject,
                intent=intent,
                recipient=recipient,
                context_lines=context_lines,
            )

        model_name = os.getenv("PLAYGROUND_EMAIL_DRAFT_MODEL", "gemini-2.5-flash-lite")
        prompt = self._build_llm_prompt(
            subject=subject,
            intent=intent,
            recipient=recipient,
            context_lines=context_lines,
            source_message=source_message,
        )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt)])],
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=360,
                    temperature=0.4,
                    system_instruction=(
                        "You draft concise executive-assistant emails. "
                        "Return plain email body only. No markdown. No explanations."
                    ),
                ),
            )
            text = (response.text or "").strip()
            if text:
                return text
            logger.warning("email_draft_llm_empty user=%s model=%s", self.user_id, model_name)
        except Exception:
            logger.exception("email_draft_llm_failed user=%s model=%s", self.user_id, model_name)

        return self._render_draft_body(
            subject=subject,
            intent=intent,
            recipient=recipient,
            context_lines=context_lines,
        )

    def _build_llm_prompt(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        context_lines: List[Dict[str, Any]],
        source_message: Optional[InboxMessage],
    ) -> str:
        recipient_hint = recipient or "unknown recipient"
        source_block = "[none]"
        if source_message:
            source_block = (
                f"From: {source_message.sender}\n"
                f"Subject: {source_message.subject}\n"
                f"Preview: {(source_message.body_preview or '').strip()}"
            )
        structured_context = [
            {
                "type": entry.get("type"),
                "entity_type": entry.get("entity_type"),
                "importance_level": entry.get("importance_level"),
                "content": entry.get("content"),
            }
            for entry in context_lines[:12]
        ]

        return (
            "Draft an email reply.\n\n"
            f"Recipient: {recipient_hint}\n"
            f"Subject: {subject}\n"
            f"Intent: {intent}\n\n"
            "Relevant source message:\n"
            f"{source_block}\n\n"
            "Context memory (highest-signal first):\n"
            f"{structured_context}\n\n"
            "Requirements:\n"
            "- Keep it brief, clear, and human.\n"
            "- Respect preferences/context if provided.\n"
            "- If there is uncertainty, ask one concise clarifying question.\n"
            "- Return only the email body text."
        )

    def _resolve_thread_ref(self, identifier: Optional[str]) -> Optional[str]:
        query = (identifier or "").strip()
        if not query:
            return None

        thread = (
            self.db.query(InboxThread)
            .filter(InboxThread.user_id == self.user_id, InboxThread.thread_id == query)
            .first()
        )
        if thread:
            return thread.thread_id

        thread = (
            self.db.query(InboxThread)
            .filter(InboxThread.user_id == self.user_id, func.lower(InboxThread.subject) == query.lower())
            .first()
        )
        if thread:
            return thread.thread_id

        ref = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "thread",
                func.lower(EntityReference.display_name) == query.lower(),
            )
            .first()
        )
        if ref:
            return ref.ref
        return query

    def _resolve_message_ref(self, identifier: Optional[str]) -> Optional[str]:
        query = (identifier or "").strip()
        if not query:
            return None

        msg = (
            self.db.query(InboxMessage)
            .filter(InboxMessage.user_id == self.user_id, InboxMessage.message_id == query)
            .first()
        )
        if msg:
            return msg.message_id

        msg = (
            self.db.query(InboxMessage)
            .filter(InboxMessage.user_id == self.user_id, func.lower(InboxMessage.subject) == query.lower())
            .order_by(InboxMessage.sent_at.desc())
            .first()
        )
        if msg:
            return msg.message_id

        ref = (
            self.db.query(EntityReference)
            .filter(
                EntityReference.user_id == self.user_id,
                EntityReference.entity_type == "message",
                func.lower(EntityReference.display_name) == query.lower(),
            )
            .first()
        )
        if ref:
            return ref.ref
        return query

    def _resolve_recipient(self, recipient: Optional[str]) -> Optional[str]:
        value = (recipient or "").strip()
        if not value:
            return None
        if "@" in value:
            return value.lower()

        contact = (
            self.db.query(Contact)
            .filter(Contact.user_id == self.user_id, func.lower(Contact.name) == value.lower())
            .first()
        )
        if contact and contact.email:
            return contact.email.lower()
        return value

    def _query_entries(
        self,
        entity_type: str,
        entity_id: Optional[str],
        limit: int,
        allowed_types: Optional[set[str]] = None,
        only_active: bool = False,
        recent_hours: Optional[int] = None,
    ) -> List[ContextEntry]:
        if not entity_id:
            return []
        query = (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type == entity_type,
                ContextEntry.entity_id == entity_id,
            )
        )
        if allowed_types:
            query = query.filter(ContextEntry.type.in_(sorted(allowed_types)))
        if only_active:
            now = datetime.now(timezone.utc)
            query = query.filter(ContextEntry.status == "active")
            query = query.filter(
                (ContextEntry.expires_at.is_(None)) | (ContextEntry.expires_at >= now)
            )
            if recent_hours is not None:
                threshold = now - timedelta(hours=recent_hours)
                query = query.filter(
                    (ContextEntry.created_at >= threshold) | (ContextEntry.expires_at >= now)
                )
        return query.order_by(ContextEntry.created_at.desc()).limit(limit).all()

    def _query_profile_preferences(self, entity_type: str, limit: int) -> List[ContextEntry]:
        return (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type == entity_type,
                ContextEntry.type == "preferences",
                ContextEntry.status == "active",
            )
            .order_by(ContextEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    def _build_context_lines(
        self,
        thread_entries: List[ContextEntry],
        message_entries: List[ContextEntry],
        contact_entries: List[ContextEntry],
        assistant_preferences: List[ContextEntry],
        executive_preferences: List[ContextEntry],
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for entry in (
            thread_entries
            + message_entries
            + contact_entries
            + assistant_preferences
            + executive_preferences
        ):
            results.append(
                {
                    "id": entry.id,
                    "type": entry.type,
                    "entity_type": entry.entity_type,
                    "entity_id": entry.entity_id,
                    "content": entry.content,
                    "importance_level": entry.importance_level,
                    "status": entry.status,
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                }
            )
        return results[:16]

    def _render_draft_body(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        context_lines: List[Dict[str, Any]],
    ) -> str:
        greeting = f"Hi {recipient.split('@')[0].title()}," if recipient and "@" in recipient else "Hi,"
        top_context = [line["content"] for line in context_lines[:3] if line.get("content")]
        context_sentence = " ".join(top_context) if top_context else "Sharing a quick update."

        return (
            f"{greeting}\n\n"
            f"{intent.strip().capitalize()} re: {subject.strip()}.\n"
            f"{context_sentence}\n\n"
            "Please confirm if this works on your side.\n\n"
            "Best,\n"
            "Teeks"
        )
