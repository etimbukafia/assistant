from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# App infrastructure
from app.infra.database import init_db, SessionLocal
from app.infra.logging_config import setup_logging
import app.handlers # Register event handlers
from app.data.models import TaskQueue
from app.jobs.queue import queue_service
from app.jobs.worker import get_next_cleanup_time, get_next_chat_cleanup_time

# Router imports
from app.routes.v1 import (
    auth,
    messages,
    tasks,
    settings,
    digests,
    scheduling,
    calendar,
    memory,
    gdpr,
    system,
    chat,
    subscription,
    billing,
    webhooks,
    notifications,
)
from app.handlers.webhook_handlers import router as billing_router
from app.security.rate_limiter import RateLimitMiddleware

app = FastAPI(
    title="AI Assistant for Assistants",
    description="Universal Inbox Brain - Email management with AI",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Next.js (if used)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (applied to chat and sync endpoints)
app.add_middleware(RateLimitMiddleware)

# Initialize database and logging on startup
@app.on_event("startup")
def startup_event():
    setup_logging(level="INFO", structured=False)
    init_db()
    schedule_cleanup_job_if_needed()
    schedule_chat_cleanup_job_if_needed()
    schedule_gmail_watch_renewal_if_needed()
    preload_email_classifier()


def preload_email_classifier():
    """
    Preload the email classifier model to avoid first-request latency.

    The MiniLM model (~80MB) takes a few seconds to load on first use.
    Preloading at startup ensures the first sync request is fast.
    """
    try:
        from app.services.email_classifier import preload_classifier
        if preload_classifier():
            print("Email classifier model preloaded successfully")
        else:
            print("Email classifier not available (sentence-transformers not installed)")
    except Exception as e:
        print(f"Failed to preload email classifier: {e}")


def schedule_cleanup_job_if_needed():
    """
    Ensure the nightly data cleanup job is scheduled.

    This job:
    - Expires content for messages older than 30 days
    - Hard deletes source-deleted messages with no open tasks
    """

    db = SessionLocal()
    try:
        # Check if cleanup job already scheduled
        existing = db.query(TaskQueue).filter(
            TaskQueue.task_type == "data_cleanup",
            TaskQueue.status == "pending"
        ).first()

        if not existing:
            next_run = get_next_cleanup_time()
            queue_service.enqueue(
                task_type="data_cleanup",
                payload={},
                scheduled_for=next_run,
                db=db
            )
            print(f"Scheduled data cleanup job for {next_run}")
    finally:
        db.close()


def schedule_chat_cleanup_job_if_needed():
    """
    Ensure the hourly chat cleanup job is scheduled.

    This job:
    - Deletes reflection sessions older than 24 hours
    - Deletes command sessions older than 30 days
    """

    db = SessionLocal()
    try:
        # Check if chat cleanup job already scheduled
        existing = db.query(TaskQueue).filter(
            TaskQueue.task_type == "chat_cleanup",
            TaskQueue.status == "pending"
        ).first()

        if not existing:
            next_run = get_next_chat_cleanup_time()
            queue_service.enqueue(
                task_type="chat_cleanup",
                payload={},
                scheduled_for=next_run,
                db=db
            )
            print(f"Scheduled chat cleanup job for {next_run}")
    finally:
        db.close()


def schedule_gmail_watch_renewal_if_needed():
    """
    Ensure the daily Gmail watch renewal job is scheduled.

    This job:
    - Renews Pub/Sub watches for all connected Gmail accounts
    - Gmail watches expire after 7 days; daily renewal keeps them active
    """

    db = SessionLocal()
    try:
        existing = db.query(TaskQueue).filter(
            TaskQueue.task_type == "renew_gmail_watches",
            TaskQueue.status == "pending"
        ).first()

        if not existing:
            from datetime import datetime, timedelta
            next_run = datetime.utcnow() + timedelta(days=1)
            queue_service.enqueue(
                task_type="renew_gmail_watches",
                payload={},
                scheduled_for=next_run,
                db=db
            )
            print(f"Scheduled Gmail watch renewal for {next_run}")
    finally:
        db.close()

# Include Routers
app.include_router(auth.router)
app.include_router(messages.router)
app.include_router(tasks.router)
app.include_router(settings.router)
app.include_router(digests.router)
app.include_router(scheduling.router)
app.include_router(calendar.router)
app.include_router(memory.router)
app.include_router(gdpr.router)
app.include_router(system.router)
app.include_router(chat.router)
app.include_router(subscription.router)
app.include_router(billing.router)
app.include_router(billing_router)  # Polar webhooks
app.include_router(webhooks.router)  # Gmail Pub/Sub
app.include_router(notifications.router)


@app.get("/")
def root():
    return {
        "message": "AI Assistant for Assistants API",
        "version": "1.0.0",
        "features": [
            "Gmail integration",
            "Auto-summarize threads",
            "Extract tasks, dates, people, decisions",
            "Classify needs reply vs FYI",
            "Draft replies"
        ]
    }
