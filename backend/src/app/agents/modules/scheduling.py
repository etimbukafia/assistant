"""
Scheduling Module

Handles scheduling intent detection, availability checking, and meeting coordination.
Works with CalendarService for Google Calendar integration.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from .base import BaseModule
from ...calendar_service import CalendarService, TimeSlot
from ...models import UserSettings, SchedulingSuggestion, CalendarEvent, Message

logger = logging.getLogger(__name__)


class SchedulingModule(BaseModule):
    """
    Module for scheduling coordination and calendar management.

    Capabilities:
    - Detect scheduling intent in messages
    - Extract scheduling details (participants, times, meeting type)
    - Fetch calendar availability
    - Generate time slot suggestions
    - Draft scheduling replies
    - Create calendar events (after user approval)
    """

    def get_capabilities(self) -> Dict[str, str]:
        return {
            "detect_scheduling_intent": "Detect if a message contains scheduling intent",
            "extract_scheduling_details": "Extract participants, times, and meeting type from message",
            "fetch_availability": "Get available time slots from calendar",
            "generate_suggestions": "Generate scheduling suggestions with draft reply",
            "create_calendar_event": "Create a calendar event after user approval",
        }

    def detect_scheduling_intent(self, message_body: str, message_subject: str = "") -> Dict[str, Any]:
        """
        Detect if a message contains scheduling intent and classify the type.

        Intent types:
        - availability_request: They're asking when you're free
        - time_request: They're asking you to provide/confirm a specific time
        - meeting_confirmation: They're confirming a time that was discussed
        - meeting_reminder: Reminding about an existing meeting
        - reschedule_request: They want to change an existing meeting
        - none: No actionable scheduling intent

        Args:
            message_body: The message body text
            message_subject: The message subject

        Returns:
            Dict with has_intent, intent_type, confidence, and extracted details
        """

        prompt_template = self._load_prompt('detect_scheduling_intent')
        prompt = prompt_template.format(body=message_body, subject=message_subject)

        try:
            result = self._orchestrator.generate(prompt)
            if result.get("_error"):
                # Fallback
                return {"has_intent": False, "intent_type": "none", "confidence": 0.0}
            
            # Map DB fields if needed, usually direct return is fine if prompt matches schema
            return {
                "has_intent": result.get("detected", False),
                "intent_type": result.get("type", "none"),
                "confidence": result.get("confidence", 0.0),
                "meeting_with": result.get("meeting_with", ""),
                "mentioned_times": result.get("mentioned_times", [])
            }
        except Exception as e:
            logger.error(f"Error detecting scheduling intent: {e}")
            return {"has_intent": False, "intent_type": "none", "confidence": 0.0}

    def extract_scheduling_details(
        self,
        message_body: str,
        message_subject: str = "",
        sender_email: str = "",
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Extract scheduling details from a message.

        Args:
            message_body: The message body
            message_subject: The message subject
            sender_email: The sender's email address
            db: Optional database session for Principal Memory context

        Returns:
            Dict with participants, time_constraints, meeting_type, duration_minutes, timezone
        """

        prompt_template = self._load_prompt('extract_scheduling_details')
        prompt = prompt_template.format(
            body=message_body, 
            subject=message_subject,
            sender=sender_email
        )

        try:
            result = self._orchestrator.generate(prompt)
            if result.get("_error"):
                logger.warning("Failed to parse extract_scheduling_details response")
                return {}
            return result
        except Exception as e:
            logger.error(f"Error extracting scheduling details: {e}")
            return {}

    def fetch_availability(
        self,
        start_date: str,
        end_date: str,
        duration_minutes: int = 30,
        count: int = 3,
        db: Session = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Fetch available time slots from calendar.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            duration_minutes: Meeting duration
            count: Number of slots to suggest
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Dict with suggested_slots list
        """
        if not db or not user_id:
            return {
                "success": False,
                "error": "Database session and user_id are required",
                "suggested_slots": [],
                "timezone": "UTC"
            }

        try:
            # Get user settings for calendar preferences (filtered by RLS)
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                return {
                    "success": False,
                    "error": "User settings not found - please complete account setup",
                    "suggested_slots": [],
                    "timezone": "UTC"
                }

            calendar_service = CalendarService(db)

            # Parse dates
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

            # Get suggestions using async method
            import asyncio
            
            coro = calendar_service.suggest_time_slots(
                start_date=start,
                end_date=end,
                duration_minutes=duration_minutes,
                count=count,
                working_hours_start=settings.working_hours_start,
                working_hours_end=settings.working_hours_end,
                buffer_minutes=settings.buffer_minutes,
                preferred_times=settings.preferred_meeting_times,
                calendar_ids=settings.calendar_ids
            )
            
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, use nest_asyncio or run directly
                import nest_asyncio
                nest_asyncio.apply()
                slots = loop.run_until_complete(coro)
            except RuntimeError:
                # No running loop, create one
                slots = asyncio.run(coro)

            return {
                "success": True,
                "suggested_slots": [slot.to_dict() for slot in slots],
                "timezone": settings.default_timezone
            }

        except Exception as e:
            logger.error(f"Error fetching availability: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggested_slots": [],
                "timezone": "UTC"
            }

    def get_availability_context_string(
        self,
        db: Session,
        user_id: str,
        days: int = 14
    ) -> str:
        """
        Get a formatted string of availability for context injection.
        """
        try:
            from datetime import datetime, timezone, timedelta
            start = datetime.now(timezone.utc)
            end = start + timedelta(days=days)
            
            result = self.fetch_availability(
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                duration_minutes=30,
                count=5,
                db=db,
                user_id=user_id
            )
            
            if not result.get("success") or not result.get("suggested_slots"):
                return ""
                
            slots = result.get("suggested_slots", [])
            tz = result.get("timezone", "UTC")
            
            slot_texts = []
            for slot in slots:
                # slot['start_time'] is ISO string
                dt = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00'))
                slot_texts.append(dt.strftime("%A at %-I:%M%p").replace("AM", "am").replace("PM", "pm"))
            
            return f"\n- **Your available times ({tz}):** {', '.join(slot_texts)}"
            
        except Exception as e:
            logger.error(f"Error generating availability context string: {e}")
            return ""

    def generate_draft_reply(
        self,
        intent_type: str,
        suggested_slots: List[Dict[str, Any]],
        meeting_type: str,
        timezone_str: str,
        sender_name: str = "",
        meeting_with: str = "",
        mentioned_times: List[str] = None,
        sender_email: str = "",
        db: Session = None,
        user_id: str = None
    ) -> str:
        """
        Generate a context-appropriate scheduling reply based on intent type.

        Args:
            intent_type: Type of scheduling intent detected
            suggested_slots: List of suggested time slots from calendar
            meeting_type: Type of meeting
            timezone_str: Timezone for display
            sender_name: Name of person who sent the email
            meeting_with: Name of person to meet with (may differ from sender)
            mentioned_times: Any times mentioned in the original email
            sender_email: Sender's email for contact context
            db: Optional database session for Principal Memory

        Returns:
            Draft reply text
        """

        pass # imports removed

        # Get Principal Memory context if db available
        memory_context = ""
        if db and sender_email and user_id:
            try:
                from ...context_builder import ContextBuilder
                builder = ContextBuilder(db, user_id=user_id)
                memory_context = builder.get_context_summary(
                    context_type="scheduling",
                    sender_email=sender_email
                ).get("summary", "")
            except Exception as e:
                logger.warning(f"Failed to load memory context: {e}")

        # Get timezone abbreviation
        tz_display = timezone_str.split("/")[-1].replace("_", " ") if "/" in timezone_str else timezone_str

        # Format available slots if we have them
        slot_texts = []
        if suggested_slots:
            for slot in suggested_slots[:3]:
                start = datetime.fromisoformat(slot["start_time"].replace('Z', '+00:00'))
                slot_texts.append(start.strftime("%a at %I%p").lstrip("0").replace("AM", "am").replace("PM", "pm"))

        # Build context based on intent type
        if intent_type == "meeting_confirmation":
            times_str = ", ".join(mentioned_times) if mentioned_times else "the scheduled time"
            context_details = f"""- Meeting with: {meeting_with or sender_name}
- Confirmed time: {times_str}"""
            example = "Great, I've noted the meeting for tomorrow at 2pm. Looking forward to it."
            sentence_limit = "1 sentence max"
            additional_requirements = "Acknowledge the confirmation\n- Express that you'll be there / looking forward to it"

        elif intent_type == "meeting_reminder":
            times_str = ", ".join(mentioned_times) if mentioned_times else "tomorrow"
            context_details = f"""- Meeting with: {meeting_with or 'the team'}
- When: {times_str}"""
            example = "Thanks for the reminder. I'll be there for the meeting with Sarah tomorrow."
            sentence_limit = "1 sentence max"
            additional_requirements = "Thank them for the reminder\n- Confirm you'll be there"

        elif intent_type == "time_request":
            if not slot_texts:
                return "Let me check my calendar and get back to you with available times shortly."

            slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
            context_details = f"""- They asked us to communicate/provide a meeting time
- Meeting with: {meeting_with or 'them'}
- Our available times: {slots_formatted}
- Timezone: {tz_display}"""
            example = f"For the meeting with Elizabeth, I'm available tomorrow at 10am, 2pm, or 4pm (SAST). Let me know which works best."
            sentence_limit = "1-2 sentences max"
            additional_requirements = "Provide the specific available times\n- Include timezone\n- Ask them to confirm"

        elif intent_type == "reschedule_request":
            if not slot_texts:
                return "I understand you'd like to reschedule. Let me check my calendar and propose some alternative times."

            slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
            context_details = f"""- They want to reschedule an existing meeting
- Our available times: {slots_formatted}
- Timezone: {tz_display}"""
            example = "No problem, we can reschedule. I'm available Wed at 11am, Thu at 2pm, or Fri at 10am (SAST)."
            sentence_limit = "1-2 sentences max"
            additional_requirements = "Acknowledge the reschedule request\n- Offer the alternative times"

        else:  # availability_request or default
            if not slot_texts:
                return "I'll check my calendar and get back to you with some available times."

            slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
            memory_section = f"\n- User preferences: {memory_context}" if memory_context else ""
            context_details = f"""- Meeting type: {meeting_type}
- Available times: {slots_formatted}
- Timezone: {tz_display}
- Meeting with: {sender_name or 'them'}{memory_section}"""
            example = "I'm available Tue at 11am, Wed at 2pm, or Thu at 10am (SAST). Let me know what works for you."
            sentence_limit = "1-2 sentences max"
            additional_requirements = "Mention the available times exactly as provided\n- Include timezone\n- Ask them to confirm"
            if memory_context:
                additional_requirements += "\n- Apply any user preferences mentioned above (tone, formality, etc.)"

        # Generate draft directly using BaseModule's orchestrator
        prompt_template = self._load_prompt('scheduling_draft_reply')
        
        prompt = prompt_template.format(
            intent_type=intent_type,
            context_details=context_details,
            sentence_limit=sentence_limit,
            tone_guidance="Professional and friendly",
            additional_requirements=additional_requirements,
            example=f"Example: \"{example}\""
        )
        
        try:
            result = self._orchestrator.generate(prompt)
            return result.get('reply', '')
        except Exception as e:
            logger.error(f"Error generating scheduling reply: {e}")
            return ""

    def generate_event_description(
        self,
        message_body: str,
        meeting_type: str,
        participants: List[str]
    ) -> str:
        """
        Generate a calendar event description from email context.

        Args:
            message_body: Original message body
            meeting_type: Type of meeting
            participants: List of participant emails

        Returns:
            Event description text
        """

        # Inline generation
        prompt_template = self._load_prompt('generate_event_description')
        prompt = prompt_template.format(
            body=message_body,
            meeting_type=meeting_type,
            participants=", ".join(participants)
        )
        try:
            result = self._orchestrator.generate(prompt)
            return result.get("description", "")
        except Exception as e:
            logger.error(f"Error generating event description: {e}")
            return ""

    def generate_suggestions(
        self,
        message_id: int,
        message_body: str,
        message_subject: str,
        sender_email: str,
        thread_id: str,
        db: Session = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Full pipeline: detect intent, extract details, fetch availability, generate drafts.

        Args:
            message_id: Database ID of the message
            message_body: Message body text
            message_subject: Message subject
            sender_email: Sender's email
            thread_id: Thread ID for tracking
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Dict with suggestion data or None if no scheduling intent
        """
        if not db or not user_id:
            return {
                "success": False,
                "reason": "Database session and user_id are required"
            }
        # Step 1: Detect scheduling intent
        intent = self.detect_scheduling_intent(message_body, message_subject)

        if not intent.get("has_intent") or intent.get("confidence", 0) < 0.6:
            return {
                "success": False,
                "reason": "No scheduling intent detected",
                "intent": intent
            }

        # Step 2: Extract scheduling details
        details = self.extract_scheduling_details(message_body, message_subject, sender_email)

        # Step 3: Determine date range to search
        now = datetime.now(timezone.utc)
        time_constraints = details.get("time_constraints", {})

        if time_constraints.get("date_range", {}).get("start"):
            try:
                start_date = datetime.fromisoformat(time_constraints["date_range"]["start"])
            except (ValueError, TypeError):
                start_date = now
        else:
            start_date = now

        if time_constraints.get("date_range", {}).get("end"):
            try:
                end_date = datetime.fromisoformat(time_constraints["date_range"]["end"])
            except (ValueError, TypeError):
                end_date = now + timedelta(days=14)
        else:
            # Default to next 2 weeks
            end_date = now + timedelta(days=14)

        # Step 4: Fetch availability
        duration = details.get("duration_minutes") or 30
        availability = self.fetch_availability(
            start_date.isoformat(),
            end_date.isoformat(),
            duration_minutes=duration,
            count=3,
            db=db,
            user_id=user_id
        )

        suggested_slots = availability.get("suggested_slots", [])
        user_timezone = availability.get("timezone", "UTC")

        # Step 5: Generate draft reply with intent context
        sender_name = sender_email.split("@")[0] if sender_email else ""
        intent_type = intent.get("intent_type", "availability_request")
        meeting_with = intent.get("meeting_with", "")
        mentioned_times = intent.get("mentioned_times", [])

        # Generate draft reply with Principal Memory context
        try:
            draft_reply = self.generate_draft_reply(
                intent_type=intent_type,
                suggested_slots=suggested_slots,
                meeting_type=details.get("meeting_type", "meeting"),
                timezone_str=user_timezone,
                sender_name=sender_name,
                meeting_with=meeting_with,
                mentioned_times=mentioned_times,
                sender_email=sender_email,
                db=db,
                user_id=user_id
            )

            # Step 6: Generate event description
            draft_description = self.generate_event_description(
                message_body,
                details.get("meeting_type", "meeting"),
                details.get("participants", [])
            )

            # Step 7: Save to database
            suggestion = SchedulingSuggestion(
                user_id=user_id,
                thread_id=thread_id,
                message_id=message_id,
                participants=details.get("participants", []),
                suggested_slots=suggested_slots,
                time_window_start=start_date,
                time_window_end=end_date,
                timezone=user_timezone,
                meeting_type=details.get("meeting_type", "other"),
                duration_minutes=duration,
                intent_type=intent_type,
                source_text_snippet=details.get("source_snippet", ""),
                draft_reply=draft_reply,
                draft_event_description=draft_description,
                status="pending"
            )

            # Expire previous suggestions for same thread
            db.query(SchedulingSuggestion).filter(
                SchedulingSuggestion.thread_id == thread_id,
                SchedulingSuggestion.status == "pending"
            ).update({"status": "expired"})

            db.add(suggestion)
            db.commit()
            db.refresh(suggestion)

            return {
                "success": True,
                "suggestion_id": suggestion.id,
                "participants": suggestion.participants,
                "suggested_slots": suggestion.suggested_slots,
                "meeting_type": suggestion.meeting_type,
                "duration_minutes": suggestion.duration_minutes,
                "intent_type": suggestion.intent_type,
                "timezone": suggestion.timezone,
                "draft_reply": suggestion.draft_reply,
                "draft_event_description": suggestion.draft_event_description,
                "status": suggestion.status
            }

        except Exception as e:
            logger.error(f"Error generating or saving suggestion: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    def create_calendar_event(
        self,
        suggestion_id: int,
        selected_slot_index: int = 0,
        title: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        db: Session = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a calendar event from a scheduling suggestion.

        Args:
            suggestion_id: ID of the SchedulingSuggestion
            selected_slot_index: Which suggested slot to use (0-indexed)
            title: Optional custom title (uses default if not provided)
            description: Optional custom description
            location: Optional meeting location/link
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Dict with created event details
        """
        if not db or not user_id:
            return {"success": False, "error": "Database session and user_id are required"}

        try:
            # Get suggestion
            suggestion = db.query(SchedulingSuggestion).filter(
                SchedulingSuggestion.id == suggestion_id
            ).first()

            if not suggestion:
                return {"success": False, "error": "Suggestion not found"}

            if not suggestion.suggested_slots:
                return {"success": False, "error": "No suggested slots available"}

            if selected_slot_index >= len(suggestion.suggested_slots):
                return {"success": False, "error": "Invalid slot index"}

            slot = suggestion.suggested_slots[selected_slot_index]
            start_time = datetime.fromisoformat(slot["start_time"].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(slot["end_time"].replace('Z', '+00:00'))

            # Default title
            if not title:
                participants_str = ", ".join(suggestion.participants[:2])
                title = f"{suggestion.meeting_type.title()} with {participants_str}"

            # Use suggestion's draft description if not provided
            if not description:
                description = suggestion.draft_event_description

            # Create CalendarEvent record
            calendar_event = CalendarEvent(
                user_id=user_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                participants=suggestion.participants,
                timezone=suggestion.timezone,
                location=location,
                source_message_id=suggestion.message_id,
                source_suggestion_id=suggestion.id,
                provider="google",
                status="pending"
            )
            db.add(calendar_event)
            db.commit()
            db.refresh(calendar_event)

            # Create in Google Calendar
            calendar_service = CalendarService(db)

            import asyncio
            
            coro = calendar_service.create_event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                attendees=suggestion.participants,
                location=location,
                timezone_str=suggestion.timezone
            )
            
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                import nest_asyncio
                nest_asyncio.apply()
                result = loop.run_until_complete(coro)
            except RuntimeError:
                result = asyncio.run(coro)

            # Update records
            calendar_event.external_event_id = result.get("external_event_id")
            calendar_event.status = "created"
            suggestion.status = "accepted"
            db.commit()

            return {
                "success": True,
                "event_id": calendar_event.id,
                "external_event_id": calendar_event.external_event_id,
                "html_link": result.get("html_link"),
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            # Update status to failed
            if 'calendar_event' in locals():
                calendar_event.status = "failed"
                calendar_event.error_message = str(e)
                db.commit()
            return {
                "success": False,
                "error": str(e)
            }
