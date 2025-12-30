"""
Scheduling Module

Handles scheduling intent detection, availability checking, and meeting coordination.
Works with CalendarService for Google Calendar integration.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

import google.genai as genai

from .base import BaseModule
from ...config import settings
from ...database import SessionLocal
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

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        super().__init__()
        self.model_name = model_name
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

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
        prompt = f"""Analyze this email to understand the scheduling context.

Classify into ONE of these intent types:
- "availability_request": Sender is asking when YOU are available to meet
- "time_request": Sender is asking YOU to provide or communicate a meeting time
- "meeting_confirmation": Sender is confirming a specific meeting time
- "meeting_reminder": Sender is reminding about an already-scheduled meeting
- "reschedule_request": Sender wants to change an existing meeting time
- "none": No actionable scheduling intent

Also extract any specific times/dates mentioned.

Subject: {message_subject}

Body:
{message_body[:1500]}

Respond with JSON only:
{{
    "has_intent": true/false,
    "intent_type": "availability_request|time_request|meeting_confirmation|meeting_reminder|reschedule_request|none",
    "confidence": 0.0-1.0,
    "reason": "Brief explanation of what the sender wants",
    "action_required": "What the recipient needs to do",
    "meeting_with": "Name of person to meet with, if mentioned",
    "mentioned_times": ["any specific times/dates mentioned"],
    "detected_phrases": ["key phrases that indicate intent"]
}}"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            result_text = response.text.strip()
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            # Ensure required fields exist
            result.setdefault("intent_type", "none")
            result.setdefault("action_required", "")
            result.setdefault("meeting_with", "")
            result.setdefault("mentioned_times", [])

            return result

        except Exception as e:
            logger.error(f"Error detecting scheduling intent: {e}")
            return {
                "has_intent": False,
                "intent_type": "none",
                "confidence": 0.0,
                "reason": f"Error: {str(e)}",
                "action_required": "",
                "meeting_with": "",
                "mentioned_times": [],
                "detected_phrases": []
            }

    def extract_scheduling_details(
        self,
        message_body: str,
        message_subject: str = "",
        sender_email: str = ""
    ) -> Dict[str, Any]:
        """
        Extract scheduling details from a message.

        Args:
            message_body: The message body
            message_subject: The message subject
            sender_email: The sender's email address

        Returns:
            Dict with participants, time_constraints, meeting_type, duration_minutes, timezone
        """
        prompt = f"""Extract scheduling details from this email.

Subject: {message_subject}
From: {sender_email}

Body:
{message_body[:2000]}

Extract:
1. Participants (email addresses or names mentioned)
2. Time constraints (specific times, date ranges, or relative dates like "next week")
3. Meeting type (call, review, demo, coffee, interview, or other)
4. Duration if mentioned (in minutes)
5. Timezone if mentioned (in IANA format like "America/New_York")

Respond with JSON only:
{{
    "participants": ["email or name"],
    "time_constraints": {{
        "specific_times": ["any specific times mentioned"],
        "date_range": {{
            "start": "YYYY-MM-DD or null",
            "end": "YYYY-MM-DD or null"
        }},
        "relative_reference": "e.g., 'next week', 'tomorrow', or null"
    }},
    "meeting_type": "call|review|demo|coffee|interview|other",
    "duration_minutes": 30,
    "timezone": "detected timezone or null",
    "source_snippet": "the exact text that indicates scheduling intent"
}}"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            result_text = response.text.strip()
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            # Ensure sender is in participants
            if sender_email and sender_email not in result.get("participants", []):
                result["participants"] = [sender_email] + result.get("participants", [])

            return result

        except Exception as e:
            logger.error(f"Error extracting scheduling details: {e}")
            return {
                "participants": [sender_email] if sender_email else [],
                "time_constraints": {},
                "meeting_type": "other",
                "duration_minutes": 30,
                "timezone": None,
                "source_snippet": ""
            }

    def fetch_availability(
        self,
        start_date: str,
        end_date: str,
        duration_minutes: int = 30,
        count: int = 3
    ) -> Dict[str, Any]:
        """
        Fetch available time slots from calendar.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            duration_minutes: Meeting duration
            count: Number of slots to suggest

        Returns:
            Dict with suggested_slots list
        """
        db = SessionLocal()
        try:
            # Get user settings for calendar preferences
            settings = db.query(UserSettings).first()
            if not settings:
                settings = UserSettings(user_email="default@user.com")

            calendar_service = CalendarService(db)

            # Parse dates
            start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

            # Get suggestions using async method (run synchronously)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                slots = loop.run_until_complete(
                    calendar_service.suggest_time_slots(
                        start_date=start,
                        end_date=end,
                        duration_minutes=duration_minutes,
                        count=count,
                        working_hours_start=settings.working_hours_start,
                        working_hours_end=settings.working_hours_end,
                        buffer_minutes=settings.buffer_minutes,
                        preferred_times=settings.preferred_meeting_times,
                        calendar_ids=settings.calendar_ids or None
                    )
                )
            finally:
                loop.close()

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
        finally:
            db.close()

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
        db=None  # Optional: for Principal Memory context
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
        # Get Principal Memory context if db available
        memory_context = ""
        if db and sender_email:
            try:
                from ...context_builder import ContextBuilder
                builder = ContextBuilder(db, user_id="default")
                memory_context = builder.build_context(
                    context_type="scheduling",
                    sender_email=sender_email
                )
            except Exception as e:
                logger.warning(f"Failed to load memory context: {e}")

        # Get timezone abbreviation
        tz_display = timezone_str.split("/")[-1].replace("_", " ") if "/" in timezone_str else timezone_str

        # Format available slots if we have them
        slot_texts = []
        if suggested_slots:
            for slot in suggested_slots[:3]:
                start = datetime.fromisoformat(slot["start_time"].replace('Z', '+00:00'))
                slot_texts.append(start.strftime("%a at %-I%p").replace("AM", "am").replace("PM", "pm"))

        # Build context-specific prompt based on intent type
        if intent_type == "meeting_confirmation":
            # They confirmed a time - acknowledge it
            times_str = ", ".join(mentioned_times) if mentioned_times else "the scheduled time"
            prompt = f"""Generate a brief reply acknowledging a meeting confirmation.

Context:
- Meeting with: {meeting_with or sender_name}
- Confirmed time: {times_str}

Requirements:
- 1 sentence max
- Acknowledge the confirmation
- Express that you'll be there / looking forward to it
- DO NOT use any placeholders like [time] or [name] - use the actual values provided

Example: "Great, I've noted the meeting for tomorrow at 2pm. Looking forward to it."

Generate the reply (text only, no quotes, no placeholders):"""

        elif intent_type == "meeting_reminder":
            # They're reminding about a meeting - acknowledge
            times_str = ", ".join(mentioned_times) if mentioned_times else "tomorrow"
            prompt = f"""Generate a brief reply acknowledging a meeting reminder.

Context:
- Meeting with: {meeting_with or 'the team'}
- When: {times_str}

Requirements:
- 1 sentence max
- Thank them for the reminder
- Confirm you'll be there
- DO NOT use any placeholders - use actual values

Example: "Thanks for the reminder. I'll be there for the meeting with Sarah tomorrow."

Generate the reply (text only, no quotes, no placeholders):"""

        elif intent_type == "time_request":
            # They're asking US to provide a time
            if not slot_texts:
                return "Let me check my calendar and get back to you with available times shortly."

            slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
            prompt = f"""Generate a brief reply providing meeting times.

Context:
- They asked us to communicate/provide a meeting time
- Meeting with: {meeting_with or 'them'}
- Our available times: {slots_formatted}
- Timezone: {tz_display}

Requirements:
- 1-2 sentences max
- Provide the specific available times
- Include timezone
- Ask them to confirm
- DO NOT use placeholders - use the actual times provided above

Example: "For the meeting with Elizabeth, I'm available tomorrow at 10am, 2pm, or 4pm (SAST). Let me know which works best."

Generate the reply (text only, no quotes, no placeholders):"""

        elif intent_type == "reschedule_request":
            # They want to reschedule
            if not slot_texts:
                return "I understand you'd like to reschedule. Let me check my calendar and propose some alternative times."

            slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
            prompt = f"""Generate a brief reply offering alternative times for rescheduling.

Context:
- They want to reschedule an existing meeting
- Our available times: {slots_formatted}
- Timezone: {tz_display}

Requirements:
- 1-2 sentences max
- Acknowledge the reschedule request
- Offer the alternative times
- DO NOT use placeholders

Example: "No problem, we can reschedule. I'm available Wed at 11am, Thu at 2pm, or Fri at 10am (SAST)."

Generate the reply (text only, no quotes, no placeholders):"""

        else:  # availability_request or default
            # Standard availability response
            if not slot_texts:
                return "I'll check my calendar and get back to you with some available times."

            slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]

            # Add memory context if available
            memory_section = f"\n- User preferences: {memory_context}" if memory_context else ""

            prompt = f"""Generate a brief, professional scheduling reply.

Context:
- Meeting type: {meeting_type}
- Available times: {slots_formatted}
- Timezone: {tz_display}
- Meeting with: {sender_name or 'them'}{memory_section}

Requirements:
- 1-2 sentences max
- Mention the available times exactly as provided
- Include timezone
- Ask them to confirm
- Apply any user preferences mentioned above (tone, formality, etc.)
- DO NOT use placeholders - use the actual times

Example: "I'm available Tue at 11am, Wed at 2pm, or Thu at 10am (SAST). Let me know what works for you."

Generate the reply (text only, no quotes, no placeholders):"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            reply = response.text.strip().strip('"').strip("'")

            # Safety check: reject if it contains obvious placeholders
            placeholder_patterns = ["[", "]", "{", "}", "INSERT", "TIME HERE", "NAME HERE"]
            if any(p in reply.upper() for p in placeholder_patterns):
                logger.warning(f"AI generated placeholder text, using fallback: {reply}")
                # Use fallback based on intent
                if intent_type in ["meeting_confirmation", "meeting_reminder"]:
                    times_str = mentioned_times[0] if mentioned_times else "the scheduled time"
                    return f"Thanks for the reminder about the meeting {times_str}. I'll be there."
                elif slot_texts:
                    slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
                    return f"I'm available {slots_formatted} ({tz_display}). Let me know what works."
                else:
                    return "I'll check my calendar and get back to you shortly."

            return reply

        except Exception as e:
            logger.error(f"Error generating draft reply: {e}")
            # Fallback templates based on intent
            if intent_type in ["meeting_confirmation", "meeting_reminder"]:
                return "Thanks for the reminder. I'll be there."
            elif slot_texts:
                slots_formatted = ", ".join(slot_texts[:-1]) + f", or {slot_texts[-1]}" if len(slot_texts) > 1 else slot_texts[0]
                return f"I'm available {slots_formatted} ({tz_display}). Let me know what works."
            else:
                return "I'll check my calendar and get back to you with available times."

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
        prompt = f"""Generate a brief calendar event description based on this email context.

Meeting type: {meeting_type}
Participants: {', '.join(participants)}

Email context:
{message_body[:1000]}

Requirements:
- Start with a one-line summary
- Extract any discussion points or agenda items mentioned
- Keep it concise (3-5 lines max)
- Professional tone

Generate the description (plain text, no markdown):"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()

        except Exception as e:
            logger.error(f"Error generating event description: {e}")
            return f"{meeting_type.title()} with {', '.join(participants)}"

    def generate_suggestions(
        self,
        message_id: int,
        message_body: str,
        message_subject: str,
        sender_email: str,
        thread_id: str
    ) -> Dict[str, Any]:
        """
        Full pipeline: detect intent, extract details, fetch availability, generate drafts.

        Args:
            message_id: Database ID of the message
            message_body: Message body text
            message_subject: Message subject
            sender_email: Sender's email
            thread_id: Thread ID for tracking

        Returns:
            Dict with suggestion data or None if no scheduling intent
        """
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
            except:
                start_date = now
        else:
            start_date = now

        if time_constraints.get("date_range", {}).get("end"):
            try:
                end_date = datetime.fromisoformat(time_constraints["date_range"]["end"])
            except:
                end_date = now + timedelta(days=14)
        else:
            # Default to next 2 weeks
            end_date = now + timedelta(days=14)

        # Step 4: Fetch availability
        duration = details.get("duration_minutes", 30)
        availability = self.fetch_availability(
            start_date.isoformat(),
            end_date.isoformat(),
            duration_minutes=duration,
            count=3
        )

        suggested_slots = availability.get("suggested_slots", [])
        user_timezone = availability.get("timezone", "UTC")

        # Step 5: Generate draft reply with intent context
        sender_name = sender_email.split("@")[0] if sender_email else ""
        intent_type = intent.get("intent_type", "availability_request")
        meeting_with = intent.get("meeting_with", "")
        mentioned_times = intent.get("mentioned_times", [])

        # Get db session for Principal Memory context
        db = SessionLocal()
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
                db=db
            )
        finally:
            db.close()

        # Step 6: Generate event description
        draft_description = self.generate_event_description(
            message_body,
            details.get("meeting_type", "meeting"),
            details.get("participants", [])
        )

        # Step 7: Save to database
        db = SessionLocal()
        try:
            suggestion = SchedulingSuggestion(
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
            logger.error(f"Error saving suggestion: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            db.close()

    def create_calendar_event(
        self,
        suggestion_id: int,
        selected_slot_index: int = 0,
        title: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a calendar event from a scheduling suggestion.

        Args:
            suggestion_id: ID of the SchedulingSuggestion
            selected_slot_index: Which suggested slot to use (0-indexed)
            title: Optional custom title (uses default if not provided)
            description: Optional custom description
            location: Optional meeting location/link

        Returns:
            Dict with created event details
        """
        db = SessionLocal()
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
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    calendar_service.create_event(
                        title=title,
                        start_time=start_time,
                        end_time=end_time,
                        description=description,
                        attendees=suggestion.participants,
                        location=location,
                        timezone_str=suggestion.timezone
                    )
                )
            finally:
                loop.close()

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
        finally:
            db.close()
