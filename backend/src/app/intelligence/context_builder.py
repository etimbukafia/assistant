from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

"""
Context Builder Service (Executive Context Engine - Phase 1)

Compiles relevant memory context for injection into AI prompts.
Handles token budgeting, priority ordering, and relevance filtering.

Priority order (more specific wins):
1. ContactContext (if sender exists)
2. PrincipalMemory (explicit preferences)
3. DecisionPatterns (only if directly relevant)

Token budget: ~400 tokens max
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.data.models import PrincipalMemory, DecisionPattern, ContactContext


@dataclass
class ContextItem:
    """A single piece of context to potentially inject"""
    text: str
    priority: int  # 1 = highest (contact), 2 = medium (preference), 3 = lowest (pattern)
    relevance_score: float  # 0.0 - 1.0
    source: str  # "contact", "preference", "pattern"
    key: str  # Original key for conflict detection


# Context types and their relevant preference keys
CONTEXT_TYPE_KEYS = {
    "drafting": ["tone", "reply_length", "sign_off", "greeting", "formality"],
    "scheduling": ["working_hours_start", "working_hours_end", "blocked_times",
                   "preferred_meeting_times", "buffer_minutes", "no_meeting_days"],
    "task_review": ["auto_dismiss_patterns", "priority_keywords", "task_preferences"]
}

# Approximate tokens per character (conservative estimate)
CHARS_PER_TOKEN = 4
MAX_TOKENS = 400
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN  # ~1600 chars


class ContextBuilder:
    """
    Builds context strings for injection into AI prompts.

    Usage:
        builder = ContextBuilder(db, user_id)
        context = builder.build_context(
            context_type="drafting",
            sender_email="john@example.com"
        )
        # Returns: "User prefers concise replies. Contact is VIP, use formal tone."
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def build_context(
        self,
        context_type: str,
        sender_email: Optional[str] = None,
        include_patterns: bool = True
    ) -> str:
        """
        Build a context string for the given context type.

        Args:
            context_type: One of "drafting", "scheduling", "task_review"
            sender_email: Optional sender email for contact-specific context
            include_patterns: Whether to include observed patterns (default True)

        Returns:
            A concise context string ready for prompt injection
        """
        items: List[ContextItem] = []

        # 1. Get ContactContext (highest priority)
        if sender_email:
            contact_items = self._get_contact_context(sender_email, context_type)
            items.extend(contact_items)

        # 2. Get PrincipalMemory preferences
        preference_items = self._get_preferences(context_type)
        items.extend(preference_items)

        # 3. Get DecisionPatterns (if enabled and relevant)
        if include_patterns:
            pattern_items = self._get_relevant_patterns(context_type)
            items.extend(pattern_items)

        # Resolve conflicts (more specific wins)
        resolved_items = self._resolve_conflicts(items)

        # Apply token budget
        final_items = self._apply_token_budget(resolved_items)

        # Compile into string
        return self._compile_context(final_items, context_type, sender_email)

    def _get_contact_context(self, email: str, context_type: str) -> List[ContextItem]:
        """Get context items from ContactContext"""
        items = []

        contact = self.db.query(ContactContext).filter(
            ContactContext.user_id == self.user_id,
            ContactContext.contact_email == email
        ).first()

        if not contact:
            return items

        # Category provides context
        if contact.category:
            category_text = {
                "vip": "This is a VIP contact - prioritize and respond promptly.",
                "colleague": "This is a colleague - use friendly professional tone.",
                "external": "This is an external contact.",
                "vendor": "This is a vendor/supplier contact."
            }.get(contact.category, f"Contact category: {contact.category}")

            items.append(ContextItem(
                text=category_text,
                priority=1,
                relevance_score=1.0,
                source="contact",
                key="category"
            ))

        # Preferred tone overrides default
        if contact.preferred_tone and context_type == "drafting":
            items.append(ContextItem(
                text=f"Use {contact.preferred_tone} tone with this contact (overrides default).",
                priority=1,
                relevance_score=1.0,
                source="contact",
                key="tone"
            ))

        # Manual notes (if present and not empty)
        if contact.notes and contact.notes.strip():
            items.append(ContextItem(
                text=f"Note about contact: {contact.notes}",
                priority=1,
                relevance_score=0.9,
                source="contact",
                key="notes"
            ))

        # Metadata insights (factual observations)
        metadata = contact.contact_metadata or {}

        # High urgency frequency
        if metadata.get("urgency_frequency", 0) > 5:
            items.append(ContextItem(
                text="This contact frequently sends urgent messages.",
                priority=1,
                relevance_score=0.7,
                source="contact",
                key="urgency_pattern"
            ))

        return items

    def _get_preferences(self, context_type: str) -> List[ContextItem]:
        """Get context items from PrincipalMemory"""
        items = []

        preferences = self.db.query(PrincipalMemory).filter(
            PrincipalMemory.user_id == self.user_id,
            PrincipalMemory.context_type == context_type
        ).all()

        for pref in preferences:
            # Format preference as readable text
            text = self._format_preference(pref.key, pref.value, context_type)

            items.append(ContextItem(
                text=text,
                priority=2,
                relevance_score=1.0,  # Explicit preferences are always relevant
                source="preference",
                key=pref.key
            ))

        return items

    def _format_preference(self, key: str, value: str, context_type: str) -> str:
        """Format a preference key-value into readable text"""
        formatters = {
            # Drafting preferences
            "tone": f"User prefers {value} tone in replies.",
            "reply_length": f"User prefers {value} replies.",
            "sign_off": f"Use this sign-off: \"{value}\"",
            "greeting": f"Use this greeting style: {value}",
            "formality": f"Formality level: {value}",

            # Scheduling preferences
            "working_hours_start": f"Working hours start at {value}.",
            "working_hours_end": f"Working hours end at {value}.",
            "blocked_times": f"Blocked times: {value}",
            "preferred_meeting_times": f"Preferred meeting times: {value}",
            "no_meeting_days": f"No meetings on: {value}",

            # Task preferences
            "auto_dismiss_patterns": f"Auto-dismiss pattern: {value}",
            "priority_keywords": f"High priority keywords: {value}",
        }

        return formatters.get(key, f"{key}: {value}")

    def _get_relevant_patterns(self, context_type: str) -> List[ContextItem]:
        """Get relevant observed patterns (not stale, high confidence)"""
        items = []

        stale_threshold = datetime.now(timezone.utc) - timedelta(days=90)

        patterns = self.db.query(DecisionPattern).filter(
            DecisionPattern.user_id == self.user_id,
            DecisionPattern.context_type == context_type,
            DecisionPattern.status.in_(["observed", "suggested"]),  # Not rejected
            DecisionPattern.confidence >= 0.6,  # At least 3 occurrences
            DecisionPattern.last_occurrence_at >= stale_threshold
        ).order_by(DecisionPattern.confidence.desc()).limit(3).all()  # Max 3 patterns

        for pattern in patterns:
            text = self._format_pattern(pattern)

            items.append(ContextItem(
                text=text,
                priority=3,
                relevance_score=pattern.confidence,
                source="pattern",
                key=pattern.pattern_key
            ))

        return items

    def _format_pattern(self, pattern: DecisionPattern) -> str:
        """Format a pattern into readable text"""
        confidence_pct = int(pattern.confidence * 100)

        pattern_texts = {
            "dismiss_email": f"User often dismisses emails like this ({confidence_pct}% confidence).",
            "prefer_morning": f"User prefers morning meetings ({confidence_pct}% confidence).",
            "prefer_afternoon": f"User prefers afternoon meetings ({confidence_pct}% confidence).",
            "shorten_draft": f"User tends to shorten AI drafts ({confidence_pct}% confidence).",
            "lengthen_draft": f"User tends to expand AI drafts ({confidence_pct}% confidence).",
        }

        return pattern_texts.get(
            pattern.pattern_type,
            f"Observed pattern: {pattern.action} ({confidence_pct}% confidence)"
        )

    def _resolve_conflicts(self, items: List[ContextItem]) -> List[ContextItem]:
        """
        Resolve conflicts between items with the same key.
        Higher priority (lower number) wins.
        """
        resolved = {}

        for item in items:
            if item.key not in resolved:
                resolved[item.key] = item
            else:
                # Lower priority number wins
                if item.priority < resolved[item.key].priority:
                    resolved[item.key] = item

        return list(resolved.values())

    def _apply_token_budget(self, items: List[ContextItem]) -> List[ContextItem]:
        """
        Apply token budget by selecting items until budget is exhausted.
        Items are sorted by priority then relevance.
        """
        # Sort by priority (ascending) then relevance (descending)
        sorted_items = sorted(items, key=lambda x: (x.priority, -x.relevance_score))

        selected = []
        current_chars = 0

        for item in sorted_items:
            item_chars = len(item.text)

            if current_chars + item_chars <= MAX_CHARS:
                selected.append(item)
                current_chars += item_chars
            else:
                # Budget exceeded, stop adding
                break

        return selected

    def _compile_context(
        self,
        items: List[ContextItem],
        context_type: str,
        sender_email: Optional[str]
    ) -> str:
        """Compile selected items into a context string"""
        if not items:
            return ""

        # Group by source for clarity
        contact_items = [i for i in items if i.source == "contact"]
        preference_items = [i for i in items if i.source == "preference"]
        pattern_items = [i for i in items if i.source == "pattern"]

        parts = []

        if contact_items:
            contact_texts = [i.text for i in contact_items]
            parts.append(" ".join(contact_texts))

        if preference_items:
            pref_texts = [i.text for i in preference_items]
            parts.append(" ".join(pref_texts))

        if pattern_items:
            pattern_texts = [i.text for i in pattern_items]
            parts.append(" ".join(pattern_texts))

        return " ".join(parts)

    def get_context_summary(
        self,
        context_type: str,
        sender_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a structured summary of what context would be injected.
        Useful for debugging and transparency.
        """
        items: List[ContextItem] = []

        if sender_email:
            items.extend(self._get_contact_context(sender_email, context_type))

        items.extend(self._get_preferences(context_type))
        items.extend(self._get_relevant_patterns(context_type))

        resolved = self._resolve_conflicts(items)
        final = self._apply_token_budget(resolved)

        return {
            "context_type": context_type,
            "sender_email": sender_email,
            "total_items_found": len(items),
            "after_conflict_resolution": len(resolved),
            "after_token_budget": len(final),
            "estimated_tokens": sum(len(i.text) for i in final) // CHARS_PER_TOKEN,
            "items": [
                {
                    "text": i.text,
                    "source": i.source,
                    "priority": i.priority,
                    "key": i.key
                }
                for i in final
            ],
            "compiled_context": self._compile_context(final, context_type, sender_email)
        }


