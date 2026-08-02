from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.automation.base import BaseAutomationService
from app.automation.catalog import AutomationId
from app.data.models import CalendarEvent
from app.superpowers.meeting_brief import MeetingBriefService


AUTOMATION_ID: AutomationId = "meeting-prep"


class MeetingPrepService(BaseAutomationService):
    """Product automation wrapper for meeting briefing."""

    def get_summary(self) -> Dict[str, Any]:
        setting = self._get_or_create_setting(AUTOMATION_ID)
        definition = self._definition(AUTOMATION_ID)
        status = self._status_for(AUTOMATION_ID, setting)
        next_event = self._next_event()
        return {
            "id": AUTOMATION_ID,
            "name": definition["name"],
            "outcome": definition["outcome"],
            "description": definition["description"],
            "status": status,
            "safety_mode": setting.safety_mode,
            "execution_mode": setting.execution_mode,
            "connectors": self._build_connector_payload(AUTOMATION_ID),
            "degraded_behavior": definition["degraded_behavior"],
            "enabled": bool(setting.enabled),
            "next_event": self._serialize_event(next_event) if next_event else None,
            "recent_runs": [self._serialize_run(run) for run in self._recent_runs(AUTOMATION_ID)],
        }

    def update(self, *, enabled: Optional[bool] = None) -> Dict[str, Any]:
        setting = self._get_or_create_setting(AUTOMATION_ID)
        if enabled is not None:
            setting.configured = True
            setting.enabled = bool(enabled)
        self.db.add(setting)
        self.db.commit()
        return self.get_summary()

    def run(
        self,
        *,
        event_id: Optional[str] = None,
        include_recent_context: bool = True,
        trigger: str = "manual",
    ) -> Dict[str, Any]:
        event = self._resolve_event(event_id)
        brief_service = MeetingBriefService(db=self.db, user_id=self.user_id)
        brief = brief_service.build_brief(
            event_id=str(event.id) if event else event_id,
            include_recent_context=include_recent_context,
        )
        summary = brief.get("summary") or "Meeting Prep generated a brief."
        run = self._record_run(
            automation_id=AUTOMATION_ID,
            status="completed",
            trigger=trigger,
            summary=summary,
            run_metadata={
                "event_id": brief.get("event_id"),
                "meeting_subject": brief.get("meeting_subject"),
                "participant_count": len(brief.get("participants") or []),
            },
        )
        self.db.commit()
        return {
            "run": self._serialize_run(run),
            "brief": brief,
        }

    def _next_event(self) -> Optional[CalendarEvent]:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(CalendarEvent)
            .filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.start_time >= now,
                CalendarEvent.status.in_(("upcoming", "created")),
            )
            .order_by(CalendarEvent.start_time.asc())
            .first()
        )

    def _resolve_event(self, event_id: Optional[str]) -> Optional[CalendarEvent]:
        if event_id and str(event_id).isdigit():
            return (
                self.db.query(CalendarEvent)
                .filter(CalendarEvent.user_id == self.user_id, CalendarEvent.id == int(event_id))
                .first()
            )
        return self._next_event()

    def _serialize_event(self, event: CalendarEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "location": event.location,
            "participant_count": len(event.participants or []),
        }

    def _serialize_run(self, run) -> Dict[str, Any]:
        return {
            "id": run.id,
            "status": run.status,
            "trigger": run.trigger,
            "summary": run.summary,
            "run_metadata": run.run_metadata or {},
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }
