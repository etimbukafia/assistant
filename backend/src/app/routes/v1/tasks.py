from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.data.models import Task, Message
from app.data.schemas import (
    TasksListResponse, TaskResponse, TaskCreateRequest,
    ManualTaskCreateRequest, TaskUpdateRequest, TaskSnoozeRequest, TaskListItem
)
from app.intelligence.pattern_tracker import track_task_action
from app.jobs.queue import enqueue_task
from app.services.entity_cache_coordinator import EntityCacheCoordinator

router = APIRouter(prefix="/tasks", tags=["Tasks"])
cache_coordinator = EntityCacheCoordinator()


def _tenant_id() -> str:
    return "default"


def _invalidate_thread_and_prewarm(db: Session, user_id: str, thread_id: str) -> None:
    if not thread_id:
        return
    cache_coordinator.invalidate_thread(_tenant_id(), user_id, thread_id)
    cache_coordinator.prewarm_action_chips(
        db=db,
        tenant_id=_tenant_id(),
        user_id=user_id,
    )


def _invalidate_task(user_id: str, task_id: int) -> None:
    cache_coordinator.invalidate_task(_tenant_id(), user_id, str(task_id))

@router.get("/", response_model=TasksListResponse)
def get_tasks(
    status: str = None,
    priorities: str = None,
    sort: str = "priority",
    limit: int = 50,
    offset: int = 0,
    today_start: str = None,
    today_end: str = None,
    db: Session = Depends(get_db_for_user)
):
    """Get tasks with optional status filter"""
    query = db.query(Task)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            query = query.filter(Task.status == statuses[0])
        else:
            query = query.filter(Task.status.in_(statuses))
    else:
        # Never return dismissed tasks unless explicitly requested
        query = query.filter(Task.status != "dismissed")

    if priorities:
        priority_list = [p.strip() for p in priorities.split(",") if p.strip()]
        if len(priority_list) == 1:
            query = query.filter(Task.priority == priority_list[0])
        else:
            query = query.filter(Task.priority.in_(priority_list))

    # Today filter: tasks created today OR with a deadline today
    if today_start and today_end:
        try:
            t_start = datetime.fromisoformat(today_start)
            t_end = datetime.fromisoformat(today_end)
            query = query.filter(
                (Task.created_at >= t_start) & (Task.created_at < t_end) |
                (Task.deadline >= t_start) & (Task.deadline < t_end)
            )
        except ValueError:
            pass  # ignore malformed dates

    total = query.count()
    if sort == "created_at":
        tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(limit).all()
    else:
        priority_rank = case(
            (Task.priority == "urgent", 0),
            (Task.priority == "high", 1),
            (Task.priority == "normal", 2),
            (Task.priority == "low", 3),
            else_=4
        )
        tasks = query.order_by(priority_rank.asc(), Task.created_at.desc()).offset(offset).limit(limit).all()

    return TasksListResponse(tasks=[TaskListItem.model_validate(t) for t in tasks], total=total)


@router.post("/", response_model=TaskResponse)
def create_task(
    request: TaskCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Create a new task (e.g., from extracted_tasks text approved by user)

    This allows users to convert AI-detected text into real actionable tasks.
    """

    # Verify message exists
    message = db.query(Message).filter(Message.id == request.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Create task
    task = Task(
        user_id=user.user_id,
        message_id=request.message_id,
        title=request.title,
        description=request.description,
        source_snippet=request.source_snippet,
        task_type=request.task_type,
        task_signal=request.task_signal,
        priority=request.priority,
        status=request.status,
        confidence_score=1.0,  # User-approved = full confidence
        approved_at=datetime.now(timezone.utc) if request.status == "approved" else None
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    # Remove from extracted_tasks if it exists there
    if message.extracted_tasks:
        def _task_matches(t, title):
            """Match extracted task by title, handling both str and dict formats."""
            if isinstance(t, str):
                return t == title
            if isinstance(t, dict):
                return t.get('title') == title
            return False
        message.extracted_tasks = [t for t in message.extracted_tasks if not _task_matches(t, request.title)]
        db.commit()

    _invalidate_thread_and_prewarm(db, user.user_id, message.thread_id)
    _invalidate_task(user.user_id, task.id)

    # Build response with source message
    task_dict = {
        "id": task.id,
        "message_id": task.message_id,
        "title": task.title,
        "description": task.description,
        "source_snippet": task.source_snippet,
        "task_type": task.task_type,
        "task_signal": task.task_signal,
        "priority": task.priority,
        "status": task.status,
        "approved_at": task.approved_at,
        "completed_at": task.completed_at,
        "dismissed_at": task.dismissed_at,
        "reminder_context": task.reminder_context,
        "scheduled_reminder_at": task.scheduled_reminder_at,
        "last_reminded_at": task.last_reminded_at,
        "reminder_count": task.reminder_count or 0,
        "snoozed_until": task.snoozed_until,
        "related_people": task.related_people or [],
        "related_dates": task.related_dates or [],
        "deadline": task.deadline,
        "deadline_source": task.deadline_source,
        "deadline_user_confirmed": task.deadline_user_confirmed,
        "confidence_score": task.confidence_score,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "source_message": message
    }

    return TaskResponse(**task_dict)


@router.post("/manual", response_model=TaskResponse)
def create_manual_task(
    request: ManualTaskCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Create a task manually (not from email).

    This allows users to add standalone tasks that aren't linked to any email.
    We use a placeholder message ID for database consistency.
    """

    placeholder_message_id = f"__manual_tasks_placeholder__:{user.user_id}"
    manual_thread_id = f"__manual_tasks__:{user.user_id}"

    # Get or create a placeholder message for manual tasks
    # (manual tasks need a message_id due to foreign key constraint)
    placeholder_message = db.query(Message).filter(
        Message.user_id == user.user_id,
        Message.message_id == placeholder_message_id,
    ).first()

    if not placeholder_message:
        placeholder_message = Message(
            user_id=user.user_id,
            message_id=placeholder_message_id,
            thread_id=manual_thread_id,
            subject="Manual Tasks",
            sender="user",
            recipient="user",
            body="",
            received_at=datetime.now(timezone.utc),
            processed=True,
            status="archived"
        )
        db.add(placeholder_message)
        db.commit()
        db.refresh(placeholder_message)

    # Create task
    task = Task(
        user_id=user.user_id,
        message_id=placeholder_message.id,
        thread_id=manual_thread_id,
        title=request.title,
        description=request.description,
        task_type="other",
        task_signal="explicit",  # Manual tasks are always explicit
        priority=request.priority,
        status=request.status,
        confidence_score=1.0,  # User-created = full confidence
        approved_at=datetime.now(timezone.utc) if request.status == "approved" else None,
        # Deadline fields
        deadline=request.deadline,
        deadline_source="explicit" if request.deadline else None,
        deadline_user_confirmed=True if request.deadline else False,
        urgency_suggested_by_ai=False
    )

    db.add(task)
    db.commit()
    db.refresh(task)
    _invalidate_task(user.user_id, task.id)

    return task


@router.get("/stats")
def get_task_stats(db: Session = Depends(get_db_for_user)):
    """Get task statistics"""

    pending_approval = db.query(Task).filter(Task.status == "pending_approval").count()
    approved = db.query(Task).filter(Task.status == "approved").count()
    in_progress = db.query(Task).filter(Task.status == "in_progress").count()
    completed = db.query(Task).filter(Task.status == "completed").count()
    dismissed = db.query(Task).filter(Task.status == "dismissed").count()
    overdue = db.query(Task).filter(
        Task.scheduled_reminder_at < datetime.now(timezone.utc),
        Task.status.in_(["approved", "pending_approval"])
    ).count()

    return {
        "pending_approval": pending_approval,
        "approved": approved,
        "in_progress": in_progress,
        "completed": completed,
        "dismissed": dismissed,
        "overdue": overdue,
        "total": pending_approval + approved + in_progress + completed
    }


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db_for_user)):
    """Get a specific task with source message"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Include source message
    message = db.query(Message).filter(Message.id == task.message_id).first()

    # Convert to dict and add source_message
    task_dict = {
        "id": task.id,
        "message_id": task.message_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "task_signal": task.task_signal,
        "priority": task.priority,
        "status": task.status,
        "approved_at": task.approved_at,
        "completed_at": task.completed_at,
        "dismissed_at": task.dismissed_at,
        "reminder_context": task.reminder_context,
        "scheduled_reminder_at": task.scheduled_reminder_at,
        "last_reminded_at": task.last_reminded_at,
        "reminder_count": task.reminder_count,
        "snoozed_until": task.snoozed_until,
        "related_people": task.related_people or [],
        "related_dates": task.related_dates or [],
        "deadline": task.deadline,
        "deadline_source": task.deadline_source,
        "deadline_user_confirmed": task.deadline_user_confirmed,
        "confidence_score": task.confidence_score,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "source_message": message
    }

    return TaskResponse(**task_dict)


@router.post("/{task_id}/approve")
def approve_task(
    task_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Approve a pending task"""

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "approved"
    task.approved_at = datetime.now(timezone.utc)
    db.commit()

    if task.thread_id:
        _invalidate_thread_and_prewarm(db, user.user_id, task.thread_id)
    _invalidate_task(user.user_id, task.id)

    # Track pattern for learning
    track_task_action(db, "approve", task, task.user_id or user.user_id)

    # Schedule reminder if needed
    if task.scheduled_reminder_at:
        enqueue_task(
            task_type="evaluate_reminder",
            payload={"task_id": task.id, "user_id": task.user_id},
            scheduled_for=task.scheduled_reminder_at,
            db=db
        )

    return {"message": "Task approved", "task_id": task_id}


@router.post("/{task_id}/dismiss")
def dismiss_task(
    task_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Dismiss a task (mark as not relevant)"""

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "dismissed"
    task.dismissed_at = datetime.now(timezone.utc)
    db.commit()

    if task.thread_id:
        _invalidate_thread_and_prewarm(db, user.user_id, task.thread_id)
    _invalidate_task(user.user_id, task.id)

    # Track pattern for learning
    track_task_action(db, "dismiss", task, task.user_id or user.user_id)

    return {"message": "Task dismissed", "task_id": task_id}


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    request: TaskUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Update task details (one-click edit)

    Handles:
    - title, description, priority, scheduled_reminder_at (standard fields)
    - deadline: User-provided deadline (sets deadline_source='explicit', deadline_user_confirmed=True)
    - deadline_confirmed: Confirm AI-suggested deadline (sets deadline_user_confirmed=True)
    - mark_urgent: Confirm AI-suggested urgency (sets priority='urgent', urgency_suggested_by_ai=False)
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update standard fields
    if request.title is not None:
        task.title = request.title
    # Use model_fields_set so that explicit null clears the field (None is not None would drop it)
    if "description" in request.model_fields_set:
        task.description = request.description
    if request.priority is not None:
        task.priority = request.priority
        # If user explicitly sets priority, it's no longer AI-suggested
        task.urgency_suggested_by_ai = False
    if "scheduled_reminder_at" in request.model_fields_set:
        task.scheduled_reminder_at = request.scheduled_reminder_at

    # Handle deadline updates (Smart Todo List)
    if request.clear_deadline is True:
        task.deadline = None
        task.deadline_source = None
        task.deadline_user_confirmed = False
        task.deadline_confidence = None
    elif request.deadline is not None:
        # User explicitly setting deadline overrides AI suggestion
        task.deadline = request.deadline
        task.deadline_source = "explicit"
        task.deadline_user_confirmed = True
        task.deadline_confidence = None  # Clear AI confidence since user set it

    # Handle deadline confirmation (user approving AI suggestion)
    if request.deadline_confirmed is True:
        task.deadline_user_confirmed = True

    # Handle urgency confirmation (user approving AI-suggested urgency)
    if request.mark_urgent is True:
        task.priority = "urgent"
        task.urgency_suggested_by_ai = False  # Now confirmed by user

    db.commit()

    # If reminder was explicitly set or updated, enqueue an evaluation job
    if (
        "scheduled_reminder_at" in request.model_fields_set
        and task.scheduled_reminder_at is not None
        and task.status in ("approved", "in_progress")
    ):
        enqueue_task(
            task_type="evaluate_reminder",
            payload={"task_id": task.id, "user_id": task.user_id},
            scheduled_for=task.scheduled_reminder_at,
            db=db,
        )

    if task.thread_id:
        _invalidate_thread_and_prewarm(db, user.user_id, task.thread_id)
    _invalidate_task(user.user_id, task.id)

    db.refresh(task)

    return task


@router.post("/{task_id}/start")
def start_task(task_id: int, db: Session = Depends(get_db_for_user)):
    """Move task to in_progress status

    Typically used when a waiting_for task receives the expected response
    and the user needs to take action on it.
    """

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "in_progress"
    db.commit()
    if task.user_id:
        _invalidate_task(task.user_id, task.id)

    return {"message": "Task started", "task_id": task_id}


@router.post("/{task_id}/complete")
def complete_task(
    task_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Mark task as completed"""

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    db.commit()

    if task.thread_id:
        _invalidate_thread_and_prewarm(db, user.user_id, task.thread_id)
    _invalidate_task(user.user_id, task.id)

    return {"message": "Task completed", "task_id": task_id}


@router.post("/{task_id}/snooze")
def snooze_task(
    task_id: int,
    request: TaskSnoozeRequest,
    db: Session = Depends(get_db_for_user)
):
    """Snooze task reminders until specified time"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.snoozed_until = request.snooze_until
    task.status = "snoozed"
    db.commit()
    if task.user_id:
        _invalidate_task(task.user_id, task.id)

    return {"message": "Task snoozed", "snoozed_until": request.snooze_until}
