from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.security.auth import get_db_for_user, get_db
from app.data.models import Message, TaskQueue
from core.events import get_registered_handlers

router = APIRouter(prefix="", tags=["System"])

@router.get("/stats")
def get_stats(db: Session = Depends(get_db_for_user)):
    """Get inbox statistics"""
    total_messages = db.query(Message).count()
    needs_reply_count = db.query(Message).filter(Message.needs_reply == True).count()
    fyi_only = db.query(Message).filter(Message.needs_reply == False).count()
    unprocessed = db.query(Message).filter(Message.processed == False).count()

    # Count messages with tasks (non-empty array)
    has_tasks_count = db.query(Message).filter(
        and_(
            Message.extracted_tasks.isnot(None),
            func.json_array_length(Message.extracted_tasks) > 0
        )
    ).count()

    return {
        "total_messages": total_messages,
        "needs_reply_count": needs_reply_count,
        "fyi_only": fyi_only,
        "unprocessed": unprocessed,
        "has_tasks_count": has_tasks_count
    }

@router.get("/debug/handlers")
def list_event_handlers():
    """List all registered event handlers (for debugging)"""
    return {
        "handlers": get_registered_handlers(),
        "description": "Event handlers currently registered in the system"
    }

@router.get("/queue/stats")
def get_queue_stats(db: Session = Depends(get_db)):
    """
    Get task queue statistics (Phase 2)

    Shows status of background task processing
    """
    try:
        # Count tasks by status
        pending = db.query(TaskQueue).filter(TaskQueue.status == "pending").count()
        in_progress = db.query(TaskQueue).filter(TaskQueue.status == "in_progress").count()
        completed = db.query(TaskQueue).filter(TaskQueue.status == "completed").count()
        failed = db.query(TaskQueue).filter(TaskQueue.status == "failed").count()

        # Count by task type
        task_types = {}
        
        type_counts = db.query(
            TaskQueue.task_type,
            TaskQueue.status,
            func.count(TaskQueue.id)
        ).group_by(TaskQueue.task_type, TaskQueue.status).all()

        for task_type, status, count in type_counts:
            if task_type not in task_types:
                task_types[task_type] = {}
            task_types[task_type][status] = count

        return {
            "total": {
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
                "failed": failed,
                "total": pending + in_progress + completed + failed
            },
            "by_type": task_types,
            "worker_status": "Check if worker is running: python -m app.worker"
        }
    except Exception as e:
        # If task_queue table doesn't exist (SQLite or not migrated)
        return {
            "error": "Queue stats unavailable",
            "message": "Using SQLite or queue table not created. Use Supabase for Phase 2 queue.",
            "detail": str(e)
        }
