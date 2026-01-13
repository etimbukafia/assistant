"""
Pattern Tracker Service (Executive Context Engine - Phase 1)

Tracks user actions to detect behavioral patterns.
Patterns are surfaced as suggestions only - never automated.

Pattern Types:
- dismiss_email: User dismisses certain types of emails
- prefer_morning: User prefers morning meetings
- prefer_afternoon: User prefers afternoon meetings
- shorten_draft: User edits drafts to be shorter
- lengthen_draft: User edits drafts to be longer

Confidence Formula: occurrences / (occurrences + 2)
- 3 occurrences = 60% confidence (minimum to surface)
- 5 occurrences = 71%
- 8 occurrences = 80%

Time Decay:
- 30 days inactive: -10% confidence
- 90 days inactive: mark as stale
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import hashlib
import json

from .models import DecisionPattern, Task, Message


class PatternTracker:
    """
    Tracks user actions and detects behavioral patterns.

    Usage:
        tracker = PatternTracker(db, user_id)

        # Track a dismissal
        tracker.track_action(
            action_type="dismiss_task",
            context={"sender_domain": "newsletter.com", "task_type": "explicit"}
        )

        # Apply time decay (call periodically)
        tracker.apply_decay()
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def track_action(
        self,
        action_type: str,
        context: Dict[str, Any],
        context_category: str = "task_review"
    ) -> Optional[DecisionPattern]:
        """
        Track a user action and update/create relevant patterns.

        Args:
            action_type: Type of action (dismiss_task, approve_task, edit_draft, etc.)
            context: Context about the action (sender, type, etc.)
            context_category: Category for relevance filtering (drafting, scheduling, task_review)

        Returns:
            Updated or created DecisionPattern, or None if not trackable
        """
        # Generate pattern key and extract pattern details
        pattern_info = self._extract_pattern_info(action_type, context)

        if not pattern_info:
            return None

        pattern_key = pattern_info["key"]
        pattern_type = pattern_info["type"]
        action = pattern_info["action"]
        conditions = pattern_info.get("conditions")

        # Look for existing pattern
        existing = self.db.query(DecisionPattern).filter(
            DecisionPattern.user_id == self.user_id,
            DecisionPattern.pattern_key == pattern_key,
            DecisionPattern.status.notin_(["rejected"])  # Don't track rejected patterns
        ).first()

        if existing:
            # Update existing pattern
            existing.occurrences += 1
            existing.confidence = self._calculate_confidence(existing.occurrences)
            existing.last_occurrence_at = datetime.now(timezone.utc)
            self.db.commit()
            return existing
        else:
            # Create new pattern
            pattern = DecisionPattern(
                user_id=self.user_id,
                pattern_key=pattern_key,
                pattern_type=pattern_type,
                context_type=context_category,
                conditions=conditions,
                action=action,
                occurrences=1,
                confidence=self._calculate_confidence(1),
                last_occurrence_at=datetime.now(timezone.utc),
                status="observed"
            )
            self.db.add(pattern)
            self.db.commit()
            self.db.refresh(pattern)
            return pattern

    def _extract_pattern_info(
        self,
        action_type: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract pattern information from an action.

        Returns dict with: key, type, action, conditions (optional)
        """
        if action_type == "dismiss_task":
            # Pattern: User dismisses tasks from certain senders/types
            sender = context.get("sender", "")
            sender_domain = sender.split("@")[-1] if "@" in sender else ""
            task_type = context.get("task_type", "")

            if sender_domain:
                # Track by sender domain
                pattern_key = f"dismiss_from_{sender_domain}"
                return {
                    "key": pattern_key,
                    "type": "dismiss_email",
                    "action": f"dismiss_from:{sender_domain}",
                    "conditions": {"sender_domain": sender_domain}
                }

        elif action_type == "approve_task":
            # Could track patterns of what types of tasks get approved quickly
            task_type = context.get("task_type", "")
            if task_type:
                pattern_key = f"approve_{task_type}"
                return {
                    "key": pattern_key,
                    "type": "approve_task_type",
                    "action": f"approve:{task_type}",
                    "conditions": {"task_type": task_type}
                }

        elif action_type == "schedule_meeting":
            # Track preferred meeting times
            hour = context.get("hour")
            if hour is not None:
                if 6 <= hour < 12:
                    time_pref = "morning"
                elif 12 <= hour < 17:
                    time_pref = "afternoon"
                else:
                    time_pref = "evening"

                pattern_key = f"prefer_{time_pref}_meetings"
                return {
                    "key": pattern_key,
                    "type": f"prefer_{time_pref}",
                    "action": f"prefer_time:{time_pref}",
                    "conditions": {"time_preference": time_pref}
                }

        elif action_type == "edit_draft":
            # Track if user shortens or lengthens drafts
            original_length = context.get("original_length", 0)
            final_length = context.get("final_length", 0)

            if original_length > 0 and final_length > 0:
                ratio = final_length / original_length

                if ratio < 0.7:
                    # User significantly shortened
                    pattern_key = "shorten_drafts"
                    return {
                        "key": pattern_key,
                        "type": "shorten_draft",
                        "action": "shorten",
                        "conditions": None
                    }
                elif ratio > 1.3:
                    # User significantly lengthened
                    pattern_key = "lengthen_drafts"
                    return {
                        "key": pattern_key,
                        "type": "lengthen_draft",
                        "action": "lengthen",
                        "conditions": None
                    }

        elif action_type == "mark_done_without_reply":
            # User marked message done without replying
            sender = context.get("sender", "")
            sender_domain = sender.split("@")[-1] if "@" in sender else ""

            if sender_domain:
                pattern_key = f"no_reply_to_{sender_domain}"
                return {
                    "key": pattern_key,
                    "type": "dismiss_email",
                    "action": f"no_reply_to:{sender_domain}",
                    "conditions": {"sender_domain": sender_domain}
                }

        return None

    def _calculate_confidence(self, occurrences: int) -> float:
        """
        Calculate confidence score.
        Formula: occurrences / (occurrences + 2)
        """
        return occurrences / (occurrences + 2)

    def apply_decay(self) -> Dict[str, int]:
        """
        Apply time decay to all patterns.

        Rules:
        - 30 days inactive: reduce confidence by 10%
        - 90 days inactive: mark as stale

        Returns:
            Dict with counts of decayed and staled patterns
        """
        now = datetime.now(timezone.utc)
        decay_threshold = now - timedelta(days=30)
        stale_threshold = now - timedelta(days=90)

        decayed_count = 0
        staled_count = 0

        # Get all active patterns
        patterns = self.db.query(DecisionPattern).filter(
            DecisionPattern.user_id == self.user_id,
            DecisionPattern.status.in_(["observed", "suggested"])
        ).all()

        for pattern in patterns:
            if pattern.last_occurrence_at < stale_threshold:
                # Mark as stale
                pattern.status = "stale"
                staled_count += 1
            elif pattern.last_occurrence_at < decay_threshold:
                # Apply 10% decay
                pattern.confidence = max(0, pattern.confidence * 0.9)
                decayed_count += 1

        self.db.commit()

        return {
            "decayed": decayed_count,
            "staled": staled_count
        }

    def get_suggestable_patterns(self) -> List[DecisionPattern]:
        """
        Get patterns ready to be surfaced as suggestions.

        Criteria:
        - status = 'observed' (not yet suggested/rejected)
        - confidence >= 0.6 (at least 3 occurrences)
        - not stale
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=90)

        return self.db.query(DecisionPattern).filter(
            DecisionPattern.user_id == self.user_id,
            DecisionPattern.status == "observed",
            DecisionPattern.confidence >= 0.6,
            DecisionPattern.last_occurrence_at >= stale_threshold
        ).order_by(DecisionPattern.confidence.desc()).all()


def track_task_action(db: Session, action: str, task: Task, user_id: str):
    """
    Convenience function to track task-related actions.

    Args:
        db: Database session
        action: One of "approve", "dismiss", "complete"
        task: The Task object
        user_id: User ID
    """
    tracker = PatternTracker(db, user_id)

    # Get message for sender info
    message = db.query(Message).filter(Message.id == task.message_id).first()
    sender = message.sender if message else ""

    context = {
        "sender": sender,
        "task_type": task.task_type,
        "priority": task.priority
    }

    if action == "dismiss":
        tracker.track_action("dismiss_task", context, "task_review")
    elif action == "approve":
        tracker.track_action("approve_task", context, "task_review")


def track_message_action(db: Session, action: str, message: Message, user_id):
    """
    Convenience function to track message-related actions.

    Args:
        db: Database session
        action: One of "mark_done", "archive"
        message: The Message object
        user_id: User ID
    """
    tracker = PatternTracker(db, user_id)

    context = {
        "sender": message.sender,
        "needs_reply": message.needs_reply
    }

    if action == "mark_done" and message.needs_reply:
        # User marked as done without replying
        tracker.track_action("mark_done_without_reply", context, "task_review")
