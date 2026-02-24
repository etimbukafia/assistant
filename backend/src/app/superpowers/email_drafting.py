"""Email drafting action service backed by Gemini."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.genai import types as genai_types
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.data.models import Contact, ContextEntry, EntityReference, Message
from app.services.genai_client import get_genai_client


logger = logging.getLogger(__name__)


class EmailDraftingService:
    """Draft reply emails using scoped context and preference memory."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def draft(
        self,
        subject: str,
        intent: str = "",
        recipient: Optional[str] = None,
        sender_name: Optional[str] = None,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        thread: Optional[str] = None,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_request: Optional[str] = None,
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
        if not sender_name:
            sender_name = (from_context.get("sender_name") or "").strip() or None

        source_message = self._resolve_source_message(thread_ref=thread_ref, message_ref=message_ref)
        if source_message and not thread_ref:
            thread_ref = source_message.thread_id
        if source_message and not message_ref:
            message_ref = str(source_message.id)

        intent_text = (intent or "").strip()
        if not intent_text:
            intent_text = self._infer_intent(source_message=source_message, subject=subject)

        thread_entries = self._query_entries("thread", thread_ref, limit=8)
        message_entries = self._query_entries("message", message_ref, limit=6)
        contact_entries = (
            self._query_entries("contact", recipient_email, limit=4, allowed_types={"preferences"})
            if recipient_email else []
        )
        assistant_preferences = self._query_profile_preferences("assistant", limit=5)
        executive_preferences = self._query_profile_preferences("executive", limit=5)
        awareness_entries = self._query_recent_awareness_entries(thread_ref=thread_ref, message_ref=message_ref)

        context_lines = self._build_context_lines(
            thread_entries=thread_entries,
            message_entries=message_entries,
            contact_entries=contact_entries,
            assistant_preferences=assistant_preferences,
            executive_preferences=executive_preferences,
            awareness_entries=awareness_entries,
        )
        body = self._generate_draft_body(
            subject=subject,
            intent=intent_text,
            recipient=recipient_email,
            sender_name=sender_name,
            context_lines=context_lines,
            source_message=source_message,
            user_request=user_request,
        )
        return {
            "subject": subject,
            "intent": intent_text,
            "recipient": recipient_email,
            "sender_name": sender_name,
            "thread_id": thread_ref,
            "message_id": message_ref,
            "body": body,
            "context_entries": context_lines,
        }

    def _infer_intent(self, source_message: Optional[Message], subject: str) -> str:
        if source_message and (source_message.sender or "").strip():
            return "reply with a clear availability update and next step"
        if "availability" in (subject or "").lower():
            return "share availability update concisely"
        return "send a concise, helpful update"

    def _resolve_source_message(self, thread_ref: Optional[str], message_ref: Optional[str]) -> Optional[Message]:
        if message_ref:
            if message_ref.startswith("msg:"):
                message_ref = message_ref.split(":", 1)[1]
            msg = (
                self.db.query(Message)
                .filter(Message.user_id == self.user_id, Message.id == int(message_ref))
                .first()
                if str(message_ref).isdigit()
                else self.db.query(Message).filter(Message.user_id == self.user_id, Message.message_id == message_ref).first()
            )
            if msg:
                return msg
        if thread_ref:
            return (
                self.db.query(Message)
                .filter(Message.user_id == self.user_id, Message.thread_id == thread_ref)
                .order_by(Message.received_at.desc())
                .first()
            )
        return None

    def _generate_draft_body(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        sender_name: Optional[str],
        context_lines: List[Dict[str, Any]],
        source_message: Optional[Message],
        user_request: Optional[str] = None,
    ) -> str:
        client = get_genai_client()
        if client is None:
            return self._fallback_body(subject, intent, recipient, sender_name, context_lines)

        model_name = os.getenv("PLAYGROUND_EMAIL_DRAFT_MODEL", "gemini-2.5-flash-lite")
        prompt = self._build_llm_prompt(
            subject=subject,
            intent=intent,
            recipient=recipient,
            sender_name=sender_name,
            context_lines=context_lines,
            source_message=source_message,
            user_request=user_request,
        )
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=prompt)])],
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=380,
                    temperature=0.4,
                    system_instruction=(
                        "You draft concise executive-assistant emails. "
                        "Return plain email body only. No markdown. No explanations. "
                        "Never use placeholders like [Your Name]."
                    ),
                ),
            )
            text = self._sanitize_email_text((response.text or "").strip(), sender_name=sender_name)
            if text and self._covers_request(user_request, text):
                return text
            if user_request:
                retry_prompt = self._build_llm_prompt(
                    subject=subject,
                    intent=intent,
                    recipient=recipient,
                    sender_name=sender_name,
                    context_lines=context_lines,
                    source_message=source_message,
                    user_request=user_request,
                    missing_only=True,
                )
                retry = client.models.generate_content(
                    model=model_name,
                    contents=[genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=retry_prompt)])],
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=380,
                        temperature=0.3,
                        system_instruction=(
                            "You draft concise executive-assistant emails. "
                            "Return plain email body only. No markdown. No explanations. "
                            "Never use placeholders like [Your Name]."
                        ),
                    ),
                )
                retry_text = self._sanitize_email_text((retry.text or "").strip(), sender_name=sender_name)
                if retry_text and self._covers_request(user_request, retry_text):
                    return retry_text
                if retry_text:
                    return retry_text
        except Exception:
            logger.exception("email_draft_generation_failed user=%s", self.user_id)

        return self._fallback_body(subject, intent, recipient, sender_name, context_lines)

    def _build_llm_prompt(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        sender_name: Optional[str],
        context_lines: List[Dict[str, Any]],
        source_message: Optional[Message],
        user_request: Optional[str] = None,
        missing_only: bool = False,
    ) -> str:
        recipient_hint = recipient or "unknown recipient"
        recipient_note = "" if recipient else "Recipient unresolved; keep greeting generic and avoid naming."
        source_block = "[none]"
        if source_message:
            source_block = (
                f"From: {source_message.sender or ''}\n"
                f"Subject: {source_message.subject or ''}\n"
                f"Preview: {(source_message.decrypted_body or source_message.body or '')[:700]}"
            )
        structured_context = [
            {
                "type": entry.get("type"),
                "entity_type": entry.get("entity_type"),
                "importance_level": entry.get("importance_level"),
                "status": entry.get("status"),
                "expires_at": entry.get("expires_at"),
                "content": entry.get("content"),
            }
            for entry in context_lines[:14]
        ]
        required_points = self._extract_required_points(user_request)
        missing_points = required_points if not missing_only else [p for p in required_points if p]
        return (
            "Draft an email reply.\n\n"
            f"Recipient: {recipient_hint}\n"
            f"{recipient_note}\n"
            f"Sender name: {sender_name or '[none]'}\n"
            f"Subject: {subject}\n"
            f"Intent: {intent}\n\n"
            "Relevant source message:\n"
            f"{source_block}\n\n"
            "Context memory (highest-signal first):\n"
            f"{structured_context}\n\n"
            "Requirements:\n"
            "- Keep it brief, clear, and human.\n"
            "- Respect assistant, executive, and contact preferences.\n"
            "- Treat resolved/stale/archived items as historical context only.\n"
            "- Never output placeholders such as [Your Name].\n"
            "- If sender name is provided, use it in the sign-off.\n"
            "- Return only the email body text.\n"
            + (
                ""
                if not required_points
                else "- Explicitly cover these user-stated points:\n"
                     + "\n".join(f"  • {p}" for p in required_points)
            )
            + (
                ""
                if not (missing_only and missing_points)
                else "\n- Missing coverage in the previous draft; include these explicitly now:\n"
                     + "\n".join(f"  • {p}" for p in missing_points)
            )
        )

    def _resolve_thread_ref(self, identifier: Optional[str]) -> Optional[str]:
        query = (identifier or "").strip()
        if not query:
            return None

        by_ref = self.db.query(EntityReference).filter(
            EntityReference.user_id == self.user_id,
            EntityReference.entity_type == "thread",
            EntityReference.ref == query,
        ).first()
        if by_ref:
            return by_ref.ref

        by_name = self.db.query(EntityReference).filter(
            EntityReference.user_id == self.user_id,
            EntityReference.entity_type == "thread",
            func.lower(EntityReference.display_name) == query.lower(),
        ).first()
        if by_name:
            return by_name.ref

        msg = (
            self.db.query(Message)
            .filter(Message.user_id == self.user_id, Message.subject.ilike(f"%{query}%"))
            .order_by(Message.received_at.desc())
            .first()
        )
        return msg.thread_id if msg else query

    def _resolve_message_ref(self, identifier: Optional[str]) -> Optional[str]:
        query = (identifier or "").strip()
        if not query:
            return None
        if query.startswith("msg:"):
            query = query.split(":", 1)[1]
        if query.isdigit():
            return query

        by_ref = self.db.query(EntityReference).filter(
            EntityReference.user_id == self.user_id,
            EntityReference.entity_type == "message",
            EntityReference.ref == query,
        ).first()
        if by_ref:
            return by_ref.ref

        by_name = self.db.query(EntityReference).filter(
            EntityReference.user_id == self.user_id,
            EntityReference.entity_type == "message",
            func.lower(EntityReference.display_name) == query.lower(),
        ).first()
        if by_name:
            return by_name.ref
        return query

    # --- Request coverage helpers -------------------------------------------------

    def _extract_required_points(self, user_request: Optional[str]) -> List[str]:
        if not user_request:
            return []
        text = " ".join(user_request.split())
        raw_parts: List[str] = []
        for chunk in re.split(r"[.;]| and | AND ", text):
            chunk = chunk.strip(" -,:")
            if len(chunk) >= 8:
                raw_parts.append(chunk)
        parts = []
        for part in raw_parts:
            if len(parts) >= 6:
                break
            parts.append(part[:160])
        return parts

    def _covers_request(self, user_request: Optional[str], body: str) -> bool:
        if not user_request:
            return True
        body_l = body.lower()
        for phrase in self._extract_required_points(user_request):
            if phrase.lower() not in body_l:
                return False
        return True

    def _resolve_recipient(self, recipient: Optional[str]) -> Optional[str]:
        value = (recipient or "").strip()
        if not value:
            return None
        if "@" in value:
            return value.lower()
        contact = self.db.query(Contact).filter(
            Contact.user_id == self.user_id,
            func.lower(Contact.name) == value.lower(),
        ).first()
        return (contact.email or "").lower() if contact and contact.email else value

    def _query_entries(
        self,
        entity_type: str,
        entity_id: Optional[str],
        limit: int,
        allowed_types: Optional[set[str]] = None,
    ) -> List[ContextEntry]:
        if not entity_id:
            return []
        now = datetime.now(timezone.utc)
        query = self.db.query(ContextEntry).filter(
            ContextEntry.user_id == self.user_id,
            ContextEntry.entity_type == entity_type,
            ContextEntry.entity_id == entity_id,
            ContextEntry.status == "active",
            or_(ContextEntry.expires_at.is_(None), ContextEntry.expires_at >= now),  # type: ignore[name-defined]
        )
        if allowed_types:
            query = query.filter(ContextEntry.type.in_(sorted(allowed_types)))
        return query.order_by(ContextEntry.created_at.desc()).limit(limit).all()

    def _query_profile_preferences(self, entity_type: str, limit: int) -> List[ContextEntry]:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(ContextEntry)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.entity_type == entity_type,
                ContextEntry.type == "preferences",
                ContextEntry.status == "active",
                ((ContextEntry.expires_at.is_(None)) | (ContextEntry.expires_at >= now)),
            )
            .order_by(ContextEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    def _query_recent_awareness_entries(
        self,
        thread_ref: Optional[str],
        message_ref: Optional[str],
    ) -> List[ContextEntry]:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=1)
        query = self.db.query(ContextEntry).filter(
            ContextEntry.user_id == self.user_id,
            ContextEntry.type.in_(["decision", "commitment"]),
            ContextEntry.created_at >= threshold,
        )
        if thread_ref or message_ref:
            query = query.filter(
                ((ContextEntry.entity_type == "thread") & (ContextEntry.entity_id == thread_ref))
                | ((ContextEntry.entity_type == "message") & (ContextEntry.entity_id == message_ref))
            )
        return query.order_by(ContextEntry.created_at.desc()).limit(6).all()

    def _build_context_lines(
        self,
        thread_entries: List[ContextEntry],
        message_entries: List[ContextEntry],
        contact_entries: List[ContextEntry],
        assistant_preferences: List[ContextEntry],
        executive_preferences: List[ContextEntry],
        awareness_entries: List[ContextEntry],
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for entry in (
            thread_entries
            + message_entries
            + contact_entries
            + assistant_preferences
            + executive_preferences
            + awareness_entries
        ):
            result.append(
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
        return result[:18]

    def _fallback_body(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        sender_name: Optional[str],
        context_lines: List[Dict[str, Any]],
    ) -> str:
        greeting = f"Hi {recipient.split('@')[0].title()}," if recipient and "@" in recipient else "Hi,"
        top_context = [line["content"] for line in context_lines[:3] if line.get("content")]
        context_sentence = " ".join(top_context) if top_context else "Sharing a quick update."
        sign_off_name = (sender_name or "").strip()
        sign_off = f"Best,\n{sign_off_name}" if sign_off_name else "Best,"
        return (
            f"{greeting}\n\n"
            f"{intent.strip().capitalize()} re: {subject.strip()}.\n"
            f"{context_sentence}\n\n"
            "Please confirm if this works on your side.\n\n"
            f"{sign_off}"
        )

    def _sanitize_email_text(self, text: str, sender_name: Optional[str]) -> str:
        value = (text or "").strip()
        if not value:
            return value

        value = re.sub(r"\*\*(.*?)\*\*", r"\1", value, flags=re.DOTALL)
        value = re.sub(r"__(.*?)__", r"\1", value, flags=re.DOTALL)
        replacement_name = (sender_name or "").strip()
        value = re.sub(r"\[(?:your\s*name)\]", replacement_name, value, flags=re.IGNORECASE)
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()
