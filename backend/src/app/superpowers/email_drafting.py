"""Email drafting action service backed by the shared LLM layer."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.llm import LLMConfig, LLMOrchestrator
from app.data.models import Contact, ContextEntry, DiaryEntryLink, EntityReference, Message
from app.security.prompt_sanitizer import sanitize_with_detection
from app.services.contact_brief import ContactBriefService
from app.services.context_memory_policy import apply_memory_retrieval_filter


logger = logging.getLogger(__name__)
CONTEXT_ENTRY_TYPES = {
    "decision",
    "commitment",
    "preference",
    "preferences",
    "risk",
    "risks",
    "insight",
}
_draft_llm: Optional[LLMOrchestrator] = None


def _get_drafting_llm() -> LLMOrchestrator:
    global _draft_llm
    if _draft_llm is None:
        config = LLMConfig.for_drafting()
        output_limit = os.getenv("PLAYGROUND_EMAIL_DRAFT_MAX_OUTPUT_TOKENS", "380").strip()
        if output_limit.isdigit():
            config.api_max_output_tokens = int(output_limit)
        _draft_llm = LLMOrchestrator(config=config)
    return _draft_llm


class DraftGenerationError(RuntimeError):
    """Raised when a reply draft cannot be generated safely."""


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
        draft_format = self._infer_draft_format(
            thread_ref=thread_ref,
            message_ref=message_ref,
            source_message=source_message,
            subject=subject,
            intent=intent_text,
            user_request=user_request,
        )
        one_hop = self._discover_one_hop_entities(
            thread_ref=thread_ref,
            source_message=source_message,
            recipient_email=recipient_email,
        )

        thread_entries = self._query_thread_scope_entries(thread_ref, limit=10)
        message_entries = self._query_entries(
            "message",
            message_ref,
            limit=6,
            allowed_types=CONTEXT_ENTRY_TYPES,
        )
        contact_briefs = self._load_contact_briefs(one_hop["contacts"])
        contact_entries = self._build_contact_brief_context_lines(contact_briefs)
        event_entries = self._query_entity_scope_entries(
            entity_type="event",
            entity_ids=one_hop["events"],
            per_entity_limit=4,
            allowed_types=CONTEXT_ENTRY_TYPES,
            max_entities=3,
        )
        assistant_preferences = self._query_profile_preferences("assistant", limit=5)
        executive_preferences = self._query_profile_preferences("executive", limit=5)

        context_lines = self._build_context_lines(
            thread_entries=thread_entries,
            message_entries=message_entries,
            contact_entries=contact_entries,
            event_entries=event_entries,
            assistant_preferences=assistant_preferences,
            executive_preferences=executive_preferences,
        )
        body = self._generate_draft_body(
            subject=subject,
            intent=intent_text,
            recipient=recipient_email,
            sender_name=sender_name,
            context_lines=context_lines,
            contact_briefs=contact_briefs,
            source_message=source_message,
            user_request=user_request,
            draft_format=draft_format,
        )
        return {
            "subject": subject,
            "intent": intent_text,
            "recipient": recipient_email,
            "sender_name": sender_name,
            "thread_id": thread_ref,
            "message_id": message_ref,
            "draft_format": draft_format,
            "body": body,
            "context_entries": self._response_context_lines(context_lines),
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
        contact_briefs: List[Dict[str, Any]],
        source_message: Optional[Message],
        user_request: Optional[str] = None,
        draft_format: str = "email",
    ) -> str:
        llm = _get_drafting_llm()
        prompt = self._build_llm_prompt(
            subject=subject,
            intent=intent,
            recipient=recipient,
            sender_name=sender_name,
            context_lines=context_lines,
            contact_briefs=contact_briefs,
            source_message=source_message,
            user_request=user_request,
            draft_format=draft_format,
        )
        system_instruction = (
            "You draft concise executive-assistant emails. "
            "Return plain email body only. No markdown. No explanations. "
            "Never use placeholders like [Your Name]."
            if draft_format == "email"
            else "You draft concise, natural follow-up messages for chat channels "
            "(WhatsApp, LinkedIn DM, SMS). Return plain text only. "
            "No subject lines. No To/Cc/Bcc lines. No markdown. "
            "Never use placeholders like [Your Name]."
        )
        try:
            text = self._sanitize_draft_text(
                llm.generate_text(
                    prompt=prompt,
                    system_prompt=system_instruction,
                    max_output_tokens=380,
                    temperature=0.4,
                ),
                sender_name=sender_name,
                draft_format=draft_format,
            )
            if text and self._covers_request(user_request, text):
                return text
            if user_request:
                retry_prompt = self._build_llm_prompt(
                    subject=subject,
                    intent=intent,
                    recipient=recipient,
                    sender_name=sender_name,
                    context_lines=context_lines,
                    contact_briefs=contact_briefs,
                    source_message=source_message,
                    user_request=user_request,
                    missing_only=True,
                    draft_format=draft_format,
                )
                retry_text = self._sanitize_draft_text(
                    llm.generate_text(
                        prompt=retry_prompt,
                        system_prompt=system_instruction,
                        max_output_tokens=380,
                        temperature=0.3,
                    ),
                    sender_name=sender_name,
                    draft_format=draft_format,
                )
                if retry_text and self._covers_request(user_request, retry_text):
                    return retry_text
                if retry_text:
                    return retry_text
            if text:
                return text
            raise DraftGenerationError("empty_draft")
        except DraftGenerationError:
            raise
        except Exception as exc:
            logger.exception("email_draft_generation_failed user=%s", self.user_id)
            message = " ".join(str(exc).split()).lower()
            if any(token in message for token in {"quota", "resource_exhausted", "429", "credit", "billing"}):
                raise DraftGenerationError("quota_exceeded")
            if any(token in message for token in {"503", "unavailable", "timeout", "deadline"}):
                raise DraftGenerationError("llm_unavailable")
            raise DraftGenerationError("draft_generation_failed")

    def _build_llm_prompt(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        sender_name: Optional[str],
        context_lines: List[Dict[str, Any]],
        contact_briefs: List[Dict[str, Any]],
        source_message: Optional[Message],
        user_request: Optional[str] = None,
        missing_only: bool = False,
        draft_format: str = "email",
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
                "status": entry.get("status"),
                "expires_at": entry.get("expires_at"),
                "content": entry.get("content"),
            }
            for entry in context_lines[:14]
        ]
        contact_brief_context = [
            {
                "contact": item.get("contact"),
                "headline": item.get("headline"),
                "preferred_tone": item.get("preferred_tone"),
                "preferences": item.get("preferences") or [],
                "open_commitments": item.get("open_commitments") or [],
                "recent_decisions": item.get("recent_decisions") or [],
                "signals": item.get("signals") or [],
            }
            for item in (contact_briefs or [])[:3]
        ]
        required_points = self._extract_required_points(user_request)
        missing_points = required_points if not missing_only else [p for p in required_points if p]

        if draft_format == "email":
            task_label = "Draft an email reply."
            format_instruction = (
                "- Return only the email body text.\n"
                "- If sender name is provided, use it in the sign-off."
            )
        else:
            task_label = "Draft a natural follow-up message."
            format_instruction = (
                "- Return one natural message draft (channel-neutral).\n"
                "- No subject line. No To/Cc/Bcc line.\n"
                "- Do not force a formal sign-off unless the user asked for it."
            )

        return (
            f"{task_label}\n\n"
            f"Recipient: {recipient_hint}\n"
            f"{recipient_note}\n"
            f"Sender name: {sender_name or '[none]'}\n"
            f"Subject/topic: {subject}\n"
            f"Intent: {intent}\n\n"
            "Relevant source message:\n"
            f"{source_block}\n\n"
            "Known contact briefs:\n"
            f"{contact_brief_context or '[none]'}\n\n"
            "Context memory (highest-signal first):\n"
            f"{structured_context}\n\n"
            "Requirements:\n"
            "- Keep it brief, clear, and human.\n"
            "- Respect assistant, executive, and contact preferences.\n"
            "- When a contact brief is available, explicitly incorporate the contact's open commitments, recent decisions, and sensitivities.\n"
            "- Treat resolved/stale/archived items as historical context only.\n"
            "- Never output placeholders such as [Your Name].\n"
            f"{format_instruction}\n"
            + (
                ""
                if not required_points
                else "- Explicitly cover these user-stated points:\n"
                     + "\n".join(f"  - {p}" for p in required_points)
            )
            + (
                ""
                if not (missing_only and missing_points)
                else "\n- Missing coverage in the previous draft; include these explicitly now:\n"
                     + "\n".join(f"  - {p}" for p in missing_points)
            )
        )

    def _infer_draft_format(
        self,
        thread_ref: Optional[str],
        message_ref: Optional[str],
        source_message: Optional[Message],
        subject: str,
        intent: str,
        user_request: Optional[str],
    ) -> str:
        # Thread/message references are email-native entities in this app.
        if thread_ref or message_ref or source_message:
            return "email"

        text = " ".join([subject or "", intent or "", user_request or ""]).lower()
        if self._has_email_signal(text):
            return "email"
        if self._looks_like_email_text(user_request or ""):
            return "email"
        return "message"

    def _has_email_signal(self, text: str) -> bool:
        value = " ".join((text or "").split()).lower()
        if not value:
            return False
        tokens = {
            "email",
            "mail",
            "inbox",
            "subject",
            "cc",
            "bcc",
            "reply all",
            "forward",
            "thread",
            "send this email",
            "write an email",
        }
        return any(token in value for token in tokens)

    def _looks_like_email_text(self, text: str) -> bool:
        value = text or ""
        if re.search(r"(?im)^\s*(subject|to|cc|bcc)\s*:", value):
            return True
        has_greeting = bool(re.search(r"(?im)^\s*(hi|hello|dear)\b", value))
        has_signoff = bool(re.search(r"(?im)\b(best|regards|sincerely|thanks),?\s*$", value))
        return has_greeting and has_signoff

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

    def _discover_one_hop_entities(
        self,
        thread_ref: Optional[str],
        source_message: Optional[Message],
        recipient_email: Optional[str],
    ) -> Dict[str, List[str]]:
        contacts: List[str] = []
        events: List[str] = []

        if recipient_email:
            contacts.append(recipient_email.lower())
        if source_message:
            contacts.extend(self._extract_emails(source_message.sender))
            contacts.extend(self._extract_emails(source_message.recipient))

        if thread_ref:
            rows = (
                self.db.query(Message.sender, Message.recipient)
                .filter(
                    Message.user_id == self.user_id,
                    Message.thread_id == thread_ref,
                )
                .order_by(Message.received_at.desc(), Message.created_at.desc())
                .limit(25)
                .all()
            )
            for row in rows:
                contacts.extend(self._extract_emails(getattr(row, "sender", None)))
                contacts.extend(self._extract_emails(getattr(row, "recipient", None)))

            entry_ids = [
                item[0]
                for item in (
                    self.db.query(DiaryEntryLink.entry_id)
                    .join(ContextEntry, ContextEntry.id == DiaryEntryLink.entry_id)
                    .filter(
                        ContextEntry.user_id == self.user_id,
                        ContextEntry.status == "active",
                        DiaryEntryLink.entity_type == "thread",
                        DiaryEntryLink.entity_id == thread_ref,
                    )
                    .all()
                )
                if item and item[0] is not None
            ]
            if entry_ids:
                link_rows = (
                    self.db.query(DiaryEntryLink.entity_type, DiaryEntryLink.entity_id)
                    .filter(
                        DiaryEntryLink.entry_id.in_(entry_ids),
                        DiaryEntryLink.entity_type.in_(["contact", "event"]),
                    )
                    .all()
                )
                for link_type, link_id in link_rows:
                    if not link_id:
                        continue
                    if link_type == "contact":
                        contacts.append(str(link_id).lower())
                    elif link_type == "event":
                        events.append(str(link_id))

        return {
            "contacts": self._dedupe_non_empty(contacts),
            "events": self._dedupe_non_empty(events),
        }

    def _extract_emails(self, value: Optional[str]) -> List[str]:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return []
        found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        return [email.lower() for email in found]

    def _dedupe_non_empty(self, values: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in values:
            value = " ".join(str(item or "").split()).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(value)
        return out

    def _query_thread_scope_entries(self, thread_ref: Optional[str], limit: int = 10) -> List[ContextEntry]:
        if not thread_ref:
            return []
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(ContextEntry)
            .outerjoin(DiaryEntryLink, DiaryEntryLink.entry_id == ContextEntry.id)
            .filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.status == "active",
                or_(ContextEntry.expires_at.is_(None), ContextEntry.expires_at >= now),
                ContextEntry.type.in_(sorted(CONTEXT_ENTRY_TYPES)),
                or_(
                    and_(ContextEntry.entity_type == "thread", ContextEntry.entity_id == thread_ref),
                    and_(DiaryEntryLink.entity_type == "thread", DiaryEntryLink.entity_id == thread_ref),
                ),
            )
            .order_by(ContextEntry.updated_at.desc(), ContextEntry.created_at.desc())
            .limit(limit * 3)
            .all()
        )
        deduped: List[ContextEntry] = []
        seen = set()
        for row in rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            deduped.append(row)
            if len(deduped) >= limit:
                break
        return deduped

    def _query_entity_scope_entries(
        self,
        entity_type: str,
        entity_ids: List[str],
        per_entity_limit: int,
        allowed_types: Optional[set[str]] = None,
        max_entities: int = 4,
    ) -> List[ContextEntry]:
        out: List[ContextEntry] = []
        for entity_id in (entity_ids or [])[:max_entities]:
            out.extend(
                self._query_entries(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    limit=per_entity_limit,
                    allowed_types=allowed_types,
                )
            )
        deduped: List[ContextEntry] = []
        seen = set()
        for row in out:
            if row.id in seen:
                continue
            seen.add(row.id)
            deduped.append(row)
        return deduped

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
                ContextEntry.type == "preference",
                ContextEntry.status == "active",
                ((ContextEntry.expires_at.is_(None)) | (ContextEntry.expires_at >= now)),
            )
            .order_by(ContextEntry.created_at.desc())
            .limit(limit)
            .all()
        )

    def _load_contact_briefs(self, contact_emails: List[str], max_contacts: int = 3) -> List[Dict[str, Any]]:
        emails = [email.lower() for email in self._dedupe_non_empty(contact_emails)[: max(1, max_contacts)] if "@" in email]
        if not emails:
            return []

        contacts = (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                func.lower(Contact.email).in_(emails),
            )
            .all()
        )
        by_email = {(contact.email or "").strip().lower(): contact for contact in contacts if contact.email}
        brief_service = ContactBriefService(self.db, user_id=self.user_id)
        results: List[Dict[str, Any]] = []
        for email in emails:
            contact = by_email.get(email)
            if not contact:
                continue
            brief = brief_service.get_contact_brief(contact.id, consumer="drafting")
            if not brief:
                continue
            summary = brief.get("summary") or {}
            results.append(
                {
                    "contact": {
                        "id": contact.id,
                        "name": self._sanitize_contact_text(contact.name),
                        "email": (contact.email or "").strip().lower(),
                        "role": self._sanitize_contact_text(contact.role),
                        "organization": self._sanitize_contact_text(contact.organization),
                    },
                    "headline": self._sanitize_contact_text(summary.get("headline")),
                    "preferred_tone": self._sanitize_contact_text(summary.get("preferred_tone")),
                    "manual_notes": self._sanitize_contact_text(summary.get("manual_notes")),
                    "preferences": self._sanitize_contact_list(
                        [item.get("content") for item in (brief.get("preferences") or [])[:3]]
                    ),
                    "open_commitments": self._sanitize_contact_list(
                        [item.get("title") for item in (brief.get("commitments") or [])[:3]]
                    ),
                    "recent_decisions": self._sanitize_contact_list(
                        [item.get("decision") for item in (brief.get("decisions") or [])[:3]]
                    ),
                    "signals": self._sanitize_contact_list(
                        [item.get("message") or item.get("detail") for item in (brief.get("signals") or [])[:2]]
                    ),
                }
            )
        return results

    def _build_contact_brief_context_lines(self, contact_briefs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        lines: List[Dict[str, Any]] = []
        for brief in (contact_briefs or [])[:3]:
            contact = brief.get("contact") or {}
            email = contact.get("email")
            headline = brief.get("headline")
            if headline:
                lines.append(
                    {
                        "id": f"contact-brief:{contact.get('id')}:headline",
                        "type": "insight",
                        "entity_type": "contact",
                        "entity_id": email,
                        "content": headline,
                        "status": "active",
                    }
                )
            for idx, value in enumerate(brief.get("preferences") or []):
                lines.append(
                    {
                        "id": f"contact-brief:{contact.get('id')}:preference:{idx}",
                        "type": "preference",
                        "entity_type": "contact",
                        "entity_id": email,
                        "content": value,
                        "status": "active",
                    }
                )
            for idx, value in enumerate(brief.get("open_commitments") or []):
                lines.append(
                    {
                        "id": f"contact-brief:{contact.get('id')}:commitment:{idx}",
                        "type": "commitment",
                        "entity_type": "contact",
                        "entity_id": email,
                        "content": value,
                        "status": "active",
                    }
                )
            for idx, value in enumerate(brief.get("recent_decisions") or []):
                lines.append(
                    {
                        "id": f"contact-brief:{contact.get('id')}:decision:{idx}",
                        "type": "decision",
                        "entity_type": "contact",
                        "entity_id": email,
                        "content": value,
                        "status": "active",
                    }
                )
        return lines[:10]

    def _query_recent_awareness_entries(
        self,
        thread_ref: Optional[str],
        message_ref: Optional[str],
    ) -> List[ContextEntry]:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=1)
        query = apply_memory_retrieval_filter(
            self.db.query(ContextEntry).filter(
                ContextEntry.user_id == self.user_id,
                ContextEntry.type.in_(["decision", "commitment"]),
                ContextEntry.created_at >= threshold,
            ),
            allowed_statuses=("active",),
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
        contact_entries: List[Dict[str, Any]],
        event_entries: List[ContextEntry],
        assistant_preferences: List[ContextEntry],
        executive_preferences: List[ContextEntry],
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for entry in (
            thread_entries
            + message_entries
            + event_entries
            + assistant_preferences
            + executive_preferences
        ):
            result.append(
                {
                    "id": entry.id,
                    "type": entry.type,
                    "entity_type": entry.entity_type,
                    "entity_id": entry.entity_id,
                    "content": entry.content,
                    "status": entry.status,
                    "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
                }
            )
        result.extend(contact_entries)
        return result[:18]

    def _response_context_lines(self, context_lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Do not expose contact-derived relationship memory in action responses."""
        return [entry for entry in context_lines if entry.get("entity_type") != "contact"]

    def _fallback_body(
        self,
        subject: str,
        intent: str,
        recipient: Optional[str],
        sender_name: Optional[str],
        context_lines: List[Dict[str, Any]],
        draft_format: str = "email",
    ) -> str:
        if draft_format != "email":
            top_context = [line["content"] for line in context_lines[:2] if line.get("content")]
            context_sentence = " ".join(top_context).strip()
            base = (intent or "").strip().capitalize() or f"Quick follow-up on {subject.strip()}."
            return f"{base} {context_sentence}".strip() if context_sentence else base

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

    def _sanitize_draft_text(self, text: str, sender_name: Optional[str], draft_format: str = "email") -> str:
        value = (text or "").strip()
        if not value:
            return value

        value = re.sub(r"\*\*(.*?)\*\*", r"\1", value, flags=re.DOTALL)
        value = re.sub(r"__(.*?)__", r"\1", value, flags=re.DOTALL)
        replacement_name = (sender_name or "").strip()
        value = re.sub(r"\[(?:your\s*name)\]", replacement_name, value, flags=re.IGNORECASE)
        # Strip template placeholders (e.g., [Contact Name], [Specific Task], [Date]).
        value = re.sub(
            r"\[(?:[^\]]*\b(?:name|contact|recipient|assignee|specific|task|date|time|location|placeholder)\b[^\]]*)\]",
            "",
            value,
            flags=re.IGNORECASE,
        )
        # Remove synthetic thread labels that should never be shown to users.
        value = re.sub(r"@thread[a-z0-9_-]+", "", value, flags=re.IGNORECASE)
        if draft_format != "email":
            value = re.sub(r"(?im)^\s*(subject|to|cc|bcc)\s*:\s*.*$", "", value)
            value = re.sub(
                r"(?is)\n(?:best|regards|sincerely|thanks)[,!\.]?\s*\n[^\n]{0,60}\s*$",
                "",
                value.strip(),
            )
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    def _sanitize_contact_text(self, value: Optional[str]) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        result = sanitize_with_detection(text)
        cleaned = " ".join(result.sanitized_text.split()).strip()
        return cleaned or None

    def _sanitize_contact_list(self, values: List[Optional[str]]) -> List[str]:
        cleaned: List[str] = []
        for value in values:
            item = self._sanitize_contact_text(value)
            if item:
                cleaned.append(item)
        return cleaned
