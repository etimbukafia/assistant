"""
Task Queue Model - Reusable across projects

This model is database-agnostic (works with any SQLAlchemy setup).
Just import and add to your Base.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime


def create_task_queue_model(Base):
    """
    Factory function to create TaskQueue model with your Base class

    Usage:
        from app.infra.database import Base
        from core.queue.models import create_task_queue_model

        TaskQueue = create_task_queue_model(Base)
    """

    class TaskQueue(Base):
        """
        Persistent task queue for background processing

        Enables:
        - Event chaining (one task completion triggers another)
        - Retry logic for failed tasks
        - Survives server restarts
        - Safe concurrent processing with Postgres row locking
        """
        __tablename__ = "task_queue"

        id = Column(Integer, primary_key=True, index=True)

        # Task identification
        task_type = Column(String, index=True)  # e.g., "emit_event", "send_notification"
        correlation_id = Column(String, index=True, nullable=True)  # Link related tasks
        user_id = Column(String, index=True, nullable=True)  # For RLS context

        # Task data
        payload = Column(JSON)  # Task-specific data

        # Execution tracking
        status = Column(String, default="pending", index=True)  # pending, in_progress, completed, failed
        attempts = Column(Integer, default=0)
        max_attempts = Column(Integer, default=3)
        last_error = Column(Text, nullable=True)

        # Scheduling
        scheduled_for = Column(DateTime, default=datetime.utcnow, index=True)  # When to run
        started_at = Column(DateTime, nullable=True)
        completed_at = Column(DateTime, nullable=True)

        # Metadata
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    return TaskQueue
