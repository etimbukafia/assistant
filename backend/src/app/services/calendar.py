"""
Calendar Service - Google Calendar API Integration

Uses the same OAuth credentials as Gmail to access Google Calendar.
Provides availability checking and event creation.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.security.encryption import decrypt_token
from app.integrations.gmail import SCOPES
from app.infra.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BusySlot:
    """Represents a busy time slot from calendar"""
    start: datetime
    end: datetime
    calendar_id: str = "primary"


@dataclass
class CalendarInfo:
    """Basic calendar information"""
    id: str
    summary: str
    primary: bool = False
    access_role: str = "reader"


@dataclass
class TimeSlot:
    """A proposed time slot for scheduling"""
    start_time: datetime
    end_time: datetime
    has_conflict: bool = False
    conflict_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "has_conflict": self.has_conflict,
            "conflict_details": self.conflict_details,
        }


class CalendarService:
    """
    Service for Google Calendar integration.

    Uses the same OAuth credentials stored for Gmail.
    """

    def __init__(self, db: Session):
        """
        Initialize CalendarService with database session.

        Args:
            db: SQLAlchemy database session for loading credentials
        """
        self.db = db
        self.service = None

    def _load_credentials(self, email: Optional[str] = None) -> Optional[Credentials]:
        """
        Load and decrypt Google credentials from database.

        Args:
            email: Specific email account (uses first account if None)

        Returns:
            Credentials object or None if not found
        """
        from app.data.models import GmailAccount
        import json

        # Get account from database
        query = self.db.query(GmailAccount)
        if email:
            account = query.filter(GmailAccount.email == email).first()
        else:
            account = query.first()

        if not account:
            logger.warning("No Gmail account found in database")
            return None

        try:
            access_token = decrypt_token(account.access_token)
            refresh_token = decrypt_token(account.refresh_token) if account.refresh_token else None
        except ValueError as e:
            logger.error(f"Failed to decrypt tokens: {e}")
            return None

        # Handle timezone-aware datetime
        token_expiry = account.token_expiry
        if token_expiry and hasattr(token_expiry, 'tzinfo') and token_expiry.tzinfo is not None:
            token_expiry = token_expiry.replace(tzinfo=None)

        # Load client credentials from environment
        settings = get_settings()
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET

        if not client_id or not client_secret:
            logger.error("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not configured")
            return None

        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
            expiry=token_expiry
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save updated tokens
                from app.security.encryption import encrypt_token
                account.access_token = encrypt_token(creds.token)
                if creds.refresh_token:
                    account.refresh_token = encrypt_token(creds.refresh_token)
                account.token_expiry = creds.expiry
                account.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                logger.info("Refreshed expired credentials")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                return None

        return creds if creds.valid else None

    def _get_service(self):
        """Get or create Calendar API service"""
        if self.service is None:
            creds = self._load_credentials()
            if creds is None:
                raise Exception("Calendar not authenticated. Please connect your Google account.")
            self.service = build('calendar', 'v3', credentials=creds)
        return self.service

    async def get_calendars(self) -> List[CalendarInfo]:
        """
        Get list of user's calendars.

        Returns:
            List of CalendarInfo objects
        """
        try:
            service = self._get_service()
            calendar_list = service.calendarList().list().execute()

            calendars = []
            for cal in calendar_list.get('items', []):
                calendars.append(CalendarInfo(
                    id=cal['id'],
                    summary=cal.get('summary', 'Unnamed Calendar'),
                    primary=cal.get('primary', False),
                    access_role=cal.get('accessRole', 'reader')
                ))

            return calendars

        except Exception as e:
            logger.error(f"Failed to get calendars: {e}")
            raise

    async def get_availability(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_ids: Optional[List[str]] = None
    ) -> List[BusySlot]:
        """
        Get busy time slots for the specified time range.

        Args:
            start_time: Start of time range to check
            end_time: End of time range to check
            calendar_ids: List of calendar IDs to check (uses primary if None)

        Returns:
            List of BusySlot objects representing busy times
        """
        try:
            service = self._get_service()

            # Default to primary calendar
            if not calendar_ids:
                calendar_ids = ["primary"]

            # Build freebusy request
            body = {
                "timeMin": start_time.isoformat(),
                "timeMax": end_time.isoformat(),
                "items": [{"id": cal_id} for cal_id in calendar_ids]
            }

            result = service.freebusy().query(body=body).execute()

            busy_slots = []
            for cal_id, cal_data in result.get('calendars', {}).items():
                for busy in cal_data.get('busy', []):
                    busy_slots.append(BusySlot(
                        start=datetime.fromisoformat(busy['start'].replace('Z', '+00:00')),
                        end=datetime.fromisoformat(busy['end'].replace('Z', '+00:00')),
                        calendar_id=cal_id
                    ))

            # Sort by start time
            busy_slots.sort(key=lambda x: x.start)

            return busy_slots

        except Exception as e:
            logger.error(f"Failed to get availability: {e}")
            raise

    def _check_slot_conflicts(
        self,
        slot_start: datetime,
        slot_end: datetime,
        busy_slots: List[BusySlot]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a time slot conflicts with any busy slots.

        Returns:
            Tuple of (has_conflict, conflict_details)
        """
        for busy in busy_slots:
            # Check for overlap
            if slot_start < busy.end and slot_end > busy.start:
                # Format conflict details
                conflict_time = f"{busy.start.strftime('%H:%M')}–{busy.end.strftime('%H:%M')}"
                return True, f"Busy ({conflict_time})"

        return False, None

    async def suggest_time_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 30,
        count: int = 3,
        working_hours_start: str = "09:00",
        working_hours_end: str = "17:00",
        buffer_minutes: int = 15,
        preferred_times: str = "any",
        calendar_ids: Optional[List[str]] = None
    ) -> List[TimeSlot]:
        """
        Suggest available time slots within the given date range.

        Args:
            start_date: Start of date range to search
            end_date: End of date range to search
            duration_minutes: Meeting duration in minutes
            count: Number of slots to suggest
            working_hours_start: Start of working hours (HH:MM)
            working_hours_end: End of working hours (HH:MM)
            buffer_minutes: Buffer time between meetings
            preferred_times: "morning", "afternoon", or "any"
            calendar_ids: Calendar IDs to check

        Returns:
            List of TimeSlot objects
        """
        try:
            # Defensive: ensure numeric params are not None
            duration_minutes = duration_minutes or 30
            buffer_minutes = buffer_minutes or 15

            # Get busy slots for the range
            busy_slots = await self.get_availability(start_date, end_date, calendar_ids)

            # Parse working hours
            work_start_hour, work_start_min = map(int, working_hours_start.split(':'))
            work_end_hour, work_end_min = map(int, working_hours_end.split(':'))

            suggestions = []
            current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

            while len(suggestions) < count and current_date < end_date:
                # Skip weekends
                if current_date.weekday() >= 5:
                    current_date += timedelta(days=1)
                    continue

                # Determine time range based on preference
                if preferred_times == "morning":
                    day_start_hour = work_start_hour
                    day_end_hour = 12
                elif preferred_times == "afternoon":
                    day_start_hour = 12
                    day_end_hour = work_end_hour
                else:
                    day_start_hour = work_start_hour
                    day_end_hour = work_end_hour

                # Generate candidate slots for this day
                slot_start = current_date.replace(
                    hour=day_start_hour,
                    minute=work_start_min if day_start_hour == work_start_hour else 0
                )
                day_end = current_date.replace(
                    hour=day_end_hour,
                    minute=work_end_min if day_end_hour == work_end_hour else 0
                )

                while slot_start + timedelta(minutes=duration_minutes) <= day_end:
                    slot_end = slot_start + timedelta(minutes=duration_minutes)

                    # Skip if slot is in the past
                    if slot_start < datetime.now(timezone.utc):
                        slot_start = slot_end + timedelta(minutes=buffer_minutes)
                        continue

                    # Check for conflicts
                    has_conflict, conflict_details = self._check_slot_conflicts(
                        slot_start, slot_end, busy_slots
                    )

                    # Only suggest non-conflicting slots
                    if not has_conflict:
                        suggestions.append(TimeSlot(
                            start_time=slot_start,
                            end_time=slot_end,
                            has_conflict=False,
                            conflict_details=None
                        ))

                        if len(suggestions) >= count:
                            break

                        # Skip past this slot plus buffer
                        slot_start = slot_end + timedelta(minutes=buffer_minutes)
                    else:
                        # Try next 30-minute slot
                        slot_start += timedelta(minutes=30)

                current_date += timedelta(days=1)

            return suggestions

        except Exception as e:
            logger.error(f"Failed to suggest time slots: {e}")
            raise

    async def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        location: Optional[str] = None,
        timezone_str: str = "UTC",
        calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        """
        Create a calendar event.

        Args:
            title: Event title
            start_time: Event start time
            end_time: Event end time
            description: Event description
            attendees: List of attendee email addresses
            location: Event location or meeting link
            timezone_str: Timezone for the event
            calendar_id: Calendar to create event in

        Returns:
            Created event data including external_event_id
        """
        try:
            service = self._get_service()

            event = {
                'summary': title,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone_str,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone_str,
                },
            }

            if description:
                event['description'] = description

            if location:
                event['location'] = location

            if attendees:
                # Extract clean emails from "Name <email>" format and filter invalid
                import re
                clean_attendees = []
                for a in attendees:
                    if not a:
                        continue
                    # Check if it's "Name <email>" format
                    match = re.search(r'<([^>]+@[^>]+)>', a)
                    if match:
                        email = match.group(1).strip()
                    else:
                        email = a.strip()
                    # Basic email validation
                    if '@' in email and '.' in email.split('@')[-1]:
                        clean_attendees.append(email)
                    else:
                        logger.warning(f"Skipping invalid attendee email: {a}")
                
                if clean_attendees:
                    event['attendees'] = [{'email': email} for email in clean_attendees]

            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='all' if attendees else 'none'
            ).execute()

            logger.info(f"Created calendar event: {created_event.get('id')}")

            return {
                'external_event_id': created_event.get('id'),
                'html_link': created_event.get('htmlLink'),
                'status': 'created',
            }

        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            raise

    async def get_event(self, event_id: str, calendar_id: str = "primary") -> Optional[Dict[str, Any]]:
        """
        Get a specific calendar event.

        Args:
            event_id: The event ID from Google Calendar
            calendar_id: Calendar containing the event

        Returns:
            Event data or None if not found
        """
        try:
            service = self._get_service()
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return event
        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None

    async def get_upcoming_events(
        self,
        days_ahead: int = 7,
        calendar_ids: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events from Google Calendar.

        Args:
            days_ahead: Number of days to look ahead
            calendar_ids: Calendars to fetch from (uses primary if None)
            max_results: Maximum events per calendar

        Returns:
            List of normalized event dicts
        """
        try:
            service = self._get_service()

            if not calendar_ids:
                calendar_ids = ["primary"]

            now = datetime.now(timezone.utc)
            time_max = now + timedelta(days=days_ahead)

            all_events = []

            for cal_id in calendar_ids:
                events_result = service.events().list(
                    calendarId=cal_id,
                    timeMin=now.isoformat(),
                    timeMax=time_max.isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()

                for event in events_result.get('items', []):
                    # Skip all-day events
                    if 'dateTime' not in event.get('start', {}):
                        continue

                    all_events.append(self._normalize_event(event, cal_id))

            all_events.sort(key=lambda x: x['start_time'])
            return all_events

        except Exception as e:
            logger.error(f"Failed to get upcoming events: {e}")
            raise

    def _normalize_event(self, event: Dict[str, Any], calendar_id: str) -> Dict[str, Any]:
        """Normalize Google Calendar event to our format."""
        start = event.get('start', {})
        end = event.get('end', {})

        attendees = [
            {
                'email': att.get('email'),
                'name': att.get('displayName'),
                'response_status': att.get('responseStatus')
            }
            for att in event.get('attendees', [])
        ]

        return {
            'external_event_id': event.get('id'),
            'calendar_id': calendar_id,
            'title': event.get('summary', 'No Title'),
            'description': event.get('description'),
            'start_time': datetime.fromisoformat(start.get('dateTime').replace('Z', '+00:00')),
            'end_time': datetime.fromisoformat(end.get('dateTime').replace('Z', '+00:00')),
            'timezone': start.get('timeZone', 'UTC'),
            'location': event.get('location'),
            'organizer': event.get('organizer', {}).get('email'),
            'attendees': attendees,
            'status': event.get('status', 'confirmed')
        }

    async def sync_upcoming_events(self, days_ahead: int = 7, briefing_hours_before: int = 2) -> Dict[str, int]:
        """
        Sync upcoming events from Google Calendar to database.
        Schedules briefing generation for new events.

        Args:
            days_ahead: Number of days to look ahead
            briefing_hours_before: Hours before meeting to generate briefing

        Returns:
            Dict with created, updated, unchanged counts
        """
        from app.data.models import CalendarEvent
        from app.jobs.task_queue import enqueue_task

        events = await self.get_upcoming_events(days_ahead=days_ahead)
        now = datetime.now(timezone.utc)

        created = 0
        updated = 0
        unchanged = 0

        for event_data in events:
            existing = self.db.query(CalendarEvent).filter(
                CalendarEvent.external_event_id == event_data['external_event_id']
            ).first()

            if existing:
                # Update if changed
                if (existing.title != event_data['title'] or
                    existing.start_time != event_data['start_time'] or
                    existing.participants != event_data['attendees']):

                    existing.title = event_data['title']
                    existing.description = event_data['description']
                    existing.start_time = event_data['start_time']
                    existing.end_time = event_data['end_time']
                    existing.location = event_data['location']
                    existing.organizer = event_data['organizer']
                    existing.participants = event_data['attendees']
                    existing.timezone = event_data['timezone']
                    existing.last_synced_at = now
                    updated += 1
                else:
                    existing.last_synced_at = now
                    unchanged += 1
            else:
                # Create new
                new_event = CalendarEvent(
                    external_event_id=event_data['external_event_id'],
                    calendar_id=event_data['calendar_id'],
                    title=event_data['title'],
                    description=event_data['description'],
                    start_time=event_data['start_time'],
                    end_time=event_data['end_time'],
                    location=event_data['location'],
                    organizer=event_data['organizer'],
                    participants=event_data['attendees'],
                    timezone=event_data['timezone'],
                    source='synced',
                    status='upcoming',
                    last_synced_at=now
                )
                self.db.add(new_event)
                self.db.flush()  # Get the ID

                # Schedule briefing generation
                briefing_time = event_data['start_time'] - timedelta(hours=briefing_hours_before)
                if briefing_time > now:
                    enqueue_task(
                        task_type="generate_briefing",
                        payload={"event_id": new_event.id},
                        scheduled_for=briefing_time,
                        db=self.db
                    )
                    logger.info(f"Scheduled briefing for event {new_event.id} at {briefing_time}")

                created += 1

        self.db.commit()

        logger.info(f"Calendar sync complete: {created} created, {updated} updated, {unchanged} unchanged")
        return {'created': created, 'updated': updated, 'unchanged': unchanged}
