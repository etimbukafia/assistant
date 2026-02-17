"""
Briefing Service - Generate meeting briefings from calendar events.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.data.models import CalendarEvent, Message, Task
from app.processors.ai import AIProcessor

logger = logging.getLogger(__name__)


class BriefingService:
    """Generate meeting briefings by combining calendar, email, and task data."""

    def __init__(self, db: Session):
        self.db = db
        self.ai_processor = AIProcessor()

    def generate_briefing(self, event: CalendarEvent) -> Dict[str, Any]:
        """
        Generate a briefing for a calendar event.

        Args:
            event: CalendarEvent to generate briefing for

        Returns:
            Briefing dict with attendees, agenda, related_emails, tasks, context, prep_warnings
        """
        # 1. Get attendee emails
        attendee_emails = self._get_attendee_emails(event)

        # 2. Find related messages
        related_messages = self._find_related_messages(attendee_emails, event.title)

        # 3. Find related tasks
        related_tasks = self._find_related_tasks(attendee_emails)

        # 4. Check prep status
        prep_warnings = self._check_prep_status(event, related_tasks, attendee_emails)

        # 5. Build briefing
        briefing = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'attendees': self._format_attendees(event),
            'agenda': event.description or 'No agenda provided',
            'location': event.location,
            'related_emails': self._summarize_messages(related_messages),
            'open_tasks': self._format_tasks(related_tasks),
            'prep_warnings': prep_warnings,
            'message_count': len(related_messages),
            'task_count': len(related_tasks),
            'prep_complete': len(prep_warnings) == 0
        }

        # 6. Store related IDs on event
        event.related_message_ids = [m.id for m in related_messages]
        event.related_task_ids = [t.id for t in related_tasks]
        event.briefing = briefing
        event.briefing_generated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"Generated briefing for event {event.id}: {len(related_messages)} messages, {len(related_tasks)} tasks")
        return briefing

    def _get_attendee_emails(self, event: CalendarEvent) -> List[str]:
        """Extract attendee emails from event."""
        emails = []
        for p in (event.participants or []):
            if isinstance(p, dict):
                email = p.get('email', '')
            else:
                email = str(p)
            if email and '@' in email:
                emails.append(email.lower())
        return list(set(emails))

    def _find_related_messages(
        self,
        attendee_emails: List[str],
        event_title: str,
        limit: int = 10
    ) -> List[Message]:
        """Find messages involving attendees or matching event title."""
        if not attendee_emails:
            return []

        # Build OR conditions for sender matching any attendee
        conditions = [Message.sender.ilike(f"%{email}%") for email in attendee_emails]

        # Also match subject containing event title keywords
        if event_title and len(event_title) > 3:
            title_words = [w for w in event_title.split() if len(w) > 3]
            for word in title_words[:3]:  # First 3 significant words
                conditions.append(Message.subject.ilike(f"%{word}%"))

        messages = (
            self.db.query(Message)
            .filter(or_(*conditions))
            .order_by(Message.received_at.desc())
            .limit(limit)
            .all()
        )
        return messages

    def _find_related_tasks(
        self,
        attendee_emails: List[str],
        limit: int = 10
    ) -> List[Task]:
        """Find open tasks involving attendees."""
        if not attendee_emails:
            return []

        # Get tasks that are approved and not completed
        tasks = (
            self.db.query(Task)
            .filter(
                Task.status.in_(['approved', 'pending_approval']),
            )
            .order_by(Task.created_at.desc())
            .limit(50)  # Get more, then filter
            .all()
        )

        # Filter by attendee involvement
        related = []
        for task in tasks:
            people = task.related_people or []
            for person in people:
                if any(email in person.lower() for email in attendee_emails):
                    related.append(task)
                    break
            if len(related) >= limit:
                break

        return related

    def _format_attendees(self, event: CalendarEvent) -> List[Dict[str, Any]]:
        """Format attendee info for briefing."""
        attendees = []
        for p in (event.participants or []):
            if isinstance(p, dict):
                attendees.append({
                    'email': p.get('email'),
                    'name': p.get('name') or (p.get('email', '').split('@')[0] if p.get('email') else ''),
                    'response': p.get('response_status', 'unknown'),
                })
            elif isinstance(p, str) and '@' in p:
                attendees.append({
                    'email': p,
                    'name': p.split('@')[0],
                    'response': 'unknown',
                })
        return attendees

    def _summarize_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Create brief summaries of related messages."""
        summaries = []
        for msg in messages:
            summaries.append({
                'id': msg.id,
                'subject': msg.subject,
                'sender': msg.sender,
                'date': msg.received_at.isoformat() if msg.received_at else None,
                'summary': msg.summary or msg.subject,
                'needs_reply': msg.needs_reply
            })
        return summaries

    def _format_tasks(self, tasks: List[Task]) -> List[Dict[str, Any]]:
        """Format tasks for briefing."""
        return [
            {
                'id': t.id,
                'title': t.title,
                'priority': t.priority,
                'status': t.status,
                'type': t.task_type
            }
            for t in tasks
        ]

    def _check_prep_status(
        self,
        event: CalendarEvent,
        related_tasks: List[Task],
        attendee_emails: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Check for missing prep items before meeting.

        Returns list of warnings:
        - No agenda shared
        - Waiting on documents/info from attendees
        - Incomplete follow-up tasks from previous interactions
        """
        warnings = []

        # 1. Check for missing agenda
        if not event.description or len(event.description.strip()) < 10:
            warnings.append({
                'type': 'no_agenda',
                'severity': 'medium',
                'message': 'No agenda provided for this meeting',
                'suggestion': 'Consider adding an agenda or discussion points'
            })

        # 2. Check for "waiting_for" tasks involving attendees
        waiting_tasks = [
            t for t in related_tasks
            if t.task_type == 'waiting_for' and t.status in ['approved', 'pending_approval']
        ]
        for task in waiting_tasks:
            warnings.append({
                'type': 'waiting_for',
                'severity': 'high',
                'message': f'Waiting on: {task.title}',
                'task_id': task.id,
                'suggestion': 'Follow up before meeting or add to agenda'
            })

        # 3. Check for incomplete follow-up tasks
        followup_tasks = [
            t for t in related_tasks
            if t.task_type == 'implied_followup' and t.status in ['approved', 'pending_approval']
        ]
        for task in followup_tasks:
            warnings.append({
                'type': 'pending_followup',
                'severity': 'medium',
                'message': f'Pending follow-up: {task.title}',
                'task_id': task.id,
                'suggestion': 'Complete before meeting or discuss status'
            })

        # 4. Check for meeting_prep tasks
        prep_tasks = [
            t for t in related_tasks
            if t.task_type == 'meeting_prep' and t.status in ['approved', 'pending_approval']
        ]
        for task in prep_tasks:
            warnings.append({
                'type': 'incomplete_prep',
                'severity': 'high',
                'message': f'Prep not done: {task.title}',
                'task_id': task.id,
                'suggestion': 'Complete preparation before meeting'
            })

        # 5. Check for unanswered messages from attendees
        unanswered = self._find_unanswered_from_attendees(attendee_emails)
        if unanswered:
            warnings.append({
                'type': 'unanswered_messages',
                'severity': 'medium',
                'message': f'{len(unanswered)} unanswered message(s) from attendees',
                'message_ids': [m.id for m in unanswered],
                'suggestion': 'Review and respond before meeting'
            })

        return warnings

    def _find_unanswered_from_attendees(
        self,
        attendee_emails: List[str],
        limit: int = 5
    ) -> List[Message]:
        """Find messages from attendees that need reply."""
        if not attendee_emails:
            return []

        conditions = [Message.sender.ilike(f"%{email}%") for email in attendee_emails]

        messages = (
            self.db.query(Message)
            .filter(
                or_(*conditions),
                Message.needs_reply == True,
                Message.status == 'inbox'
            )
            .order_by(Message.received_at.desc())
            .limit(limit)
            .all()
        )
        return messages


    def generate_follow_ups(self, event: CalendarEvent) -> Dict[str, Any]:
        """
        Generate follow-up items after a meeting using AI.

        Delegates to FollowUpModule for actual generation.
        Uses the meeting briefing context to generate relevant:
        - Follow-up tasks
        - Email drafts to attendees
        - Reminders for future actions

        All items require user approval before creation.
        """
        from app.agents.modules import FollowUpModule

        follow_up_module = FollowUpModule()
        return follow_up_module.generate_meeting_follow_ups(event.id)


def generate_briefing_for_event(db: Session, event_id: int) -> Optional[Dict[str, Any]]:
    """Convenience function to generate briefing by event ID."""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        return None

    service = BriefingService(db)
    return service.generate_briefing(event)


def generate_follow_ups_for_event(db: Session, event_id: int) -> Optional[Dict[str, Any]]:
    """Convenience function to generate follow-ups by event ID."""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        return None

    service = BriefingService(db)
    return service.generate_follow_ups(event)
