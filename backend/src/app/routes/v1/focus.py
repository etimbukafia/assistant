from datetime import datetime, date, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.data.models import DailyFocus, Task
from app.data.schemas import (
    DailyFocusResponse, DailyFocusUpdateRequest, WeeklySummaryResponse, GoalItem
)

router = APIRouter(prefix="/focus", tags=["Focus"])


def _to_response(row: DailyFocus) -> DailyFocusResponse:
    """Convert a DailyFocus model to response schema."""
    goals = [GoalItem(**g) for g in (row.goals or [])]
    completed = sum(1 for g in goals if g.completed)

    # Build frog_task response if relationship loaded
    frog_task = None
    if row.frog_task is not None:
        try:
            from app.data.schemas import TaskResponse
            frog_task = TaskResponse.model_validate(row.frog_task)
        except Exception:
            # Graceful degradation — show focus without frog details
            frog_task = None

    return DailyFocusResponse(
        id=row.id,
        focus_date=row.focus_date.isoformat(),
        goals=goals,
        frog_task_id=row.frog_task_id,
        frog_task=frog_task,
        weekly_target=row.weekly_target,
        goals_completed=completed,
        goals_total=len(goals),
    )


def _get_or_create(db: Session, user_id: str, focus_date: date) -> DailyFocus:
    """Get existing daily focus or create an empty one."""
    row = db.query(DailyFocus).filter(
        and_(DailyFocus.user_id == user_id, DailyFocus.focus_date == focus_date)
    ).first()

    if not row:
        row = DailyFocus(user_id=user_id, focus_date=focus_date, goals=[])
        db.add(row)
        db.commit()
        db.refresh(row)

    return row


def _parse_date(date_str: str | None) -> date:
    """Parse ISO date string or return today."""
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    return date.today()


@router.get("/daily", response_model=DailyFocusResponse)
def get_daily_focus(
    date: str = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Get daily focus for a given date (default: today). Creates empty row if none exists."""
    focus_date = _parse_date(date)
    row = _get_or_create(db, user.user_id, focus_date)
    return _to_response(row)


@router.put("/daily", response_model=DailyFocusResponse)
def update_daily_focus(
    request: DailyFocusUpdateRequest,
    date: str = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Upsert daily focus. Validates goals (max 3) and frog_task ownership."""
    focus_date = _parse_date(date)
    row = _get_or_create(db, user.user_id, focus_date)

    if request.goals is not None:
        if len(request.goals) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 goals allowed.")
        row.goals = [g.model_dump() for g in request.goals]

    if "frog_task_id" in (request.model_fields_set or set()):
        if request.frog_task_id is None or request.frog_task_id == 0:
            row.frog_task_id = None
        else:
            task = db.query(Task).filter(
                and_(Task.id == request.frog_task_id, Task.user_id == user.user_id)
            ).first()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found.")
            if task.status in ("completed", "dismissed"):
                raise HTTPException(status_code=400, detail="Cannot set a completed or dismissed task as frog.")
            row.frog_task_id = request.frog_task_id

    if request.weekly_target is not None:
        row.weekly_target = request.weekly_target
        # Propagate weekly_target to all rows in the same ISO week
        iso_year, iso_week, _ = focus_date.isocalendar()
        week_start = date.fromisocalendar(iso_year, iso_week, 1)
        week_end = date.fromisocalendar(iso_year, iso_week, 7)
        db.query(DailyFocus).filter(
            and_(
                DailyFocus.user_id == user.user_id,
                DailyFocus.focus_date >= week_start,
                DailyFocus.focus_date <= week_end,
                DailyFocus.id != row.id,
            )
        ).update({"weekly_target": request.weekly_target})

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.get("/weekly-summary", response_model=WeeklySummaryResponse)
def get_weekly_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Get daily focus rows for the current ISO week plus task completion stats."""
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    week_end = date.fromisocalendar(iso_year, iso_week, 7)

    rows = db.query(DailyFocus).filter(
        and_(
            DailyFocus.user_id == user.user_id,
            DailyFocus.focus_date >= week_start,
            DailyFocus.focus_date <= week_end,
        )
    ).order_by(DailyFocus.focus_date).all()

    days = [_to_response(r) for r in rows]
    total_goals_set = sum(d.goals_total for d in days)
    total_goals_completed = sum(d.goals_completed for d in days)

    # Count tasks completed this week
    week_start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
    tasks_completed = db.query(Task).filter(
        and_(
            Task.user_id == user.user_id,
            Task.status == "completed",
            Task.completed_at >= week_start_dt,
        )
    ).count()

    # Get weekly target from any row
    weekly_target = None
    if rows:
        weekly_target = rows[0].weekly_target

    return WeeklySummaryResponse(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        weekly_target=weekly_target,
        days=days,
        total_goals_set=total_goals_set,
        total_goals_completed=total_goals_completed,
        tasks_completed_this_week=tasks_completed,
    )
