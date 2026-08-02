from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_db_for_user, get_user_settings, get_current_user, require_active_subscription, AuthenticatedUser
from app.data.models import CalendarEvent, UserSettings
from core.cache import calendar_cache
from app.data.schemas import (
    CalendarEventCreateRequest, CalendarEventManualCreateRequest, CalendarEventUpdateRequest, CalendarEventResponse, 
    CalendarSettingsResponse, CalendarSettingsUpdateRequest,
    CalendarAvailabilityResponse, CalendarInfoResponse
)
from app.services.calendar import CalendarService
from app.services.calendar_ms import MicrosoftCalendarService
from app.services.briefing import generate_briefing_for_event, generate_follow_ups_for_event
from app.agents.modules.scheduling import SchedulingModule
from app.services.entity_cache_coordinator import EntityCacheCoordinator

router = APIRouter(prefix="/calendar", tags=["Calendar"])
cache_coordinator = EntityCacheCoordinator()


def _tenant_id() -> str:
    return "default"


def _prewarm_action_chips(db: Session, user_id: str) -> None:
    cache_coordinator.prewarm_action_chips(
        db=db,
        tenant_id=_tenant_id(),
        user_id=user_id,
    )


def _invalidate_event_related(db: Session, user_id: str, event: CalendarEvent | None) -> None:
    if not event:
        return
    cache_coordinator.invalidate_event_related_contacts(
        db=db,
        tenant_id=_tenant_id(),
        user_id=user_id,
        event_id=event.id,
        participants=event.participants if isinstance(event.participants, list) else [],
        organizer=event.organizer,
    )


def _resolve_event_label(
    explicit_label: str | None,
    title: str,
    description: str | None,
    participants: list[str] | None,
) -> str:
    """Use explicit label when provided; otherwise classify from content."""
    if explicit_label:
        return explicit_label
    return CalendarService._classify_event_label(
        title=title,
        description=description,
        participants=participants or [],
    )


def _get_calendar_service(settings: UserSettings, db: Session, user_id: str):
    """Return provider-specific calendar service + provider name."""
    if settings.connected_provider == "microsoft":
        return MicrosoftCalendarService(db=db, user_id=user_id), "microsoft"
    return CalendarService(db=db, user_id=user_id), "google"

@router.post("/events", response_model=CalendarEventResponse)
def create_calendar_event(
    request: CalendarEventCreateRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Create a calendar event from a scheduling suggestion"""

    scheduling_module = SchedulingModule()

    result = scheduling_module.create_calendar_event(
        suggestion_id=request.suggestion_id,
        selected_slot_index=request.selected_slot_index,
        title=request.title,
        description=request.description,
        location=request.location,
        calendar_id=settings.default_calendar_id,
        db=db,
        user_id=user.user_id
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create event"))

    # Get the created event from database
    event = db.query(CalendarEvent).filter(CalendarEvent.id == result["event_id"]).first()

    calendar_cache.invalidate_all(user.user_id)
    if event:
        _invalidate_event_related(db, user.user_id, event)
    _prewarm_action_chips(db, user.user_id)

    return event


@router.post("/events/manual", response_model=CalendarEventResponse)
def create_manual_calendar_event(
    request: CalendarEventManualCreateRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Create a calendar event directly (not from a suggestion)"""
    calendar_id = request.calendar_id or settings.default_calendar_id or "primary"
    timezone_str = request.timezone or settings.default_timezone or "UTC"

    start_time = request.start_time
    end_time = request.end_time
    all_day = bool(request.all_day)
    if all_day and end_time <= start_time:
        end_time = start_time + timedelta(days=1)

    calendar_service, provider = _get_calendar_service(settings, db, user.user_id)
    event_label = _resolve_event_label(
        explicit_label=request.label,
        title=request.title,
        description=request.description,
        participants=request.participants or [],
    )
    calendar_event = CalendarEvent(
        user_id=user.user_id,
        title=request.title,
        description=request.description,
        notes=request.notes,
        start_time=start_time,
        end_time=end_time,
        participants=request.participants or [],
        timezone=timezone_str,
        location=request.location,
        source="created",
        status="pending",
        provider=provider,
        calendar_id=calendar_id,
        all_day=all_day,
        label=event_label,
    )
    db.add(calendar_event)
    db.commit()
    db.refresh(calendar_event)

    try:
        if provider == "google":
            result = calendar_service.run_create_event(
                title=request.title,
                start_time=start_time,
                end_time=end_time,
                description=request.description,
                attendees=request.participants or [],
                location=request.location,
                timezone_str=timezone_str,
                calendar_id=calendar_id,
                all_day=all_day,
            )
        else:
            payload = {
                "subject": request.title,
                "body": {"contentType": "HTML", "content": request.description or ""},
                "start": {"dateTime": start_time.isoformat(), "timeZone": timezone_str},
                "end": {"dateTime": end_time.isoformat(), "timeZone": timezone_str},
                "location": {"displayName": request.location or ""},
                "attendees": [{"emailAddress": {"address": a}} for a in (request.participants or [])],
            }
            result = calendar_service.run_create_event(payload=payload, calendar_id=calendar_id)
    except Exception as e:
        calendar_event.status = "failed"
        calendar_event.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")

    calendar_event.external_event_id = result.get("external_event_id")
    calendar_event.status = "created"
    db.commit()

    # Schedule briefing only for meeting-labelled events
    if settings.auto_briefing_enabled and calendar_event.label == "meeting":
        briefing_time = start_time - timedelta(hours=settings.briefing_hours_before or 1)
        if briefing_time > datetime.now(timezone.utc):
            from app.jobs.queue import enqueue_task
            enqueue_task(
                task_type="generate_briefing",
                payload={"event_id": calendar_event.id},
                scheduled_for=briefing_time,
                db=db
            )
            calendar_event.briefing_scheduled_for = briefing_time
            db.commit()

    calendar_cache.invalidate_all(user.user_id)
    _invalidate_event_related(db, user.user_id, calendar_event)
    _prewarm_action_chips(db, user.user_id)

    return calendar_event


@router.get("/events")
def get_calendar_events(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    start_time: str = None,
    end_time: str = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Get calendar events. Cached per user for 60s."""

    cache_key = f"events:{status}:{limit}:{offset}:{start_time}:{end_time}"

    def build():
        query = db.query(CalendarEvent)

        if status:
            query = query.filter(CalendarEvent.status == status)
        else:
            query = query.filter(CalendarEvent.status != "cancelled")
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                query = query.filter(CalendarEvent.end_time >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_time format")
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                query = query.filter(CalendarEvent.start_time <= end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_time format")

        total = query.count()
        events = query.order_by(CalendarEvent.start_time.desc()).offset(offset).limit(limit).all()

        return {
            "events": [CalendarEventResponse.model_validate(e).model_dump() for e in events],
            "total": total
        }

    return calendar_cache.get_or_build_events(user.user_id, cache_key, build)


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_calendar_event(
    event_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Get a single calendar event by ID. Cached per user for 60s."""

    def build():
        event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return CalendarEventResponse.model_validate(event).model_dump()

    return calendar_cache.get_or_build_event(user.user_id, event_id, build)


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
def update_calendar_event(
    event_id: int,
    request: CalendarEventUpdateRequest,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Update a calendar event and sync to Google if possible"""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = request.model_dump(exclude_unset=True)
    all_day = update_data.get("all_day", event.all_day)
    start_time = update_data.get("start_time", event.start_time)
    end_time = update_data.get("end_time", event.end_time)
    if all_day and end_time <= start_time:
        end_time = start_time + timedelta(days=1)

    for key, value in update_data.items():
        setattr(event, key, value)

    event.start_time = start_time
    event.end_time = end_time
    event.all_day = all_day
    if not event.label:
        event.label = _resolve_event_label(
            explicit_label=update_data.get("label"),
            title=event.title,
            description=event.description,
            participants=event.participants if isinstance(event.participants, list) else [],
        )

    calendar_id = update_data.get("calendar_id") or event.calendar_id or settings.default_calendar_id or "primary"

    calendar_service, provider = _get_calendar_service(settings, db, user.user_id)
    if event.external_event_id:
        if provider == "google":
            result = calendar_service.run_update_event(
                event_id=event.external_event_id,
                calendar_id=calendar_id,
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                description=event.description,
                attendees=event.participants,
                location=event.location,
                timezone_str=event.timezone,
                all_day=event.all_day,
            )
            if not result.get("success"):
                raise HTTPException(status_code=500, detail=result.get("error", "Failed to update event"))
        else:
            payload = {
                "subject": event.title,
                "body": {"contentType": "HTML", "content": event.description or ""},
                "start": {"dateTime": event.start_time.isoformat(), "timeZone": event.timezone or "UTC"},
                "end": {"dateTime": event.end_time.isoformat(), "timeZone": event.timezone or "UTC"},
                "location": {"displayName": event.location or ""},
                "attendees": [{"emailAddress": {"address": a}} for a in (event.participants or [])],
            }
            calendar_service.run_update_event(event_id=event.external_event_id, payload=payload)

    # Reschedule briefing only for meeting-labelled events
    if settings.auto_briefing_enabled and event.label == "meeting":
        briefing_time = event.start_time - timedelta(hours=settings.briefing_hours_before or 1)
        if briefing_time > datetime.now(timezone.utc):
            from app.jobs.queue import enqueue_task
            enqueue_task(
                task_type="generate_briefing",
                payload={"event_id": event.id},
                scheduled_for=briefing_time,
                db=db
            )
            event.briefing_scheduled_for = briefing_time
    else:
        event.briefing_scheduled_for = None

    db.commit()

    calendar_cache.invalidate_all(user.user_id)
    _invalidate_event_related(db, user.user_id, event)
    _prewarm_action_chips(db, user.user_id)

    db.refresh(event)
    return event


@router.delete("/events/{event_id}")
def delete_calendar_event(
    event_id: int,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    """Delete/cancel a calendar event and sync to Google"""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.external_event_id:
        settings = db.query(UserSettings).filter(UserSettings.user_id == user.user_id).first()
        calendar_service, provider = _get_calendar_service(settings, db, user.user_id)
        if provider == "google":
            result = calendar_service.run_delete_event(
                event_id=event.external_event_id,
                calendar_id=event.calendar_id or "primary"
            )
            if not result.get("success"):
                raise HTTPException(status_code=500, detail=result.get("error", "Failed to delete event"))
        else:
            calendar_service.run_delete_event(event_id=event.external_event_id)

    event.status = "cancelled"
    db.commit()

    calendar_cache.invalidate_all(user.user_id)
    _invalidate_event_related(db, user.user_id, event)
    _prewarm_action_chips(db, user.user_id)

    return {"success": True}


@router.post("/sync")
async def sync_calendar_events(
    days_ahead: int = 7,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Sync upcoming events from connected calendar provider to database."""

    calendar_service, provider = _get_calendar_service(settings, db, user.user_id)
 
    try:
        enable_briefings = settings.auto_briefing_enabled

        # Use the user's explicitly chosen calendars, or fall back to default calendar only
        user_calendar_ids = settings.calendar_ids or []
        calendar_ids = user_calendar_ids if user_calendar_ids else [settings.default_calendar_id or "primary"]

        if provider == "google":
            results = await calendar_service.sync_upcoming_events(
                days_ahead=days_ahead,
                briefing_hours_before=settings.briefing_hours_before or 1,
                enable_briefings=enable_briefings,
                calendar_ids=calendar_ids,
            )
        else:
            results = await calendar_service.sync_upcoming_events(
                days_ahead=days_ahead,
                calendar_ids=calendar_ids,
                briefing_hours_before=settings.briefing_hours_before or 1,
                enable_briefings=enable_briefings,
            )

        calendar_cache.invalidate_all(user.user_id)
        cache_coordinator.invalidate_user_scopes(_tenant_id(), user.user_id)
        _prewarm_action_chips(db, user.user_id)

        return {
            "success": True,
            "message": f"Calendar sync complete: {results['created']} created, {results['updated']} updated",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
 
 
@router.get("/availability")
async def check_calendar_availability(
    start_time: str,
    end_time: str,
    calendar_ids: str = None,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Check calendar availability for a time range"""

    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    calendar_id_list = calendar_ids.split(',') if calendar_ids else None

    calendar_service, provider = _get_calendar_service(settings, db, user.user_id)

    try:
        if provider == "google":
            busy_slots = await calendar_service.get_availability(start, end, calendar_id_list)
            busy_payload = [{
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "calendar_id": slot.calendar_id
            } for slot in busy_slots]
        else:
            schedules = await calendar_service.get_availability(start, end, calendar_id_list)
            busy_payload = []
            for sched in schedules:
                for item in sched.get("scheduleItems", []):
                    busy_payload.append({
                        "start": item.get("start", {}).get("dateTime"),
                        "end": item.get("end", {}).get("dateTime"),
                        "calendar_id": sched.get("scheduleId"),
                    })

        user_timezone = settings.default_timezone if settings else "UTC"

        return CalendarAvailabilityResponse(
            busy_slots=busy_payload,
            timezone=user_timezone
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check availability: {str(e)}")


@router.get("/calendars")
async def get_user_calendars(
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Get list of user's Google calendars"""

    calendar_service, provider = _get_calendar_service(settings, db, user.user_id)

    try:
        calendars = await calendar_service.get_calendars()

        if provider == "google":
            return {
                "calendars": [CalendarInfoResponse(
                    id=cal.id,
                    summary=cal.summary,
                    primary=cal.primary,
                    access_role=cal.access_role
                ) for cal in calendars]
            }
        return {
            "calendars": [CalendarInfoResponse(
                id=cal.get("id"),
                summary=cal.get("name") or cal.get("summary") or "Calendar",
                primary=cal.get("isDefaultCalendar", False),
                access_role=cal.get("canEdit", False) and "writer" or "reader"
            ) for cal in calendars]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get calendars: {str(e)}")


@router.get("/settings", response_model=CalendarSettingsResponse)
def get_calendar_settings(settings: UserSettings = Depends(get_user_settings)):
    """Get calendar-related user settings"""
    # Settings retrieved via dependency which handles creation if needed

    return CalendarSettingsResponse(
        default_meeting_duration=settings.default_meeting_duration,
        preferred_meeting_times=settings.preferred_meeting_times,
        buffer_minutes=settings.buffer_minutes,
        working_hours_start=settings.working_hours_start,
        working_hours_end=settings.working_hours_end,
        default_timezone=settings.default_timezone,
        calendar_ids=settings.calendar_ids or [],
        default_calendar_id=settings.default_calendar_id,
        auto_briefing_enabled=settings.auto_briefing_enabled,
        briefing_hours_before=settings.briefing_hours_before,
    )


@router.patch("/settings", response_model=CalendarSettingsResponse)
def update_calendar_settings(
    request: CalendarSettingsUpdateRequest,
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user)
):
    """Update calendar-related settings"""
    # Settings retrieved via dependency

    update_data = request.model_dump(exclude_unset=True)

    # Capture which calendars were previously tracked before applying the update
    old_calendar_ids = set(settings.calendar_ids or [])

    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)

    # When the user changes which calendars to sync, clean up removed calendars
    if "calendar_ids" in update_data:
        new_calendar_ids = set(settings.calendar_ids or [])
        removed = old_calendar_ids - new_calendar_ids

        # Delete events from calendars the user has deselected
        if removed:
            db.query(CalendarEvent).filter(
                CalendarEvent.user_id == settings.user_id,
                CalendarEvent.calendar_id.in_(list(removed))
            ).delete(synchronize_session=False)
            db.commit()
            calendar_cache.invalidate_all(settings.user_id)

        # Re-setup push watches to match the new selection
        try:
            from app.services.calendar_watch import setup_watches_for_user
            setup_watches_for_user(db=db, user_id=settings.user_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Calendar watch re-setup failed: {e}")

    return CalendarSettingsResponse(
        default_meeting_duration=settings.default_meeting_duration,
        preferred_meeting_times=settings.preferred_meeting_times,
        buffer_minutes=settings.buffer_minutes,
        working_hours_start=settings.working_hours_start,
        working_hours_end=settings.working_hours_end,
        default_timezone=settings.default_timezone,
        calendar_ids=settings.calendar_ids or [],
        default_calendar_id=settings.default_calendar_id,
        auto_briefing_enabled=settings.auto_briefing_enabled,
        briefing_hours_before=settings.briefing_hours_before,
    )


@router.post("/events/{event_id}/generate-briefing")
def generate_meeting_briefing(
    event_id: int,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    """Generate a briefing for a calendar event"""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = generate_briefing_for_event(db, event_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate briefing")

    _invalidate_event_related(db, user.user_id, event)
    _prewarm_action_chips(db, user.user_id)

    db.refresh(event)
    return {
        "success": True,
        "briefing": result,
        "briefing_generated_at": event.briefing_generated_at
    }


@router.post("/events/{event_id}/generate-followups")
def generate_meeting_followups(
    event_id: int,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
):
    """
    Generate follow-up items for a completed meeting.

    Returns AI-generated suggestions for:
    - Follow-up tasks
    - Email drafts to attendees
    - Reminders for future actions

    All items are returned as pending_approval - user must approve each one.
    """

    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = generate_follow_ups_for_event(db, event_id)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate follow-ups")

    _invalidate_event_related(db, user.user_id, event)
    _prewarm_action_chips(db, user.user_id)

    return result
