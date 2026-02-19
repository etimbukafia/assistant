"""Playground calendar routes."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.data.models import CalendarEvent
from app.data.schemas import CalendarEventResponse
from app.db import get_db


router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/events", response_model=List[CalendarEventResponse])
def list_events(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(CalendarEvent)
        .filter(CalendarEvent.user_id == user_id)
        .order_by(CalendarEvent.start_at.asc())
        .all()
    )


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_event(
    event_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    event = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.user_id == user_id,
            CalendarEvent.event_id == event_id,
        )
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
