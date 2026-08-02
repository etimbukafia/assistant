from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.automation.catalog import AUTOMATION_DEFINITIONS
from app.automation.inbox_copilot import InboxCopilotService
from app.automation.meeting_prep import MeetingPrepService
from app.data.models import UserSettings
from app.data.schemas import (
    AutomationListResponse,
    AutomationResponse,
    AutomationRunEnvelope,
    AutomationUpdateRequest,
    InboxCopilotRunRequest,
    MeetingPrepRunRequest,
)
from app.security.auth import get_db_for_user, get_user_settings, require_active_subscription, AuthenticatedUser


router = APIRouter(prefix="/automations", tags=["Automations"])


def _serialize(summary: dict) -> AutomationResponse:
    return AutomationResponse(
        id=summary["id"],
        name=summary["name"],
        outcome=summary["outcome"],
        description=summary["description"],
        status=summary["status"],
        safety_mode=summary["safety_mode"],
        execution_mode=summary["execution_mode"],
        enabled=summary["enabled"],
        required_connectors=summary["connectors"]["required"],
        optional_connectors=summary["connectors"]["optional"],
        degraded_behavior=summary.get("degraded_behavior"),
        recent_runs=summary.get("recent_runs") or [],
        workload=summary.get("workload"),
        next_event=summary.get("next_event"),
    )


@router.get("", response_model=AutomationListResponse)
def list_automations(
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    inbox = InboxCopilotService(db=db, user_id=settings.user_id, settings=settings)
    meeting = MeetingPrepService(db=db, user_id=settings.user_id, settings=settings)
    return AutomationListResponse(
        automations=[
            _serialize(inbox.get_summary()),
            _serialize(meeting.get_summary()),
        ]
    )


@router.get("/inbox-copilot", response_model=AutomationResponse)
def get_inbox_copilot(
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    service = InboxCopilotService(db=db, user_id=settings.user_id, settings=settings)
    return _serialize(service.get_summary())


@router.patch("/inbox-copilot", response_model=AutomationResponse)
def update_inbox_copilot(
    request: AutomationUpdateRequest,
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    service = InboxCopilotService(db=db, user_id=settings.user_id, settings=settings)
    return _serialize(service.update(enabled=request.enabled))


@router.post("/inbox-copilot/run", response_model=AutomationRunEnvelope)
def run_inbox_copilot(
    request: InboxCopilotRunRequest,
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    service = InboxCopilotService(db=db, user_id=settings.user_id, settings=settings)
    return AutomationRunEnvelope(**service.run(trigger=request.trigger))


@router.get("/meeting-prep", response_model=AutomationResponse)
def get_meeting_prep(
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    service = MeetingPrepService(db=db, user_id=settings.user_id, settings=settings)
    return _serialize(service.get_summary())


@router.patch("/meeting-prep", response_model=AutomationResponse)
def update_meeting_prep(
    request: AutomationUpdateRequest,
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    service = MeetingPrepService(db=db, user_id=settings.user_id, settings=settings)
    return _serialize(service.update(enabled=request.enabled))


@router.post("/meeting-prep/run", response_model=AutomationRunEnvelope)
def run_meeting_prep(
    request: MeetingPrepRunRequest,
    _user: AuthenticatedUser = Depends(require_active_subscription),
    settings: UserSettings = Depends(get_user_settings),
    db: Session = Depends(get_db_for_user),
):
    if request.event_id is not None and not str(request.event_id).strip():
        raise HTTPException(status_code=400, detail="event_id cannot be blank")

    service = MeetingPrepService(db=db, user_id=settings.user_id, settings=settings)
    return AutomationRunEnvelope(
        **service.run(
            event_id=request.event_id,
            include_recent_context=request.include_recent_context,
            trigger=request.trigger,
        )
    )
