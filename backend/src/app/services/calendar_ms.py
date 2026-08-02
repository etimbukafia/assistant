"""
Microsoft Calendar Service - Microsoft Graph API Integration
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

import httpx
from sqlalchemy.orm import Session

from app.integrations.outlook import OutlookClient

logger = logging.getLogger(__name__)


class MicrosoftCalendarService:
    def __init__(self, db: Session, user_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.client = OutlookClient(db=db, user_id=user_id)
        if not self.client.load_credentials():
            raise Exception("Calendar not authenticated. Please connect your Microsoft account.")

    async def get_calendars(self) -> List[Dict[str, Any]]:
        resp = httpx.get(
            "https://graph.microsoft.com/v1.0/me/calendars",
            headers=self.client._graph_headers(),
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    async def get_availability(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        schedule_ids = calendar_ids or ["me"]
        payload = {
            "schedules": schedule_ids,
            "startTime": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
            "endTime": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
            "availabilityViewInterval": 30,
        }
        resp = httpx.post(
            "https://graph.microsoft.com/v1.0/me/calendar/getSchedule",
            headers=self.client._graph_headers(),
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    async def sync_upcoming_events(
        self,
        calendar_ids: Optional[List[str]] = None,
        days_ahead: int = 7,
        briefing_hours_before: int = 2,
        enable_briefings: bool = True,
    ) -> Dict[str, int]:
        from app.data.models import CalendarEvent
        from app.jobs.queue import enqueue_task

        start = datetime.now(timezone.utc)
        end = start + timedelta(days=days_ahead)
        params = {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime",
        }
        resp = httpx.get(
            "https://graph.microsoft.com/v1.0/me/calendarView",
            headers=self.client._graph_headers(),
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        events = resp.json().get("value", [])

        created = 0
        updated = 0
        unchanged = 0
        now = datetime.now(timezone.utc)

        def _schedule_briefing(event: CalendarEvent, start_time: datetime) -> Optional[datetime]:
            if not enable_briefings:
                return None
            if event.label != "meeting":
                return None
            briefing_time = start_time - timedelta(hours=briefing_hours_before)
            if briefing_time <= now:
                return None
            enqueue_task(
                task_type="generate_briefing",
                payload={"event_id": event.id},
                scheduled_for=briefing_time,
                db=self.db
            )
            return briefing_time

        for raw in events:
            normalized = self._normalize_event(raw)
            existing = self.db.query(CalendarEvent).filter(
                CalendarEvent.external_event_id == normalized["external_event_id"]
            ).first()

            if existing:
                if (existing.title != normalized["title"] or
                    existing.start_time != normalized["start_time"] or
                    existing.participants != normalized["attendees"]):
                    existing.title = normalized["title"]
                    existing.description = normalized["description"]
                    existing.start_time = normalized["start_time"]
                    existing.end_time = normalized["end_time"]
                    existing.location = normalized["location"]
                    existing.organizer = normalized["organizer"]
                    existing.participants = normalized["attendees"]
                    existing.timezone = normalized["timezone"]
                    existing.all_day = normalized.get("all_day", False)
                    if not existing.label:
                        existing.label = self._classify_event_label(
                            normalized["title"], normalized["description"], normalized["attendees"]
                        )
                    briefing_time = _schedule_briefing(existing, normalized["start_time"])
                    existing.briefing_scheduled_for = briefing_time
                    existing.last_synced_at = now
                    updated += 1
                else:
                    existing.last_synced_at = now
                    unchanged += 1
            else:
                label = self._classify_event_label(
                    normalized["title"], normalized["description"], normalized["attendees"]
                )
                new_event = CalendarEvent(
                    external_event_id=normalized["external_event_id"],
                    calendar_id=normalized["calendar_id"],
                    title=normalized["title"],
                    description=normalized["description"],
                    start_time=normalized["start_time"],
                    end_time=normalized["end_time"],
                    location=normalized["location"],
                    organizer=normalized["organizer"],
                    participants=normalized["attendees"],
                    timezone=normalized["timezone"],
                    all_day=normalized.get("all_day", False),
                    label=label,
                    source="synced",
                    status="upcoming",
                    provider="microsoft",
                    last_synced_at=now,
                )
                self.db.add(new_event)
                self.db.flush()
                briefing_time = _schedule_briefing(new_event, normalized["start_time"])
                new_event.briefing_scheduled_for = briefing_time
                created += 1

        self.db.commit()
        return {"created": created, "updated": updated, "unchanged": unchanged}

    def _normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        start = event.get("start", {})
        end = event.get("end", {})
        start_dt_str = start.get("dateTime")
        end_dt_str = end.get("dateTime")
        if not start_dt_str or not end_dt_str:
            raise ValueError("Event missing start/end dateTime")
        start_time = datetime.fromisoformat(start_dt_str.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end_dt_str.replace("Z", "+00:00"))
        attendees = [
            {
                "email": att.get("emailAddress", {}).get("address"),
                "name": att.get("emailAddress", {}).get("name"),
                "response_status": att.get("status", {}).get("response"),
            }
            for att in event.get("attendees", [])
        ]
        return {
            "external_event_id": event.get("id"),
            "calendar_id": event.get("calendar", {}).get("id") or "primary",
            "title": event.get("subject", "No Title"),
            "description": (event.get("body") or {}).get("content"),
            "start_time": start_time,
            "end_time": end_time,
            "timezone": start.get("timeZone", "UTC"),
            "location": (event.get("location") or {}).get("displayName"),
            "organizer": (event.get("organizer") or {}).get("emailAddress", {}).get("address"),
            "attendees": attendees,
            "all_day": False,
        }

    @staticmethod
    def _classify_event_label(title: str, description: Optional[str], participants: List[Any]) -> str:
        MEETING_KW = {
            "meeting", "call", "sync", "interview", "standup", "stand-up", "stand up",
            "1:1", "one-on-one", "one on one", "review", "discussion", "conference",
            "workshop", "webinar", "zoom", "teams", "meet", "huddle", "session",
            "check-in", "check in", "catchup", "catch-up",
        }
        PERSONAL_KW = {
            "lunch", "dinner", "breakfast", "birthday", "anniversary",
            "holiday", "vacation", "pto", "day off", "off", "personal",
        }
        TRAVEL_KW = {
            "flight", "travel", "transit", "drive", "commute", "trip",
            "hotel", "depart", "arrive", "train", "ferry",
        }
        DEADLINE_KW = {
            "deadline", "due", "submit", "submission", "delivery",
            "launch", "release", "ship", "go live",
        }

        text = f"{title} {description or ''}".lower()
        for phrase in MEETING_KW | PERSONAL_KW | TRAVEL_KW | DEADLINE_KW:
            if " " in phrase and phrase in text:
                if phrase in MEETING_KW:
                    return "meeting"
                if phrase in PERSONAL_KW:
                    return "personal"
                if phrase in TRAVEL_KW:
                    return "travel"
                if phrase in DEADLINE_KW:
                    return "deadline"

        words = set(re.findall(r"\w+", text))
        if words & {kw for kw in MEETING_KW if " " not in kw}:
            return "meeting"
        if words & {kw for kw in PERSONAL_KW if " " not in kw}:
            return "personal"
        if words & {kw for kw in TRAVEL_KW if " " not in kw}:
            return "travel"
        if words & {kw for kw in DEADLINE_KW if " " not in kw}:
            return "deadline"
        if len(participants) > 1:
            return "meeting"
        return "other"

    def run_create_event(self, payload: Dict[str, Any], calendar_id: Optional[str] = None) -> Dict[str, Any]:
        url = "https://graph.microsoft.com/v1.0/me/events"
        if calendar_id:
            url = f"https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events"
        resp = httpx.post(url, headers=self.client._graph_headers(), json=payload, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return {"external_event_id": data.get("id")}

    def run_update_event(self, event_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://graph.microsoft.com/v1.0/me/events/{event_id}"
        resp = httpx.patch(url, headers=self.client._graph_headers(), json=payload, timeout=10.0)
        resp.raise_for_status()
        return {"external_event_id": event_id}

    def run_delete_event(self, event_id: str) -> Dict[str, Any]:
        url = f"https://graph.microsoft.com/v1.0/me/events/{event_id}"
        resp = httpx.delete(url, headers=self.client._graph_headers(), timeout=10.0)
        resp.raise_for_status()
        return {"external_event_id": event_id}
