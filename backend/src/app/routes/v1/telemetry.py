from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.models import UITelemetryEvent
from app.data.schemas import (
    TelemetryBatchRequest,
    TelemetryIngestResponse,
    TelemetryDashboardResponse,
    TelemetryFunnelResponse,
    TelemetryDailyCount,
)
from app.security.auth import (
    AuthenticatedUser,
    get_current_user,
    get_db_for_user,
    require_admin_user,
)
from app.infra.database import get_db


router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("/events", response_model=TelemetryIngestResponse)
def ingest_events(
    request: TelemetryBatchRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    # Guardrail: prevent very large payload abuse
    incoming = request.events[:100]
    oldest_allowed = datetime.now(timezone.utc) - timedelta(days=30)

    accepted = 0
    deduped = 0
    for evt in incoming:
        event_id = (evt.event_id or "").strip()[:120] or None
        event_name = (evt.event_name or "").strip()[:120]
        if not event_name:
            continue
        payload = evt.event_payload or {}
        if isinstance(payload, dict) and len(payload) > 60:
            payload = dict(list(payload.items())[:60])

        client_ts = evt.client_ts
        if client_ts and client_ts < oldest_allowed:
            client_ts = oldest_allowed

        if event_id:
            existing = db.query(UITelemetryEvent.id).filter(
                UITelemetryEvent.user_id == user.user_id,
                UITelemetryEvent.event_id == event_id,
            ).first()
            if existing:
                deduped += 1
                continue

        row = UITelemetryEvent(
            user_id=user.user_id,
            event_id=event_id,
            event_name=event_name,
            event_payload=payload,
            page_path=(evt.page_path or "")[:240] or None,
            session_id=(evt.session_id or "")[:120] or None,
            client_ts=client_ts,
        )
        db.add(row)
        accepted += 1

    if accepted:
        db.commit()
    return TelemetryIngestResponse(accepted=accepted, deduped=deduped)


@router.get("/dashboard", response_model=TelemetryDashboardResponse)
def telemetry_dashboard(
    days: int = Query(default=7, ge=1, le=90),
    user_id: Optional[str] = Query(default=None, min_length=1, max_length=255),
    filter_event_name: Optional[str] = Query(default=None, alias="event_name", min_length=1, max_length=120),
    user: AuthenticatedUser = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base_query = db.query(UITelemetryEvent).filter(UITelemetryEvent.created_at >= since)
    if user_id:
        base_query = base_query.filter(UITelemetryEvent.user_id == user_id)
    if filter_event_name:
        base_query = base_query.filter(UITelemetryEvent.event_name == filter_event_name)

    total_events = base_query.count()
    event_rows = db.query(
        UITelemetryEvent.event_name,
        func.count(UITelemetryEvent.id),
    ).filter(UITelemetryEvent.created_at >= since)
    if user_id:
        event_rows = event_rows.filter(UITelemetryEvent.user_id == user_id)
    if filter_event_name:
        event_rows = event_rows.filter(UITelemetryEvent.event_name == filter_event_name)
    event_rows = event_rows.group_by(UITelemetryEvent.event_name).all()
    event_counts = {name: count for name, count in event_rows}
    # Proposals are currently unhooked; hide legacy proposal telemetry from admin views.
    event_counts.pop("proposal_approved", None)
    event_counts.pop("proposal_bulk_approved", None)

    chip_clicked = event_counts.get("chat_chip_clicked", 0)
    message_sent = event_counts.get("chat_message_sent", 0)
    action_approved = event_counts.get("chat_action_approved", 0)
    funnel = TelemetryFunnelResponse(
        chip_clicked=chip_clicked,
        message_sent=message_sent,
        action_approved=action_approved,
        click_to_send_rate=(message_sent / chip_clicked) if chip_clicked else 0.0,
        send_to_approve_rate=(action_approved / message_sent) if message_sent else 0.0,
        click_to_approve_rate=(action_approved / chip_clicked) if chip_clicked else 0.0,
    )

    daily_query = db.query(
        func.date(UITelemetryEvent.created_at).label("day"),
        UITelemetryEvent.event_name,
        func.count(UITelemetryEvent.id).label("count"),
    ).filter(
        UITelemetryEvent.created_at >= since,
        UITelemetryEvent.event_name.in_(
            [
                "chat_chip_clicked",
                "chat_message_sent",
                "chat_action_approved",
            ]
        ),
    )
    if user_id:
        daily_query = daily_query.filter(UITelemetryEvent.user_id == user_id)
    if filter_event_name:
        daily_query = daily_query.filter(UITelemetryEvent.event_name == filter_event_name)
    daily_rows = daily_query.group_by(
        func.date(UITelemetryEvent.created_at),
        UITelemetryEvent.event_name,
    ).order_by(
        func.date(UITelemetryEvent.created_at).asc()
    ).all()

    by_day: dict[str, TelemetryDailyCount] = {}
    for day, event_name, count in daily_rows:
        key = str(day)
        if key not in by_day:
            by_day[key] = TelemetryDailyCount(date=key)
        if event_name == "chat_chip_clicked":
            by_day[key].chip_clicked = int(count)
        elif event_name == "chat_message_sent":
            by_day[key].message_sent = int(count)
        elif event_name == "chat_action_approved":
            by_day[key].action_approved += int(count)

    return TelemetryDashboardResponse(
        days=days,
        total_events=total_events,
        event_counts=event_counts,
        funnel=funnel,
        daily=list(by_day.values()),
    )
