"""
Multi-layer email filtering system.

Determines which emails should receive full AI processing vs metadata-only storage.
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.data.models import ContactContext


class FilterAction(Enum):
    """Actions the filter can recommend"""
    PROCESS = "process"           # Full AI processing
    METADATA_ONLY = "metadata"    # Save metadata, skip AI processing
    SKIP = "skip"                 # Don't save at all


@dataclass
class FilterResult:
    """Result of applying email filters"""
    action: FilterAction
    filter_applied: Optional[str] = None  # Which filter triggered this result
    reason: Optional[str] = None          # Human-readable reason
    override_applied: bool = False        # True if VIP/override was used


class EmailFilterService:
    """
    Multi-layer email filtering system.

    Layer 1 - Hard Filters (Gmail Categories):
        - CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, CATEGORY_UPDATES
        - Default: metadata-only (skip AI processing)
        - Exception: VIP sender overrides → full processing

    Future layers can be added as methods and called in apply_filters().
    """

    # Gmail category labels that trigger filtering
    FILTERED_CATEGORIES = {
        "CATEGORY_PROMOTIONS",
        "CATEGORY_SOCIAL",
        "CATEGORY_UPDATES",
    }

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self._vip_cache: Optional[tuple] = None  # (vip_emails: set, vip_domains: set)

    def apply_filters(
        self,
        gmail_labels: List[str],
        sender_email: str,
        subject: str,
        headers: Optional[dict] = None,
        body_preview: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> FilterResult:
        """
        Apply all filter layers in order.

        Args:
            gmail_labels: List of Gmail label IDs (e.g., ['INBOX', 'CATEGORY_PROMOTIONS'])
            sender_email: Email address of sender
            subject: Email subject line
            headers: Dict with filtering headers (list_unsubscribe, precedence, auto_submitted)
            body_preview: Optional first ~200 chars of body for AI classification
            thread_id: Optional Gmail thread ID for active thread detection

        Returns:
            FilterResult with recommended action
        """
        headers = headers or {}

        # Layer 1, Step 1: Gmail Category Filters
        result = self._apply_category_filter(gmail_labels, sender_email)
        if result.action != FilterAction.PROCESS:
            return result

        # Layer 1, Step 2: Header-Based Rules (bulk/automated detection)
        result = self._apply_header_filter(headers, sender_email)
        if result.action != FilterAction.PROCESS:
            return result

        # Layer 1, Step 3: Sender Pattern Rules (no-reply, notifications, etc.)
        result = self._apply_sender_pattern_filter(sender_email)
        if result.action != FilterAction.PROCESS:
            return result

        # Layer 1, Step 4: Subject Line Heuristics
        result = self._apply_subject_heuristics_filter(subject, sender_email)
        if result.action != FilterAction.PROCESS:
            return result

        # Layer 2: Lightweight AI Classification (MiniLM embeddings)
        result = self._apply_ai_classification(subject, sender_email, body_preview, thread_id)
        if result.action != FilterAction.PROCESS:
            return result

        # Future layers can be added here:
        # Layer 3: User-defined rules

        # Default: process normally
        return FilterResult(action=FilterAction.PROCESS)

    def _apply_category_filter(
        self,
        gmail_labels: List[str],
        sender_email: str,
    ) -> FilterResult:
        """
        Layer 1: Filter based on Gmail categories.

        Promotions, Social, and Updates are metadata-only by default,
        unless sender is VIP.
        """
        # Check if any filtered category is present
        matched_categories = set(gmail_labels) & self.FILTERED_CATEGORIES

        if not matched_categories:
            return FilterResult(action=FilterAction.PROCESS)

        # Filtered category found - check for VIP override
        if self._is_vip_sender(sender_email):
            return FilterResult(
                action=FilterAction.PROCESS,
                filter_applied="category_filter",
                reason=f"VIP override for {', '.join(matched_categories)}",
                override_applied=True,
            )

        # Apply filter - metadata only
        return FilterResult(
            action=FilterAction.METADATA_ONLY,
            filter_applied="category_filter",
            reason=f"Filtered category: {', '.join(matched_categories)}",
            override_applied=False,
        )

    def _apply_header_filter(
        self,
        headers: dict,
        sender_email: str,
    ) -> FilterResult:
        """
        Layer 1, Step 2: Filter based on email headers indicating bulk/automated mail.

        Marks as trivial (metadata-only) if:
        - List-Unsubscribe header exists (mailing list)
        - Precedence: bulk (bulk mail)
        - Auto-Submitted: auto-generated (automated/system mail)

        VIP senders override this filter.
        """
        reasons = []

        # Check List-Unsubscribe header
        if headers.get('list_unsubscribe'):
            reasons.append("List-Unsubscribe header present")

        # Check Precedence: bulk
        precedence = headers.get('precedence', '').lower()
        if precedence == 'bulk':
            reasons.append("Precedence: bulk")

        # Check Auto-Submitted: auto-generated
        auto_submitted = headers.get('auto_submitted', '').lower()
        if auto_submitted == 'auto-generated':
            reasons.append("Auto-Submitted: auto-generated")

        if not reasons:
            return FilterResult(action=FilterAction.PROCESS)

        # Header-based filter triggered - check for VIP override
        if self._is_vip_sender(sender_email):
            return FilterResult(
                action=FilterAction.PROCESS,
                filter_applied="header_filter",
                reason=f"VIP override for: {'; '.join(reasons)}",
                override_applied=True,
            )

        # Apply filter - metadata only
        return FilterResult(
            action=FilterAction.METADATA_ONLY,
            filter_applied="header_filter",
            reason='; '.join(reasons),
            override_applied=False,
        )

    # Sender patterns that indicate automated/bulk mail
    FILTERED_SENDER_PREFIXES = {
        "no-reply",
        "noreply",
        "do-not-reply",
        "donotreply",
        "notifications",
        "notification",
        "updates",
        "newsletter",
        "newsletters",
        "mailer",
        "auto",
    }

    def _apply_sender_pattern_filter(self, sender_email: str) -> FilterResult:
        """
        Layer 1, Step 3: Filter based on sender email patterns.

        Marks as trivial (metadata-only) if sender local part matches:
        - no-reply@, noreply@, do-not-reply@
        - notifications@, notification@
        - updates@
        - newsletter@, newsletters@
        - mailer@, auto@

        VIP senders OR VIP domains override this filter.
        """
        email = self._extract_email(sender_email).lower()

        if '@' not in email:
            return FilterResult(action=FilterAction.PROCESS)

        local_part, domain = email.split('@', 1)

        # Check if local part matches any filtered pattern
        matched_pattern = None
        for prefix in self.FILTERED_SENDER_PREFIXES:
            if local_part == prefix or local_part.startswith(f"{prefix}-") or local_part.startswith(f"{prefix}_"):
                matched_pattern = f"{prefix}@"
                break

        if not matched_pattern:
            return FilterResult(action=FilterAction.PROCESS)

        # Pattern matched - check for VIP override (sender OR domain)
        if self._is_vip_sender(sender_email) or self._is_vip_domain(domain):
            return FilterResult(
                action=FilterAction.PROCESS,
                filter_applied="sender_pattern_filter",
                reason=f"VIP override for sender pattern: {matched_pattern}",
                override_applied=True,
            )

        # Apply filter - metadata only
        return FilterResult(
            action=FilterAction.METADATA_ONLY,
            filter_applied="sender_pattern_filter",
            reason=f"Filtered sender pattern: {matched_pattern}",
            override_applied=False,
        )

    # Subject keywords that indicate bulk/marketing mail
    FILTERED_SUBJECT_KEYWORDS = [
        "newsletter",
        "weekly update",
        "daily update",
        "monthly update",
        "digest",
        "you're receiving this because",
        "you are receiving this because",
        "unsubscribe",
        "subscription confirmed",
        "confirm your subscription",
    ]

    # Marketing language patterns (when combined with emojis)
    MARKETING_PHRASES = [
        "limited time",
        "act now",
        "don't miss",
        "dont miss",
        "exclusive offer",
        "special offer",
        "% off",
        "percent off",
        "free shipping",
        "flash sale",
        "last chance",
        "ending soon",
        "hurry",
        "deal of the day",
        "best deal",
        "save big",
        "order now",
        "shop now",
        "buy now",
        "claim your",
        "get your free",
    ]

    # Regex pattern for detecting emojis
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Misc symbols & pictographs
        "\U0001F680-\U0001F6FF"  # Transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U00002702-\U000027B0"  # Dingbats
        "\U0001F900-\U0001F9FF"  # Supplemental symbols
        "\U0001FA00-\U0001FA6F"  # Chess symbols
        "\U0001FA70-\U0001FAFF"  # Symbols & pictographs ext-A
        "\U00002600-\U000026FF"  # Misc symbols
        "]+",
        re.UNICODE
    )

    def _apply_subject_heuristics_filter(
        self,
        subject: str,
        sender_email: str,
    ) -> FilterResult:
        """
        Layer 1, Step 4: Filter based on subject line heuristics.

        Marks as trivial (metadata-only) if subject contains:
        - Newsletter, Weekly update, Digest
        - "You're receiving this because", Unsubscribe
        - Emojis combined with marketing language

        VIP senders/domains override this filter.
        """
        if not subject:
            return FilterResult(action=FilterAction.PROCESS)

        subject_lower = subject.lower()
        reasons = []

        # Check for filtered keywords
        for keyword in self.FILTERED_SUBJECT_KEYWORDS:
            if keyword in subject_lower:
                reasons.append(f"keyword: '{keyword}'")
                break  # One match is enough

        # Check for emoji + marketing language combo
        has_emoji = bool(self.EMOJI_PATTERN.search(subject))
        has_marketing = any(phrase in subject_lower for phrase in self.MARKETING_PHRASES)

        if has_emoji and has_marketing:
            reasons.append("emoji + marketing language")

        if not reasons:
            return FilterResult(action=FilterAction.PROCESS)

        # Subject heuristics triggered - check for VIP override
        email = self._extract_email(sender_email).lower()
        domain = email.split('@', 1)[1] if '@' in email else None

        if self._is_vip_sender(sender_email) or (domain and self._is_vip_domain(domain)):
            return FilterResult(
                action=FilterAction.PROCESS,
                filter_applied="subject_heuristics_filter",
                reason=f"VIP override for: {'; '.join(reasons)}",
                override_applied=True,
            )

        # Apply filter - metadata only
        return FilterResult(
            action=FilterAction.METADATA_ONLY,
            filter_applied="subject_heuristics_filter",
            reason=f"Subject heuristics: {'; '.join(reasons)}",
            override_applied=False,
        )

    def _apply_ai_classification(
        self,
        subject: str,
        sender_email: str,
        body_preview: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> FilterResult:
        """
        Layer 2: Lightweight AI classification using sentence embeddings.

        Uses MiniLM to classify emails as important or ignorable based on
        semantic similarity to anchor descriptions.

        Bypass conditions (always PROCESS):
        - VIP sender or domain
        - Sender appears in recent calendar events (Layer 3)
        - Sender has high reply rate > 30% (Layer 3)
        - Active thread (has open tasks or recent activity)
        """
        from app.services.email_classifier import classify_email, is_classifier_available

        # Skip if classifier not available (graceful degradation)
        if not is_classifier_available():
            return FilterResult(action=FilterAction.PROCESS)

        email = self._extract_email(sender_email).lower()
        domain = email.split('@', 1)[1] if '@' in email else None

        # VIP bypass
        if self._is_vip_sender(sender_email) or (domain and self._is_vip_domain(domain)):
            return FilterResult(action=FilterAction.PROCESS)

        # Layer 3: Relationship context overrides
        if self._sender_in_recent_calendar(email):
            return FilterResult(action=FilterAction.PROCESS)

        if self._sender_has_high_reply_rate(email, threshold=0.3):
            return FilterResult(action=FilterAction.PROCESS)

        # Active thread bypass
        if thread_id and self._is_active_thread(thread_id):
            return FilterResult(action=FilterAction.PROCESS)

        # Layer 2: AI Classification
        result = classify_email(
            subject=subject,
            sender=sender_email,
            body_preview=body_preview,
            threshold=0.1,
        )

        if result.should_process:
            return FilterResult(action=FilterAction.PROCESS)

        # AI classified as ignorable
        return FilterResult(
            action=FilterAction.METADATA_ONLY,
            filter_applied="ai_classification",
            reason=f"AI: {result.reason}",
            override_applied=False,
        )

    def _sender_in_recent_calendar(self, sender_email: str, days: int = 30) -> bool:
        """
        Check if sender appears in recent calendar events.

        A sender who you've had meetings with recently is likely important.
        Uses optimized EXISTS query instead of loading all events.
        """
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import or_, func, cast, String
        from app.data.models import CalendarEvent

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Optimized: EXISTS query with JSON search, returns boolean directly
        # Check if sender is organizer OR in participants array
        exists = self.db.query(CalendarEvent.id).filter(
            CalendarEvent.user_id == self.user_id,
            CalendarEvent.start_time >= cutoff,
            or_(
                func.lower(CalendarEvent.organizer) == sender_email,
                # Search JSON array for matching email using PostgreSQL
                func.lower(cast(CalendarEvent.participants, String)).contains(sender_email)
            )
        ).limit(1).first()

        return exists is not None

    def _sender_has_high_reply_rate(self, sender_email: str, threshold: float = 0.3) -> bool:
        """
        Check if user historically replies to this sender often.

        If reply rate > threshold (default 30%), sender is likely important.
        Uses ContactContext metadata for efficient lookup (O(1) query).
        """
        from app.data.models import ContactContext

        # Single efficient query - just fetch the needed fields
        contact = self.db.query(
            ContactContext.contact_metadata
        ).filter(
            ContactContext.user_id == self.user_id,
            ContactContext.contact_email == sender_email,
        ).first()

        if not contact or not contact.contact_metadata:
            return False

        metadata = contact.contact_metadata
        message_count = metadata.get("message_count", 0)

        # Need minimum interaction history to calculate meaningful rate
        if message_count < 3:
            return False

        # Use cached reply_rate from contact_metadata
        # This should be updated by a background job when threads change
        reply_rate = metadata.get("reply_rate", 0.0)

        return reply_rate >= threshold

    def _is_active_thread(self, thread_id: str) -> bool:
        """
        Check if a thread is active (has open tasks or recent user engagement).

        A thread is considered active if:
        - It has open/pending tasks
        - User has replied to it recently (last_outbound_at within 7 days)
        """
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import or_, exists, and_
        from app.data.models import ThreadState, Task

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        # Optimized: single query checking both conditions
        # 1. ThreadState with recent outbound, OR
        # 2. Open tasks in thread

        # Check thread state for recent reply
        thread_state = self.db.query(
            ThreadState.last_outbound_at
        ).filter(
            ThreadState.thread_id == thread_id,
            ThreadState.user_id == self.user_id,
        ).first()

        if thread_state and thread_state.last_outbound_at:
            if thread_state.last_outbound_at >= cutoff:
                return True

        # Check for open tasks (EXISTS query, stops at first match)
        has_open_tasks = self.db.query(Task.id).filter(
            Task.thread_id == thread_id,
            Task.user_id == self.user_id,
            Task.status.in_(["pending_approval", "approved", "snoozed"]),
        ).limit(1).first()

        return has_open_tasks is not None

    def _is_vip_sender(self, sender_email: str) -> bool:
        """
        Check if sender is in user's VIP list.

        VIP is determined by ContactContext.category = 'vip'
        """
        # Extract email from "Name <email@example.com>" format
        email = self._extract_email(sender_email)

        # Load VIP list (cached per instance)
        vip_emails, _ = self._get_vip_data()

        return email.lower() in vip_emails

    def _is_vip_domain(self, domain: str) -> bool:
        """
        Check if domain belongs to a VIP contact.

        If any VIP contact has an email @domain, the domain is considered VIP.
        Also supports explicit domain entries (e.g., "example.com" stored as contact_email).
        """
        _, vip_domains = self._get_vip_data()
        return domain.lower() in vip_domains

    def _get_vip_data(self) -> tuple:
        """
        Get VIP emails and domains for this user (cached).

        Returns:
            tuple: (set of VIP emails, set of VIP domains)
        """
        if self._vip_cache is not None:
            return self._vip_cache

        vip_contacts = self.db.query(ContactContext).filter(
            ContactContext.user_id == self.user_id,
            ContactContext.category == "vip"
        ).all()

        vip_emails = set()
        vip_domains = set()

        for contact in vip_contacts:
            if not contact.contact_email:
                continue

            email = contact.contact_email.lower()
            vip_emails.add(email)

            # Extract domain from email
            if '@' in email:
                domain = email.split('@', 1)[1]
                vip_domains.add(domain)
            else:
                # Might be a domain-only entry (e.g., "important-client.com")
                vip_domains.add(email)

        self._vip_cache = (vip_emails, vip_domains)
        return self._vip_cache

    @staticmethod
    def _extract_email(sender: str) -> str:
        """Extract email address from 'Name <email>' format"""
        if '<' in sender and '>' in sender:
            start = sender.index('<') + 1
            end = sender.index('>')
            return sender[start:end].strip()
        return sender.strip()
