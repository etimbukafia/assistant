from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_db_for_user, get_user_settings, get_current_user, require_active_subscription, AuthenticatedUser
from app.security.feature_gating import require_feature, Feature, is_feature_enabled
from app.data.models import CalendarEvent, UserSettings
from core.cache import calendar_cache
from app.data.schemas import (
    CalendarEventCreateRequest, CalendarEventManualCreateRequest, CalendarEventUpdateRequest, CalendarEventResponse, 
    CalendarSettingsResponse, CalendarSettingsUpdateRequest,
    CalendarAvailabilityResponse, CalendarInfoResponse
)
from app.services.calendar import CalendarService
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
        cache_coordinator.invalidate_event(_tenant_id(), user.user_id, str(event.id))
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
        provider="google",
        calendar_id=calendar_id,
        all_day=all_day,
    )
    db.add(calendar_event)
    db.commit()
    db.refresh(calendar_event)

    calendar_service = CalendarService(db, user_id=user.user_id)
    try:
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
    except Exception as e:
        calendar_event.status = "failed"
        calendar_event.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")

    calendar_event.external_event_id = result.get("external_event_id")
    calendar_event.status = "created"
    db.commit()

    # Schedule briefing if enabled
    if settings.auto_briefing_enabled:
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
    cache_coordinator.invalidate_event(_tenant_id(), user.user_id, str(calendar_event.id))
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

    calendar_id = update_data.get("calendar_id") or event.calendar_id or settings.default_calendar_id or "primary"

    calendar_service = CalendarService(db, user_id=user.user_id)
    if event.external_event_id:
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

    # Reschedule briefing if enabled and time changed
    if settings.auto_briefing_enabled:
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
    cache_coordinator.invalidate_event(_tenant_id(), user.user_id, str(event.id))
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
        calendar_service = CalendarService(db, user_id=user.user_id)
        result = calendar_service.run_delete_event(
            event_id=event.external_event_id,
            calendar_id=event.calendar_id or "primary"
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to delete event"))

    event.status = "cancelled"
    db.commit()

    calendar_cache.invalidate_all(user.user_id)
    cache_coordinator.invalidate_event(_tenant_id(), user.user_id, str(event.id))
    _prewarm_action_chips(db, user.user_id)

    return {"success": True}


@router.post("/sync")
async def sync_calendar_events(
    days_ahead: int = 7,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user),
    settings: UserSettings = Depends(get_user_settings),
):
    """Sync upcoming events from Google Calendar to database"""

    calendar_service = CalendarService(db, user_id=user.user_id)
 
    try:
        enable_briefings = settings.auto_briefing_enabled and is_feature_enabled(Feature.MEETING_BRIEFINGS, settings)
        calendar_ids = [settings.default_calendar_id] if settings.default_calendar_id else None
        results = await calendar_service.sync_upcoming_events(
            days_ahead=days_ahead,
            briefing_hours_before=settings.briefing_hours_before or 1,
            enable_briefings=enable_briefings,
            calendar_ids=calendar_ids
        )

        calendar_cache.invalidate_all(user.user_id)
        cache_coordinator.invalidate_action_chips(_tenant_id(), user.user_id)
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
    db: Session = Depends(get_db_for_user)
):
    """Check calendar availability for a time range"""

    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    calendar_id_list = calendar_ids.split(',') if calendar_ids else None

    calendar_service = CalendarService(db, user_id=user.user_id)

    try:
        busy_slots = await calendar_service.get_availability(start, end, calendar_id_list)

        # Get user timezone
        settings = db.query(UserSettings).first()
        user_timezone = settings.default_timezone if settings else "UTC"

        return CalendarAvailabilityResponse(
            busy_slots=[{
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "calendar_id": slot.calendar_id
            } for slot in busy_slots],
            timezone=user_timezone
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check availability: {str(e)}")


@router.get("/calendars")
async def get_user_calendars(
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user)
):
    """Get list of user's Google calendars"""

    calendar_service = CalendarService(db, user_id=user.user_id)

    try:
        calendars = await calendar_service.get_calendars()

        return {
            "calendars": [CalendarInfoResponse(
                id=cal.id,
                summary=cal.summary,
                primary=cal.primary,
                access_role=cal.access_role
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

    # Update only fields that were set in the request
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)

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
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
    _gate=Depends(require_feature(Feature.MEETING_BRIEFINGS)),
):
    """Generate a briefing for a calendar event"""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = generate_briefing_for_event(db, event_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate briefing")

    calendar_cache.invalidate_event(user.user_id, event_id)
    cache_coordinator.invalidate_event(_tenant_id(), user.user_id, str(event_id))
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
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
    _gate=Depends(require_feature(Feature.CALENDAR_SYNC)),
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

    calendar_cache.invalidate_event(user.user_id, event_id)
    cache_coordinator.invalidate_event(_tenant_id(), user.user_id, str(event_id))
    _prewarm_action_chips(db, user.user_id)

    return result
