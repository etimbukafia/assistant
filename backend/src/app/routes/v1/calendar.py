from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_db_for_user, get_user_settings, require_active_subscription, AuthenticatedUser
from app.security.feature_gating import require_feature, Feature
from app.data.models import CalendarEvent, UserSettings
from app.data.schemas import (
    CalendarEventCreateRequest, CalendarEventResponse, 
    CalendarSettingsResponse, CalendarSettingsUpdateRequest,
    CalendarAvailabilityResponse, CalendarInfoResponse
)
from app.services.calendar import CalendarService
from app.services.briefing import generate_briefing_for_event, generate_follow_ups_for_event
from app.agents.modules.scheduling import SchedulingModule

router = APIRouter(prefix="/calendar", tags=["Calendar"])

@router.post("/events", response_model=CalendarEventResponse)
def create_calendar_event(
    request: CalendarEventCreateRequest,
    db: Session = Depends(get_db_for_user)
):
    """Create a calendar event from a scheduling suggestion"""

    scheduling_module = SchedulingModule()

    result = scheduling_module.create_calendar_event(
        suggestion_id=request.suggestion_id,
        selected_slot_index=request.selected_slot_index,
        title=request.title,
        description=request.description,
        location=request.location,
        db=db
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create event"))

    # Get the created event from database
    event = db.query(CalendarEvent).filter(CalendarEvent.id == result["event_id"]).first()

    return event


@router.get("/events")
def get_calendar_events(
    status: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_for_user)
):
    """Get calendar events"""

    query = db.query(CalendarEvent)

    if status:
        query = query.filter(CalendarEvent.status == status)

    total = query.count()
    events = query.order_by(CalendarEvent.start_time.desc()).offset(skip).limit(limit).all()

    return {
        "events": [CalendarEventResponse.model_validate(e) for e in events],
        "total": total
    }


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_calendar_event(
    event_id: int,
    db: Session = Depends(get_db_for_user)
):
    """Get a single calendar event by ID"""
    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


@router.post("/sync")
async def sync_calendar_events(
    days_ahead: int = 7,
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user)
):
    """Sync upcoming events from Google Calendar to database"""
 
    calendar_service = CalendarService(db)
 
    try:
        results = await calendar_service.sync_upcoming_events(days_ahead=days_ahead)
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
    db: Session = Depends(get_db_for_user)
):
    """Check calendar availability for a time range"""

    try:
        start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    calendar_id_list = calendar_ids.split(',') if calendar_ids else None

    calendar_service = CalendarService(db)

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
async def get_user_calendars(db: Session = Depends(get_db_for_user)):
    """Get list of user's Google calendars"""

    calendar_service = CalendarService(db)

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
        calendar_ids=settings.calendar_ids or []
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
        calendar_ids=settings.calendar_ids or []
    )


@router.post("/events/{event_id}/generate-followups")
def generate_meeting_followups(
    event_id: int,
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

    return result
