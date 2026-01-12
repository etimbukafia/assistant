"""
Follow-Up Module

Handles follow-up evaluation and generation for tasks.
"""
from typing import Dict, Any
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from .base import BaseModule
from app.models import Task, Message, CalendarEvent


class FollowUpModule(BaseModule):
    """
    Module for managing follow-ups on pending tasks

    Capabilities:
    - Evaluate if a follow-up is needed
    - Check if a reply has been received
    - Generate polite follow-up messages
    """

    def get_capabilities(self) -> Dict[str, str]:
        """Return capabilities of this module"""
        return {
            "evaluate_need": "Evaluate if a follow-up is still needed for a task",
            "check_for_reply": "Check if a reply has been received for a waiting_for task",
            "generate_follow_up": "Generate a polite follow-up message for a task",
            "generate_meeting_follow_ups": "Generate post-meeting follow-up items (tasks, emails, reminders)",
        }

    def evaluate_need(self, task_id: int, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Evaluate if a follow-up is still needed

        Args:
            task_id: ID of the task to evaluate
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Dictionary with evaluation result
        """
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            return {
                "needed": False,
                "reason": "Task not found",
                "confidence": 0.0,
            }

        # Check if task is still active
        if task.status in ["completed", "dismissed"]:
            return {
                "needed": False,
                "reason": f"Task is already {task.status}",
                "confidence": 1.0,
            }

        # Check task type - only follow up on waiting_for and implied_followup
        if task.task_type not in ["waiting_for", "implied_followup"]:
            return {
                "needed": False,
                "reason": f"Task type '{task.task_type}' doesn't require follow-up",
                "confidence": 0.9,
            }

        # Check if task was created recently (< 3 days ago)
        days_since_created = (datetime.now(timezone.utc) - task.created_at).days
        if days_since_created < 3:
            return {
                "needed": False,
                "reason": f"Task created only {days_since_created} days ago, too soon for follow-up",
                "confidence": 0.8,
            }

        # Check if we already sent a follow-up recently
        if task.last_reminded_at:
            days_since_reminder = (datetime.now(timezone.utc) - task.last_reminded_at).days
            if days_since_reminder < 5:
                return {
                    "needed": False,
                    "reason": f"Follow-up sent {days_since_reminder} days ago, too soon for another",
                    "confidence": 0.85,
                }

        # Follow-up is needed
        return {
            "needed": True,
            "reason": f"No activity for {days_since_created} days, follow-up appropriate",
            "confidence": 0.88,
            "task": {
                "id": task.id,
                "title": task.title,
                "task_type": task.task_type,
                "days_since_created": days_since_created,
            }
        }

    def check_for_reply(self, task_id: int, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Check if a reply has been received for a waiting_for task

        This checks if there are newer messages in the same thread.

        Args:
            task_id: ID of the task
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Dictionary with reply status
        """
        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            return {
                "reply_received": False,
                "reason": "Task not found",
            }

        # Get source message
        source_message = db.query(Message).filter(
            Message.id == task.message_id
        ).first()

        if not source_message:
            return {
                "reply_received": False,
                "reason": "Source message not found",
            }

        # Check for newer messages in the same thread
        newer_messages = db.query(Message).filter(
            Message.thread_id == source_message.thread_id,
            Message.received_at > source_message.received_at
        ).count()

        if newer_messages > 0:
            return {
                "reply_received": True,
                "reason": f"Found {newer_messages} newer message(s) in thread",
                "newer_messages_count": newer_messages,
            }

        return {
            "reply_received": False,
            "reason": "No newer messages in thread",
        }

    def generate_follow_up(self, task_id: int, db: Session, user_id: str, context: str = None) -> Dict[str, Any]:
        """
        Generate a contextual follow-up message using AI

        Args:
            task_id: ID of the task to follow up on
            db: Database session with RLS context
            user_id: Current user's ID
            context: Optional additional context

        Returns:
            Dictionary with 'follow_up', 'subject_line', 'tone'
        """
        from app.ai_processor import AIProcessor

        task = db.query(Task).filter(Task.id == task_id).first()

        if not task:
            return {
                "follow_up": "Unable to generate follow-up: task not found",
                "subject_line": "",
                "tone": "error"
            }

        # Get source message
        source_message = db.query(Message).filter(
            Message.id == task.message_id
        ).first()

        if not source_message:
            return {
                "follow_up": "Unable to generate follow-up: source message not found",
                "subject_line": "",
                "tone": "error"
            }

        days_since = (datetime.now(timezone.utc) - task.created_at).days

        # Build context for AI
        ai_context = {
            "sender": source_message.sender,
            "subject": source_message.subject,
            "snippet": task.source_snippet or source_message.summary or (source_message.decrypted_body or "")[:500],
            "task_title": task.title,
            "task_type": task.task_type,
            "days_since": days_since,
            "reminder_count": task.reminder_count or 0,
            "additional_context": context or ""
        }

        # Generate using AI
        ai_processor = AIProcessor()
        result = ai_processor.generate_follow_up_message(ai_context)

        return result

    def generate_meeting_follow_ups(self, event_id: int, db: Session, user_id: str) -> Dict[str, Any]:
        """
        Generate follow-up items after a meeting using AI.

        Uses the meeting context to generate relevant:
        - Follow-up tasks
        - Email drafts to attendees
        - Reminders for future actions

        All items require user approval before creation.

        Args:
            event_id: ID of the calendar event
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Dictionary with follow_ups list, reasoning, and status
        """
        from app.ai_processor import AIProcessor
        from sqlalchemy import or_

        event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()

        if not event:
            return {
                "event_id": event_id,
                "follow_ups": [],
                "reasoning": "Event not found",
                "total": 0,
                "status": "error"
            }

        # Get attendee emails (using participants, not attendees)
        attendee_emails = []
        for att in (event.participants or []):
            if att.get('email'):
                attendee_emails.append(att['email'].lower())
        if event.organizer:
            attendee_emails.append(event.organizer.lower())
        attendee_emails = list(set(attendee_emails))

        # Format attendees string
        attendees_str = ", ".join([
            f"{att.get('name', att.get('email', 'Unknown'))} ({att.get('email', '')})"
            for att in (event.participants or [])
        ])

        # Find related messages
        related_messages = []
        if attendee_emails:
            conditions = [Message.sender.ilike(f"%{email}%") for email in attendee_emails]
            if event.title and len(event.title) > 3:
                title_words = [w for w in event.title.split() if len(w) > 3]
                for word in title_words[:3]:
                    conditions.append(Message.subject.ilike(f"%{word}%"))
            related_messages = (
                db.query(Message)
                .filter(or_(*conditions))
                .order_by(Message.received_at.desc())
                .limit(5)
                .all()
            )

        # Find related tasks
        related_tasks = []
        if attendee_emails:
            all_tasks = (
                db.query(Task)
                .filter(Task.status.in_(['approved', 'pending_approval']))
                .order_by(Task.created_at.desc())
                .limit(50)
                .all()
            )
            for task in all_tasks:
                people = task.related_people or []
                for person in people:
                    if any(email in person.lower() for email in attendee_emails):
                        related_tasks.append(task)
                        break
                if len(related_tasks) >= 5:
                    break

        # Format context strings
        emails_summary = "\n".join([
            f"- From {msg.sender}: {msg.subject} ({msg.received_at.strftime('%Y-%m-%d') if msg.received_at else 'Unknown'})"
            for msg in related_messages
        ]) or "No related emails found"

        tasks_summary = "\n".join([
            f"- [{t.status}] {t.title} (type: {t.task_type})"
            for t in related_tasks
        ]) or "No open tasks"

        # Get prep warnings if briefing exists
        prep_warnings_str = "None"
        if event.briefing and event.briefing.get('prep_warnings'):
            prep_warnings_str = "\n".join([
                f"- {w.get('message', 'Unknown warning')}"
                for w in event.briefing['prep_warnings']
            ])

        # Build context for AI
        meeting_context = {
            'title': event.title,
            'meeting_date': event.start_time.isoformat() if event.start_time else 'Unknown',
            'attendees': attendees_str or 'No attendees listed',
            'agenda': event.description or 'No agenda provided',
            'related_emails': emails_summary,
            'open_tasks': tasks_summary,
            'prep_warnings': prep_warnings_str
        }

        # Generate via AI
        ai_processor = AIProcessor()
        ai_result = ai_processor.generate_meeting_followups(meeting_context)

        return {
            'event_id': event.id,
            'event_title': event.title,
            'follow_ups': ai_result.get('follow_ups', []),
            'reasoning': ai_result.get('reasoning', ''),
            'total': len(ai_result.get('follow_ups', [])),
            'status': 'pending_approval'
        }