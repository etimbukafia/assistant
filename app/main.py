from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from .config import settings

from core.events import emit_event, get_registered_handlers
from .database import get_db, init_db
from .models import Message, GmailAccount, TaskQueue, Task, UserSettings, PrincipalMemory, DecisionPattern, ContactContext
from .schemas import (
    MessageResponse, SyncResponse, DraftReplyRequest, DraftReplyResponse, MessagesListResponse,
    UserSettingsResponse, UserSettingsUpdateRequest,
    TaskResponse, TasksListResponse, TaskCreateRequest, TaskUpdateRequest, TaskSnoozeRequest, ManualTaskCreateRequest,
    SchedulingSuggestionResponse, SchedulingSuggestionSendRequest,
    CalendarEventCreateRequest, CalendarEventResponse,
    CalendarAvailabilityRequest, CalendarAvailabilityResponse,
    CalendarSettingsResponse, CalendarSettingsUpdateRequest, CalendarInfoResponse,
    PrincipalMemoryCreate, PrincipalMemoryUpdate, PrincipalMemoryResponse, PrincipalMemoryListResponse,
    DecisionPatternResponse, DecisionPatternListResponse, DecisionPatternActionRequest,
    ContactContextResponse, ContactContextUpdateRequest, ContactContextListResponse,
    DigestPreferences, DigestResponse, DigestsListResponse,
)
from .gmail_integration import GmailClient
from .ai_processor import AIProcessor
from .thread_state_service import ThreadStateService
from .encryption import encrypt_body

# Import handlers to register them with event system
import app.handlers
from app.logging_config import setup_logging

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

# Initialize database and logging on startup
@app.on_event("startup")
def startup_event():
    setup_logging(level="INFO", structured=False)
    init_db()
    schedule_cleanup_job_if_needed()


def schedule_cleanup_job_if_needed():
    """
    Ensure the nightly data cleanup job is scheduled.

    This job:
    - Expires content for messages older than 30 days
    - Hard deletes source-deleted messages with no open tasks
    """
    from .models import TaskQueue
    from .database import SessionLocal
    from .queue import enqueue_task
    from .worker import get_next_cleanup_time

    db = SessionLocal()
    try:
        # Check if cleanup job already scheduled
        existing = db.query(TaskQueue).filter(
            TaskQueue.task_type == "data_cleanup",
            TaskQueue.status == "pending"
        ).first()

        if not existing:
            next_run = get_next_cleanup_time()
            enqueue_task(
                task_type="data_cleanup",
                payload={},
                scheduled_for=next_run,
                db=db
            )
            print(f"Scheduled data cleanup job for {next_run}")
    finally:
        db.close()


# AI processor can be global (stateless)
ai_processor = AIProcessor()

# Gmail client factory (creates instance with database session)
def get_gmail_client(db: Session = Depends(get_db)) -> GmailClient:
    """Create GmailClient with database session for token storage"""
    return GmailClient(db=db)

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

@app.get("/auth/gmail")
def start_gmail_auth(gmail_client: GmailClient = Depends(get_gmail_client)):
    """
    Start Gmail OAuth flow

    Returns authorization URL that user should visit to grant permissions
    """
    try:
        auth_url, state = gmail_client.get_authorization_url()
        return {
            "auth_url": auth_url,
            "state": state,
            "message": "Visit auth_url to authorize Gmail access"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start OAuth flow: {str(e)}")

@app.get("/auth/gmail/callback")
def gmail_callback(code: str, state: str, gmail_client: GmailClient = Depends(get_gmail_client)):
    """
    OAuth callback endpoint - Google redirects here after user grants permissions

    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection
    """
    # Get frontend URL from config
    frontend_url = settings.FRONTEND_URL

    try:
        creds = gmail_client.authenticate_with_code(code, state)
        # Redirect to frontend dashboard on success
        return RedirectResponse(url=f"{frontend_url}/dashboard")
    except Exception as e:
        # Redirect to frontend home page with error parameter
        return RedirectResponse(url=f"{frontend_url}/?error=auth_failed")

@app.get("/auth/gmail/status")
def gmail_auth_status(gmail_client: GmailClient = Depends(get_gmail_client)):
    """Check if Gmail is authenticated"""
    is_auth = gmail_client.load_credentials()
    return {
        "authenticated": is_auth,
        "message": "Gmail is authenticated" if is_auth else "Not authenticated. Visit /auth/gmail to start OAuth flow"
    }

@app.post("/auth/gmail/revoke")
def revoke_gmail_auth(db: Session = Depends(get_db)):
    """
    Revoke Gmail authentication and delete ALL user data.

    This performs a complete data deletion:
    - All Messages and related data (Tasks, Reminders, Scheduling, etc.)
    - Memory data (PrincipalMemory, DecisionPattern, ContactContext)
    - Agent activity logs
    - Calendar events
    - Gmail account credentials
    - Pending queue tasks

    Only UserSettings are preserved.
    """
    from .models import (
        Task, TaskReminder, SchedulingSuggestion,
        CalendarEvent, AgentActivityLog,
        PrincipalMemory, DecisionPattern, ContactContext
    )

    try:
        deletion_summary = {}

        # Delete in order respecting foreign key constraints

        # 1. Delete task reminders (depends on tasks)
        deletion_summary["task_reminders"] = db.query(TaskReminder).delete()

        # 2. Delete tasks (depends on messages)
        deletion_summary["tasks"] = db.query(Task).delete()

        # 3. Delete scheduling suggestions (depends on messages)
        deletion_summary["scheduling_suggestions"] = db.query(SchedulingSuggestion).delete()

        # 4. Delete calendar events (depends on messages/suggestions)
        deletion_summary["calendar_events"] = db.query(CalendarEvent).delete()

        # 5. Delete agent activity logs (depends on messages/tasks)
        deletion_summary["agent_logs"] = db.query(AgentActivityLog).delete()

        # 6. Delete messages
        deletion_summary["messages"] = db.query(Message).delete()

        # 7. Delete memory data
        deletion_summary["principal_memory"] = db.query(PrincipalMemory).delete()
        deletion_summary["decision_patterns"] = db.query(DecisionPattern).delete()
        deletion_summary["contact_contexts"] = db.query(ContactContext).delete()

        # 8. Delete pending queue tasks
        deletion_summary["queue_tasks"] = db.query(TaskQueue).delete()

        # 9. Finally, delete Gmail account credentials
        deletion_summary["gmail_accounts"] = db.query(GmailAccount).delete()

        db.commit()

        return {
            "success": True,
            "message": "All user data deleted. UserSettings preserved. Re-authenticate at /auth/gmail",
            "deleted": deletion_summary
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete data: {str(e)}")

@app.post("/sync", response_model=SyncResponse)
async def sync_messages(
    background_tasks: BackgroundTasks,
    max_results: int = 3,
    query: str = "",
    db: Session = Depends(get_db),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    Sync messages from Gmail and process with batched LLM calls.

    Flow:
    1. Fetch messages from Gmail
    2. Save to database
    3. Enqueue process_email tasks
    4. Trigger immediate batch processing (no delay)
    """
    from app.message_processor import get_user_id
    from app.worker import handle_process_email_batch
    from app.queue import queue_service

    try:
        # Fetch messages from Gmail
        messages = gmail_client.get_messages(max_results=max_results, query=query)

        synced_count = 0
        message_ids = []
        user_id = get_user_id(db)

        for msg_data in messages:
            # Check if message already exists
            existing = db.query(Message).filter(
                Message.message_id == msg_data['message_id']
            ).first()

            if existing:
                continue

            # Save message to database
            attachments = msg_data.get('attachments') or []
            message = Message(
                message_id=msg_data['message_id'],
                thread_id=msg_data['thread_id'],
                subject=msg_data['subject'],
                sender=msg_data['sender'],
                recipient=msg_data['recipient'],
                body=encrypt_body(msg_data['body']),
                body_encrypted=True,
                received_at=msg_data['received_at'],
                processed=False,
                has_attachments=bool(attachments),
                attachments=attachments,
            )

            db.add(message)
            db.flush()
            message_ids.append(message.id)
            synced_count += 1

        # Store history ID for deletion tracking
        account = db.query(GmailAccount).first()
        if account and not account.last_history_id:
            history_id = gmail_client.get_current_history_id()
            if history_id:
                account.last_history_id = history_id

        db.commit()

        # Process messages in batch (immediate, no queue delay)
        if message_ids:
            # Enqueue tasks for tracking/retry purposes
            for msg_id in message_ids:
                queue_service.enqueue(
                    task_type="process_email",
                    payload={"message_id": msg_id},
                    user_id=user_id,
                    db=db
                )

            # Trigger immediate batch processing
            await queue_service.process_batch_now(
                user_id=user_id,
                task_type="process_email",
                handler=handle_process_email_batch,
                db=db
            )

            # Emit events for other handlers (attachments, task extraction, etc.)
            for msg_id in message_ids:
                emit_event(
                    event_name="message_received",
                    payload={"message_id": msg_id},
                    background_tasks=background_tasks
                )

        return SyncResponse(
            synced_count=synced_count,
            processed_count=synced_count,
            message=f"Successfully synced and processed {synced_count} messages."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@app.post("/sync/deletions")
def sync_deletions(
    db: Session = Depends(get_db),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    Sync Gmail-side deletions to mark messages as source_deleted.

    This uses the Gmail History API to detect messages that were deleted
    from Gmail after being synced to our system.
    """
    # Get account with history ID
    account = db.query(GmailAccount).first()
    if not account:
        raise HTTPException(status_code=400, detail="No Gmail account connected")

    if not account.last_history_id:
        # Initialize history ID if not set
        history_id = gmail_client.get_current_history_id()
        if history_id:
            account.last_history_id = history_id
            db.commit()
        return {
            "message": "History tracking initialized. Run again to check for deletions.",
            "marked_deleted": 0,
            "total_deletions": 0
        }

    # Get deleted message IDs since last check
    deleted_ids, new_history_id = gmail_client.get_deleted_message_ids(
        account.last_history_id
    )

    # Mark messages as source_deleted
    marked_count = 0
    for gmail_id in deleted_ids:
        msg = db.query(Message).filter(Message.message_id == gmail_id).first()
        if msg and not msg.source_deleted:
            msg.source_deleted = True
            marked_count += 1

    # Update history ID for next sync
    if new_history_id:
        account.last_history_id = new_history_id

    db.commit()

    return {
        "marked_deleted": marked_count,
        "total_deletions": len(deleted_ids),
        "message": f"Marked {marked_count} messages as deleted from Gmail"
    }


@app.post("/sync/sent")
def sync_sent_messages(
    db: Session = Depends(get_db),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    Sync sent messages from Gmail to update ThreadState.needs_reply.
    
    Rule: "Any outbound message from the user clears ThreadState.needs_reply."
    
    This is deterministic (no LLM) - if sender is user, clear needs_reply.
    """
    from .models import ThreadState
    from datetime import datetime, timezone, timedelta
    
    # Get account info
    account = db.query(GmailAccount).first()
    if not account:
        raise HTTPException(status_code=400, detail="No Gmail account connected")
    
    user_email = account.email
    
    # Fetch sent messages from last 7 days (to catch any we missed)
    since = datetime.now(timezone.utc) - timedelta(days=7)
    
    try:
        sent_messages = gmail_client.get_sent_messages(since=since, max_results=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sent messages: {str(e)}")
    
    updated_count = 0
    thread_ids_updated = []
    
    for sent_msg in sent_messages:
        thread_id = sent_msg['thread_id']
        sent_at = sent_msg['sent_at']
        
        # Find the thread state
        thread_state = db.query(ThreadState).filter(
            ThreadState.thread_id == thread_id
        ).first()
        
        if thread_state and thread_state.needs_reply:
            # User replied - clear needs_reply
            thread_state.needs_reply = False
            thread_state.last_outbound_at = sent_at
            updated_count += 1
            thread_ids_updated.append(thread_id)
    
    db.commit()
    
    return {
        "sent_messages_checked": len(sent_messages),
        "threads_updated": updated_count,
        "thread_ids": thread_ids_updated[:10],  # First 10 for debugging
        "message": f"Cleared needs_reply on {updated_count} threads where user replied"
    }


@app.get("/messages", response_model=MessagesListResponse)
def get_messages(
    skip: int = 0,
    limit: int = 3,
    needs_reply: bool = None,
    db: Session = Depends(get_db)
):
    """Get all messages with optional filtering and their associated tasks"""
    query = db.query(Message)

    if needs_reply is not None:
        query = query.filter(Message.needs_reply == needs_reply)

    # Get total count for metadata
    total = query.count()

    # Get paginated messages
    messages = query.order_by(Message.received_at.desc()).offset(skip).limit(limit).all()

    # Fetch tasks for each message
    message_ids = [msg.id for msg in messages]
    if message_ids:
        tasks_by_message = {}
        tasks = db.query(Task).filter(Task.message_id.in_(message_ids)).all()
        for task in tasks:
            if task.message_id not in tasks_by_message:
                tasks_by_message[task.message_id] = []
            tasks_by_message[task.message_id].append(task)

        # Attach tasks to messages
        message_dicts = []
        for msg in messages:
            msg_dict = {
                "id": msg.id,
                "message_id": msg.message_id,
                "thread_id": msg.thread_id,
                "subject": msg.subject,
                "sender": msg.sender,
                "recipient": msg.recipient,
                "body": msg.decrypted_body,
                "received_at": msg.received_at,
                "summary": msg.summary,
                "needs_reply": msg.needs_reply,
                "extracted_tasks": msg.extracted_tasks,
                "extracted_dates": msg.extracted_dates,
                "extracted_people": msg.extracted_people,
                "extracted_decisions": msg.extracted_decisions,
                "draft_reply": msg.draft_reply,
                "processed": msg.processed,
                "created_at": msg.created_at,
                "status": msg.status,
                "scheduling_intent": msg.scheduling_intent,
                "scheduling_intent_confidence": msg.scheduling_intent_confidence,
                "scheduling_intent_type": msg.scheduling_intent_type,
                "tasks": tasks_by_message.get(msg.id, [])
            }
            message_dicts.append(msg_dict)

        from .schemas import MessageResponse
        messages = [MessageResponse(**msg_dict) for msg_dict in message_dicts]

    return MessagesListResponse(messages=messages, total=total)


@app.get("/messages/new")
def get_new_messages(
    since: datetime,
    db: Session = Depends(get_db)
):
    """
    Get messages received since timestamp.
    
    Used for polling - frontend checks for new items periodically.
    Only returns inbox messages (not archived/synced).
    """
    messages = db.query(Message).filter(
        Message.received_at > since,
        Message.status == "inbox"
    ).order_by(Message.received_at.desc()).all()
    
    # Build response with tasks
    message_dicts = []
    for msg in messages:
        tasks = db.query(Task).filter(Task.message_id == msg.id).all()
        msg_dict = {
            "id": msg.id,
            "message_id": msg.message_id,
            "thread_id": msg.thread_id,
            "subject": msg.subject,
            "sender": msg.sender,
            "recipient": msg.recipient,
            "body": msg.decrypted_body,
            "received_at": msg.received_at,
            "summary": msg.summary,
            "needs_reply": msg.needs_reply,
            "extracted_tasks": msg.extracted_tasks,
            "extracted_dates": msg.extracted_dates,
            "extracted_people": msg.extracted_people,
            "extracted_decisions": msg.extracted_decisions,
            "draft_reply": msg.draft_reply,
            "processed": msg.processed,
            "created_at": msg.created_at,
            "status": msg.status,
            "scheduling_intent": msg.scheduling_intent,
            "scheduling_intent_confidence": msg.scheduling_intent_confidence,
            "scheduling_intent_type": msg.scheduling_intent_type,
            "tasks": tasks
        }
        message_dicts.append(msg_dict)
    
    from .schemas import MessageResponse
    messages_response = [MessageResponse(**msg_dict) for msg_dict in message_dicts]
    
    return {"messages": messages_response, "count": len(messages_response)}


@app.get("/messages/{message_id}", response_model=MessageResponse)
def get_message(message_id: int, db: Session = Depends(get_db)):
    """Get a specific message by ID with its associated tasks and thread context"""
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Fetch tasks for this message
    tasks = db.query(Task).filter(Task.message_id == message_id).all()
    
    # Fetch thread context for history awareness
    thread_state = db.query(ThreadState).filter(
        ThreadState.thread_id == message.thread_id
    ).first()

    # Build message dict with tasks and thread context
    msg_dict = {
        "id": message.id,
        "message_id": message.message_id,
        "thread_id": message.thread_id,
        "subject": message.subject,
        "sender": message.sender,
        "recipient": message.recipient,
        "body": message.decrypted_body,
        "received_at": message.received_at,
        "summary": message.summary,
        "needs_reply": message.needs_reply,
        "extracted_tasks": message.extracted_tasks,
        "extracted_dates": message.extracted_dates,
        "extracted_people": message.extracted_people,
        "extracted_decisions": message.extracted_decisions,
        "draft_reply": message.draft_reply,
        "processed": message.processed,
        "created_at": message.created_at,
        "scheduling_intent": message.scheduling_intent,
        "scheduling_intent_confidence": message.scheduling_intent_confidence,
        "scheduling_intent_type": message.scheduling_intent_type,
        # Thread context for history awareness
        "thread_message_count": thread_state.message_count if thread_state else 1,
        "thread_started_at": thread_state.created_at if thread_state else message.received_at,
        "last_user_reply_at": thread_state.last_outbound_at if thread_state else None,
        "tasks": tasks
    }

    from .schemas import MessageResponse
    return MessageResponse(**msg_dict)

@app.post("/messages/{message_id}/draft-reply", response_model=DraftReplyResponse)
def draft_reply(
    message_id: int,
    request: DraftReplyRequest = None,
    db: Session = Depends(get_db)
):
    """
    Generate a draft reply for a message.

    Uses Principal Memory context (tone, preferences, contact info)
    to personalize the draft based on user preferences.
    """
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message_data = {
        'subject': message.subject,
        'body': message.decrypted_body,
        'sender': message.sender
    }

    context = request.context if request else ""

    # Pass db session for Principal Memory context injection
    draft = ai_processor.generate_draft_reply(
        message_data,
        context,
        db=db,
        scheduling_intent=message.scheduling_intent or False
    )

    # Save draft to database
    message.draft_reply = draft
    db.commit()

    return DraftReplyResponse(draft=draft)

@app.post("/messages/{message_id}/reprocess")
def reprocess_message(message_id: int, db: Session = Depends(get_db)):
    """
    Reprocess a message using state-based thread processing.

    This updates the thread state incrementally rather than
    re-analyzing the full thread transcript.
    """
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message_data = {
        'subject': message.subject,
        'body': message.decrypted_body,
        'sender': message.sender
    }

    # Use state-based thread processing
    thread_state_service = ThreadStateService(db)
    ai_results = thread_state_service.process_message(message, message_data)

    message.summary = ai_results['summary']
    message.needs_reply = ai_results['needs_reply']
    message.extracted_tasks = ai_results['extracted_tasks']
    message.extracted_dates = ai_results.get('extracted_dates', [])
    message.extracted_people = ai_results.get('extracted_people', [])
    message.extracted_decisions = ai_results.get('extracted_decisions', [])
    message.processed = True

    db.commit()

    return {"message": "Message reprocessed successfully"}


@app.patch("/messages/{message_id}/status")
def update_message_status(
    message_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """Update message status (inbox, done, archived)"""
    valid_statuses = ["inbox", "done", "archived"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = status
    db.commit()

    return {"message": f"Message marked as {status}", "id": message_id, "status": status}


@app.post("/messages/{message_id}/done")
def mark_message_done(message_id: int, db: Session = Depends(get_db)):
    """Mark a message as done"""
    from .pattern_tracker import track_message_action

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = "done"
    db.commit()

    # Track pattern for learning (especially if marked done without replying)
    track_message_action(db, "mark_done", message)

    return {"message": "Message marked as done", "id": message_id}


@app.post("/messages/{message_id}/archive")
def archive_message(message_id: int, db: Session = Depends(get_db)):
    """Archive a message"""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = "archived"
    db.commit()

    return {"message": "Message archived", "id": message_id}


@app.delete("/messages/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Permanently delete a message and all related data"""
    from .models import SchedulingSuggestion

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Delete related tasks first (foreign key constraint)
    db.query(Task).filter(Task.message_id == message_id).delete(synchronize_session='fetch')

    # Delete related scheduling suggestions
    db.query(SchedulingSuggestion).filter(SchedulingSuggestion.message_id == message_id).delete(synchronize_session='fetch')

    # Flush to ensure deletes are sent to DB before message delete
    db.flush()

    # Now delete the message
    db.delete(message)
    db.commit()

    return {"message": "Message deleted", "id": message_id}


# ========================================
# SETTINGS ENDPOINTS
# ========================================

@app.get("/settings", response_model=UserSettingsResponse)
def get_user_settings(db: Session = Depends(get_db)):
    """Get current user settings ()"""
    settings = db.query(UserSettings).first()
    if not settings:
        # Create default settings
        settings = UserSettings(user_email="default@user.com")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@app.put("/settings", response_model=UserSettingsResponse)
def update_user_settings(
    request: UserSettingsUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update user settings"""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings(user_email="default@user.com")
        db.add(settings)

    # Update fields
    if request.auto_approve_tasks is not None:
        settings.auto_approve_tasks = request.auto_approve_tasks
    if request.task_detection_instructions is not None:
        settings.task_detection_instructions = request.task_detection_instructions
    if request.reminder_preferences is not None:
        settings.reminder_preferences = request.reminder_preferences
    if request.enable_quick_reply_from_task is not None:
        settings.enable_quick_reply_from_task = request.enable_quick_reply_from_task

    db.commit()
    db.refresh(settings)
    return settings


# ========================================
# DIGEST ENDPOINTS
# ========================================

@app.put("/settings/digest")
def update_digest_preferences(
    preferences: DigestPreferences,
    db: Session = Depends(get_db)
):
    """Update user's digest preferences and reschedule jobs."""
    from .worker import schedule_digest_jobs_if_needed
    
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings(user_email="default@user.com")
        db.add(settings)
    
    settings.digest_preferences = preferences.dict()
    db.commit()
    
    # Reschedule digests based on new preferences
    schedule_digest_jobs_if_needed(db)
    
    return {"status": "updated", "preferences": preferences}


@app.get("/digests", response_model=DigestsListResponse)
def get_digests(
    limit: int = 10,
    digest_type: str = None,
    db: Session = Depends(get_db)
):
    """Get recent digests with optional type filter."""
    from .models import Digest
    
    query = db.query(Digest).order_by(Digest.created_at.desc())
    
    if digest_type:
        query = query.filter(Digest.digest_type == digest_type)
    
    total = query.count()
    digests = query.limit(limit).all()
    
    return DigestsListResponse(digests=digests, total=total)


@app.get("/digests/{digest_id}", response_model=DigestResponse)
def get_digest(digest_id: int, db: Session = Depends(get_db)):
    """Get a specific digest by ID."""
    from .models import Digest
    
    digest = db.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest


@app.post("/digests/generate/{digest_type}")
def trigger_digest_now(
    digest_type: str,
    db: Session = Depends(get_db)
):
    """Manually trigger a digest generation."""
    from .queue import enqueue_task
    
    if digest_type not in ["morning_briefing", "end_of_day", "weekly_review"]:
        raise HTTPException(status_code=400, detail="Invalid digest type")
    
    settings = db.query(UserSettings).first()
    user_email = settings.user_email if settings else "default@user.com"
    
    enqueue_task(
        task_type="generate_digest",
        payload={"user_email": user_email, "digest_type": digest_type},
        db=db
    )
    
    return {"status": "queued", "digest_type": digest_type}


# ========================================
# TASK ENDPOINTS
# ========================================

@app.get("/tasks", response_model=TasksListResponse)
def get_tasks(
    status: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get tasks with optional status filter"""
    query = db.query(Task)

    if status:
        query = query.filter(Task.status == status)

    total = query.count()
    tasks = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

    return TasksListResponse(tasks=tasks, total=total)


@app.post("/tasks", response_model=TaskResponse)
def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new task (e.g., from extracted_tasks text approved by user)

    This allows users to convert AI-detected text into real actionable tasks.
    """
    from datetime import datetime, timezone

    # Verify message exists
    message = db.query(Message).filter(Message.id == request.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Create task
    task = Task(
        message_id=request.message_id,
        title=request.title,
        description=request.description,
        source_snippet=request.source_snippet,
        task_type=request.task_type,
        priority=request.priority,
        status=request.status,
        confidence_score=1.0,  # User-approved = full confidence
        approved_at=datetime.now(timezone.utc) if request.status == "approved" else None
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    # Remove from extracted_tasks if it exists there
    if message.extracted_tasks and request.title in message.extracted_tasks:
        message.extracted_tasks = [t for t in message.extracted_tasks if t != request.title]
        db.commit()

    # Build response with source message
    task_dict = {
        "id": task.id,
        "message_id": task.message_id,
        "title": task.title,
        "description": task.description,
        "source_snippet": task.source_snippet,
        "task_type": task.task_type,
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
        "confidence_score": task.confidence_score,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "source_message": message
    }

    return TaskResponse(**task_dict)


@app.post("/tasks/manual", response_model=TaskResponse)
def create_manual_task(
    request: ManualTaskCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Create a task manually (not from email).

    This allows users to add standalone tasks that aren't linked to any email.
    We use a placeholder message ID for database consistency.
    """
    from datetime import datetime, timezone

    # Get or create a placeholder message for manual tasks
    # (manual tasks need a message_id due to foreign key constraint)
    placeholder_message = db.query(Message).filter(
        Message.message_id == "__manual_tasks_placeholder__"
    ).first()

    if not placeholder_message:
        placeholder_message = Message(
            message_id="__manual_tasks_placeholder__",
            thread_id="__manual_tasks__",
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
        message_id=placeholder_message.id,
        thread_id="__manual_tasks__",
        title=request.title,
        description=request.description,
        task_type="explicit",  # Manual tasks are always explicit
        priority=request.priority,
        status="approved",  # Manual tasks start as approved
        confidence_score=1.0,  # User-created = full confidence
        approved_at=datetime.now(timezone.utc),
        # Deadline fields
        deadline=request.deadline,
        deadline_source="explicit" if request.deadline else None,
        deadline_user_confirmed=True if request.deadline else False,
        urgency_suggested_by_ai=False
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
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
        "confidence_score": task.confidence_score,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "source_message": message
    }

    return TaskResponse(**task_dict)


@app.post("/tasks/{task_id}/approve")
def approve_task(task_id: int, db: Session = Depends(get_db)):
    """Approve a pending task"""
    from datetime import datetime, timezone
    from .pattern_tracker import track_task_action

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "approved"
    task.approved_at = datetime.now(timezone.utc)
    db.commit()

    # Track pattern for learning
    track_task_action(db, "approve", task)

    # Schedule reminder if needed
    if task.scheduled_reminder_at:
        from app.queue import enqueue_task
        enqueue_task(
            task_type="evaluate_reminder",
            payload={"task_id": task.id},
            scheduled_for=task.scheduled_reminder_at,
            db=db
        )

    return {"message": "Task approved", "task_id": task_id}


@app.post("/tasks/{task_id}/dismiss")
def dismiss_task(task_id: int, db: Session = Depends(get_db)):
    """Dismiss a task (mark as not relevant)"""
    from datetime import datetime, timezone
    from .pattern_tracker import track_task_action

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "dismissed"
    task.dismissed_at = datetime.now(timezone.utc)
    db.commit()

    # Track pattern for learning
    track_task_action(db, "dismiss", task)

    return {"message": "Task dismissed", "task_id": task_id}


@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    request: TaskUpdateRequest,
    db: Session = Depends(get_db)
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
    if request.description is not None:
        task.description = request.description
    if request.priority is not None:
        task.priority = request.priority
        # If user explicitly sets priority, it's no longer AI-suggested
        task.urgency_suggested_by_ai = False
    if request.scheduled_reminder_at is not None:
        task.scheduled_reminder_at = request.scheduled_reminder_at

    # Handle deadline updates (Smart Todo List)
    if request.deadline is not None:
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
    db.refresh(task)

    return task


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    """Mark task as completed"""
    from datetime import datetime, timezone

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Task completed", "task_id": task_id}


@app.post("/tasks/{task_id}/snooze")
def snooze_task(
    task_id: int,
    request: TaskSnoozeRequest,
    db: Session = Depends(get_db)
):
    """Snooze task reminders until specified time"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.snoozed_until = request.snooze_until
    task.status = "snoozed"
    db.commit()

    return {"message": "Task snoozed", "snoozed_until": request.snooze_until}


@app.get("/tasks/stats")
def get_task_stats(db: Session = Depends(get_db)):
    """Get task statistics"""
    from datetime import datetime, timezone

    pending_approval = db.query(Task).filter(Task.status == "pending_approval").count()
    approved = db.query(Task).filter(Task.status == "approved").count()
    completed = db.query(Task).filter(Task.status == "completed").count()
    overdue = db.query(Task).filter(
        Task.scheduled_reminder_at < datetime.now(timezone.utc),
        Task.status.in_(["approved", "pending_approval"])
    ).count()

    return {
        "pending_approval": pending_approval,
        "approved": approved,
        "completed": completed,
        "overdue": overdue,
        "total": pending_approval + approved + completed
    }


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get inbox statistics"""
    total_messages = db.query(Message).count()
    needs_reply_count = db.query(Message).filter(Message.needs_reply == True).count()
    fyi_only = db.query(Message).filter(Message.needs_reply == False).count()
    unprocessed = db.query(Message).filter(Message.processed == False).count()

    # Count messages with tasks (non-empty array)
    from sqlalchemy import and_, func
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

@app.get("/debug/handlers")
def list_event_handlers():
    """List all registered event handlers (for debugging)"""
    return {
        "handlers": get_registered_handlers(),
        "description": "Event handlers currently registered in the system"
    }

@app.get("/queue/stats")
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
        from sqlalchemy import func
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


# ========================================
# SCHEDULING & CALENDAR ENDPOINTS
# ========================================

@app.get("/scheduling/suggestions")
def get_scheduling_suggestions(
    message_id: int = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get scheduling suggestions, optionally filtered by message or status"""
    from .models import SchedulingSuggestion

    query = db.query(SchedulingSuggestion)

    if message_id:
        query = query.filter(SchedulingSuggestion.message_id == message_id)
    if status:
        query = query.filter(SchedulingSuggestion.status == status)

    suggestions = query.order_by(SchedulingSuggestion.created_at.desc()).all()

    return {
        "suggestions": [SchedulingSuggestionResponse.model_validate(s) for s in suggestions],
        "total": len(suggestions)
    }


@app.get("/scheduling/suggestions/{suggestion_id}", response_model=SchedulingSuggestionResponse)
def get_scheduling_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """Get a specific scheduling suggestion"""
    from .models import SchedulingSuggestion

    suggestion = db.query(SchedulingSuggestion).filter(
        SchedulingSuggestion.id == suggestion_id
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return suggestion


@app.post("/scheduling/suggestions/{suggestion_id}/send")
def send_scheduling_suggestion(
    suggestion_id: int,
    request: SchedulingSuggestionSendRequest = None,
    db: Session = Depends(get_db),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """Send availability reply for a scheduling suggestion"""
    from .models import SchedulingSuggestion, Message
    from datetime import datetime, timezone

    suggestion = db.query(SchedulingSuggestion).filter(
        SchedulingSuggestion.id == suggestion_id
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Get source message for reply
    message = db.query(Message).filter(Message.id == suggestion.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Source message not found")

    # Use edited reply or draft
    reply_text = (request.edited_reply if request and request.edited_reply else suggestion.draft_reply)

    if not reply_text:
        raise HTTPException(status_code=400, detail="No reply text available")

    try:
        # Send reply via Gmail
        gmail_client.send_message(
            to=message.sender,
            subject=f"Re: {message.subject}",
            body=reply_text
        )

        # Update suggestion status
        suggestion.status = "sent"
        db.commit()

        # Create follow-up task
        from .models import Task
        follow_up_task = Task(
            message_id=message.id,
            title=f"Follow up on scheduling with {message.sender.split('@')[0]}",
            description="Check if they responded to your availability",
            task_type="follow_up",
            priority="normal",
            status="approved",
            approved_at=datetime.now(timezone.utc)
        )
        db.add(follow_up_task)
        db.commit()

        return {
            "success": True,
            "message": "Availability reply sent",
            "follow_up_task_id": follow_up_task.id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {str(e)}")


@app.post("/scheduling/suggestions/{suggestion_id}/dismiss")
def dismiss_scheduling_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """Dismiss a scheduling suggestion"""
    from .models import SchedulingSuggestion

    suggestion = db.query(SchedulingSuggestion).filter(
        SchedulingSuggestion.id == suggestion_id
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    suggestion.status = "dismissed"
    db.commit()

    return {"success": True, "message": "Suggestion dismissed"}


@app.post("/calendar/events", response_model=CalendarEventResponse)
def create_calendar_event(
    request: CalendarEventCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a calendar event from a scheduling suggestion"""
    from .agents.modules.scheduling import SchedulingModule

    scheduling_module = SchedulingModule()

    result = scheduling_module.create_calendar_event(
        suggestion_id=request.suggestion_id,
        selected_slot_index=request.selected_slot_index,
        title=request.title,
        description=request.description,
        location=request.location
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create event"))

    # Get the created event from database
    from .models import CalendarEvent
    event = db.query(CalendarEvent).filter(CalendarEvent.id == result["event_id"]).first()

    return event


@app.get("/calendar/events")
def get_calendar_events(
    status: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get calendar events"""
    from .models import CalendarEvent

    query = db.query(CalendarEvent)

    if status:
        query = query.filter(CalendarEvent.status == status)

    total = query.count()
    events = query.order_by(CalendarEvent.start_time.desc()).offset(skip).limit(limit).all()

    return {
        "events": [CalendarEventResponse.model_validate(e) for e in events],
        "total": total
    }


@app.post("/calendar/sync")
async def sync_calendar_events(
    days_ahead: int = 7,
    db: Session = Depends(get_db)
):
    """Sync upcoming events from Google Calendar to database"""
    from .calendar_service import CalendarService
 
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
 
 
@app.get("/calendar/availability")
async def check_calendar_availability(
    start_time: str,
    end_time: str,
    calendar_ids: str = None,
    db: Session = Depends(get_db)
):
    """Check calendar availability for a time range"""
    from .calendar_service import CalendarService
    from datetime import datetime

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


@app.get("/calendar/calendars")
async def get_user_calendars(db: Session = Depends(get_db)):
    """Get list of user's Google calendars"""
    from .calendar_service import CalendarService

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


@app.get("/calendar/settings", response_model=CalendarSettingsResponse)
def get_calendar_settings(db: Session = Depends(get_db)):
    """Get calendar-related user settings"""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings(user_email="default@user.com")
        db.add(settings)
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


@app.patch("/calendar/settings", response_model=CalendarSettingsResponse)
def update_calendar_settings(
    request: CalendarSettingsUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update calendar-related settings"""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings(user_email="default@user.com")
        db.add(settings)

    if request.default_meeting_duration is not None:
        settings.default_meeting_duration = request.default_meeting_duration
    if request.preferred_meeting_times is not None:
        settings.preferred_meeting_times = request.preferred_meeting_times
    if request.buffer_minutes is not None:
        settings.buffer_minutes = request.buffer_minutes
    if request.working_hours_start is not None:
        settings.working_hours_start = request.working_hours_start
    if request.working_hours_end is not None:
        settings.working_hours_end = request.working_hours_end
    if request.default_timezone is not None:
        settings.default_timezone = request.default_timezone
    if request.calendar_ids is not None:
        settings.calendar_ids = request.calendar_ids

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


@app.post("/calendar/events/{event_id}/generate-followups")
def generate_meeting_followups(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate follow-up items for a completed meeting.

    Returns AI-generated suggestions for:
    - Follow-up tasks
    - Email drafts to attendees
    - Reminders for future actions

    All items are returned as pending_approval - user must approve each one.
    """
    from .models import CalendarEvent
    from .briefing_service import generate_follow_ups_for_event

    event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    result = generate_follow_ups_for_event(db, event_id)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate follow-ups")

    return result


@app.post("/scheduling/detect")
def detect_scheduling_intent(
    message_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Manually trigger scheduling detection for a message.

    This is useful for testing or re-processing messages.
    Normally, this happens automatically via the message_received event.
    """
    from .models import Message
    from .agents.modules.scheduling import SchedulingModule

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    scheduling_module = SchedulingModule()

    # Run synchronously for immediate feedback
    result = scheduling_module.generate_suggestions(
        message_id=message.id,
        message_body=message.decrypted_body,
        message_subject=message.subject,
        sender_email=message.sender,
        thread_id=message.thread_id
    )

    return result


# ========================================
# PRINCIPAL MEMORY ENDPOINTS (Executive Context Engine)
# ========================================

DEFAULT_USER_ID = "default"


@app.get("/memory/preferences", response_model=PrincipalMemoryListResponse)
def get_preferences(
    context_type: str = None,
    db: Session = Depends(get_db)
):
    """Get all user preferences, optionally filtered by context type"""
    query = db.query(PrincipalMemory).filter(PrincipalMemory.user_id == DEFAULT_USER_ID)

    if context_type:
        query = query.filter(PrincipalMemory.context_type == context_type)

    preferences = query.order_by(PrincipalMemory.key).all()

    return PrincipalMemoryListResponse(preferences=preferences, total=len(preferences))


@app.post("/memory/preferences", response_model=PrincipalMemoryResponse)
def create_preference(
    request: PrincipalMemoryCreate,
    db: Session = Depends(get_db)
):
    """Create a new user preference"""
    # Check if preference with this key already exists
    existing = db.query(PrincipalMemory).filter(
        PrincipalMemory.user_id == DEFAULT_USER_ID,
        PrincipalMemory.key == request.key,
        PrincipalMemory.context_type == request.context_type
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Preference '{request.key}' for context '{request.context_type}' already exists. Use PUT to update."
        )

    preference = PrincipalMemory(
        user_id=DEFAULT_USER_ID,
        key=request.key,
        value=request.value,
        context_type=request.context_type,
        source=request.source
    )

    db.add(preference)
    db.commit()
    db.refresh(preference)

    return preference


@app.put("/memory/preferences/{preference_id}", response_model=PrincipalMemoryResponse)
def update_preference(
    preference_id: int,
    request: PrincipalMemoryUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing preference"""
    preference = db.query(PrincipalMemory).filter(
        PrincipalMemory.id == preference_id,
        PrincipalMemory.user_id == DEFAULT_USER_ID
    ).first()

    if not preference:
        raise HTTPException(status_code=404, detail="Preference not found")

    if request.value is not None:
        preference.value = request.value
    if request.context_type is not None:
        preference.context_type = request.context_type

    db.commit()
    db.refresh(preference)

    return preference


@app.delete("/memory/preferences/{preference_id}")
def delete_preference(preference_id: int, db: Session = Depends(get_db)):
    """Delete a preference"""
    preference = db.query(PrincipalMemory).filter(
        PrincipalMemory.id == preference_id,
        PrincipalMemory.user_id == DEFAULT_USER_ID
    ).first()

    if not preference:
        raise HTTPException(status_code=404, detail="Preference not found")

    db.delete(preference)
    db.commit()

    return {"message": "Preference deleted", "id": preference_id}


# ========================================
# DECISION PATTERNS ENDPOINTS
# ========================================

@app.get("/memory/patterns", response_model=DecisionPatternListResponse)
def get_patterns(
    status: str = None,
    context_type: str = None,
    min_confidence: float = None,
    db: Session = Depends(get_db)
):
    """Get decision patterns, optionally filtered"""
    query = db.query(DecisionPattern).filter(DecisionPattern.user_id == DEFAULT_USER_ID)

    if status:
        query = query.filter(DecisionPattern.status == status)
    if context_type:
        query = query.filter(DecisionPattern.context_type == context_type)
    if min_confidence:
        query = query.filter(DecisionPattern.confidence >= min_confidence)

    patterns = query.order_by(DecisionPattern.confidence.desc()).all()

    return DecisionPatternListResponse(patterns=patterns, total=len(patterns))


@app.get("/memory/patterns/suggestions", response_model=DecisionPatternListResponse)
def get_pattern_suggestions(db: Session = Depends(get_db)):
    """
    Get patterns ready to be surfaced as suggestions.
    Only returns patterns with:
    - status = 'observed' (not yet suggested/rejected)
    - confidence >= 0.6 (at least 3 occurrences)
    - not stale (has occurrence within 90 days)
    """
    from datetime import datetime, timezone, timedelta

    stale_threshold = datetime.now(timezone.utc) - timedelta(days=90)

    patterns = db.query(DecisionPattern).filter(
        DecisionPattern.user_id == DEFAULT_USER_ID,
        DecisionPattern.status == "observed",
        DecisionPattern.confidence >= 0.6,
        DecisionPattern.last_occurrence_at >= stale_threshold
    ).order_by(DecisionPattern.confidence.desc()).all()

    return DecisionPatternListResponse(patterns=patterns, total=len(patterns))


@app.post("/memory/patterns/{pattern_id}/action")
def action_on_pattern(
    pattern_id: int,
    request: DecisionPatternActionRequest,
    db: Session = Depends(get_db)
):
    """
    Take action on a pattern suggestion:
    - approve: Convert to PrincipalMemory preference
    - reject: Mark as rejected (never suggest again)
    - not_now: Mark as suggested (may surface again later)
    """
    from datetime import datetime, timezone

    pattern = db.query(DecisionPattern).filter(
        DecisionPattern.id == pattern_id,
        DecisionPattern.user_id == DEFAULT_USER_ID
    ).first()

    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    if request.action == "approve":
        # Create preference from pattern
        preference = PrincipalMemory(
            user_id=DEFAULT_USER_ID,
            key=pattern.pattern_key,
            value=pattern.action,
            context_type=pattern.context_type,
            source="approved_suggestion"
        )
        db.add(preference)

        pattern.status = "approved"
        db.commit()

        return {
            "message": "Pattern approved and saved as preference",
            "preference_id": preference.id
        }

    elif request.action == "reject":
        pattern.status = "rejected"
        db.commit()
        return {"message": "Pattern rejected. It won't be suggested again."}

    elif request.action == "not_now":
        pattern.status = "suggested"
        db.commit()
        return {"message": "Pattern noted. May be suggested again later."}

    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: approve, reject, not_now")


# ========================================
# CONTACT CONTEXT ENDPOINTS
# ========================================

@app.get("/memory/contacts", response_model=ContactContextListResponse)
def get_contacts(
    category: str = None,
    db: Session = Depends(get_db)
):
    """Get all contact contexts, optionally filtered by category"""
    query = db.query(ContactContext).filter(ContactContext.user_id == DEFAULT_USER_ID)

    if category:
        query = query.filter(ContactContext.category == category)

    contacts = query.order_by(ContactContext.contact_email).all()

    return ContactContextListResponse(contacts=contacts, total=len(contacts))


@app.get("/memory/contacts/{contact_email}", response_model=ContactContextResponse)
def get_contact(contact_email: str, db: Session = Depends(get_db)):
    """Get contact context for a specific email"""
    contact = db.query(ContactContext).filter(
        ContactContext.user_id == DEFAULT_USER_ID,
        ContactContext.contact_email == contact_email
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact


@app.put("/memory/contacts/{contact_email}", response_model=ContactContextResponse)
def update_contact(
    contact_email: str,
    request: ContactContextUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update contact context (manual fields only: notes, category, preferred_tone)"""
    contact = db.query(ContactContext).filter(
        ContactContext.user_id == DEFAULT_USER_ID,
        ContactContext.contact_email == contact_email
    ).first()

    if not contact:
        # Create new contact context
        contact = ContactContext(
            user_id=DEFAULT_USER_ID,
            contact_email=contact_email
        )
        db.add(contact)

    # Update manual fields only
    if request.contact_name is not None:
        contact.contact_name = request.contact_name
    if request.notes is not None:
        contact.notes = request.notes
    if request.category is not None:
        contact.category = request.category
    if request.preferred_tone is not None:
        contact.preferred_tone = request.preferred_tone

    db.commit()
    db.refresh(contact)

    return contact


@app.delete("/memory/contacts/{contact_email}")
def delete_contact(contact_email: str, db: Session = Depends(get_db)):
    """Delete contact context"""
    contact = db.query(ContactContext).filter(
        ContactContext.user_id == DEFAULT_USER_ID,
        ContactContext.contact_email == contact_email
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()

    return {"message": "Contact context deleted", "email": contact_email}


@app.get("/memory/context/preview")
def preview_context(
    context_type: str,
    sender_email: str = None,
    db: Session = Depends(get_db)
):
    """
    Preview what context would be injected for a given context type.
    Useful for debugging and transparency.
    """
    from .context_builder import ContextBuilder

    valid_types = ["drafting", "scheduling", "task_review"]
    if context_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid context_type. Must be one of: {valid_types}"
        )

    builder = ContextBuilder(db, user_id=DEFAULT_USER_ID)
    summary = builder.get_context_summary(context_type, sender_email)

    return summary


# ========================================
# GDPR COMPLIANCE ENDPOINTS
# ========================================

@app.get("/user/export")
def export_user_data(db: Session = Depends(get_db)):
    """
    GDPR Data Export - Export all user data as JSON.

    Exports:
    - Messages (with decrypted bodies where available)
    - Tasks
    - Scheduling suggestions
    - Calendar events
    - Memory (preferences, patterns, contacts)
    - Settings
    - Agent activity logs
    """
    from datetime import datetime, timezone
    from .models import (
        Task, TaskReminder, SchedulingSuggestion,
        CalendarEvent, AgentActivityLog,
        PrincipalMemory, DecisionPattern, ContactContext
    )

    export_data = {
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "export_version": "1.0",
    }

    # Messages with decrypted bodies
    messages = db.query(Message).all()
    export_data["messages"] = [
        {
            "id": m.id,
            "message_id": m.message_id,
            "thread_id": m.thread_id,
            "subject": m.subject,
            "sender": m.sender,
            "recipient": m.recipient,
            "body": m.decrypted_body if not m.content_expired else "[CONTENT EXPIRED]",
            "received_at": m.received_at.isoformat() if m.received_at else None,
            "summary": m.summary,
            "needs_reply": m.needs_reply,
            "extracted_tasks": m.extracted_tasks,
            "extracted_dates": m.extracted_dates,
            "extracted_people": m.extracted_people,
            "extracted_decisions": m.extracted_decisions,
            "draft_reply": m.draft_reply,
            "status": m.status,
            "content_expired": m.content_expired,
            "source_deleted": m.source_deleted,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    # Tasks
    tasks = db.query(Task).all()
    export_data["tasks"] = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "task_type": t.task_type,
            "priority": t.priority,
            "status": t.status,
            "source_snippet": t.source_snippet,
            "confidence_score": t.confidence_score,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasks
    ]

    # Scheduling suggestions
    suggestions = db.query(SchedulingSuggestion).all()
    export_data["scheduling_suggestions"] = [
        {
            "id": s.id,
            "participants": s.participants,
            "suggested_slots": s.suggested_slots,
            "meeting_type": s.meeting_type,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in suggestions
    ]

    # Calendar events
    events = db.query(CalendarEvent).all()
    export_data["calendar_events"] = [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "start_time": e.start_time.isoformat() if e.start_time else None,
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "participants": e.participants,
            "status": e.status,
        }
        for e in events
    ]

    # Memory data
    export_data["principal_memory"] = [
        {"key": p.key, "value": p.value, "context_type": p.context_type}
        for p in db.query(PrincipalMemory).all()
    ]

    export_data["decision_patterns"] = [
        {
            "pattern_key": d.pattern_key,
            "pattern_type": d.pattern_type,
            "action": d.action,
            "occurrences": d.occurrences,
            "status": d.status,
        }
        for d in db.query(DecisionPattern).all()
    ]

    export_data["contact_contexts"] = [
        {
            "contact_email": c.contact_email,
            "contact_name": c.contact_name,
            "category": c.category,
            "notes": c.notes,
            "contact_metadata": c.contact_metadata,
        }
        for c in db.query(ContactContext).all()
    ]

    # Agent activity logs
    export_data["agent_activity_logs"] = [
        {
            "id": a.id,
            "action_type": a.action_type,
            "action_description": a.action_description,
            "confidence": a.confidence,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in db.query(AgentActivityLog).all()
    ]

    # Settings
    settings = db.query(UserSettings).first()
    if settings:
        export_data["settings"] = {
            "user_email": settings.user_email,
            "auto_approve_tasks": settings.auto_approve_tasks,
            "task_detection_instructions": settings.task_detection_instructions,
            "reminder_preferences": settings.reminder_preferences,
            "calendar_settings": {
                "default_meeting_duration": settings.default_meeting_duration,
                "working_hours_start": settings.working_hours_start,
                "working_hours_end": settings.working_hours_end,
                "default_timezone": settings.default_timezone,
            }
        }

    # Gmail account info (no tokens)
    account = db.query(GmailAccount).first()
    if account:
        export_data["gmail_account"] = {
            "email": account.email,
            "last_sync": account.last_sync.isoformat() if account.last_sync else None,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        }

    return export_data


@app.delete("/user/delete")
def delete_user_data(
    confirm: bool = False,
    db: Session = Depends(get_db)
):
    """
    GDPR Right to Erasure - Complete data deletion.

    Requires confirm=true query parameter as safety check.
    This deletes ALL user data including UserSettings.

    Use /auth/gmail/revoke to delete data while keeping settings.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete all data. This action is irreversible."
        )

    from .models import (
        Task, TaskReminder, SchedulingSuggestion,
        CalendarEvent, AgentActivityLog,
        PrincipalMemory, DecisionPattern, ContactContext
    )

    try:
        deletion_summary = {}

        # Delete in order respecting foreign keys
        deletion_summary["task_reminders"] = db.query(TaskReminder).delete()
        deletion_summary["tasks"] = db.query(Task).delete()
        deletion_summary["scheduling_suggestions"] = db.query(SchedulingSuggestion).delete()
        deletion_summary["calendar_events"] = db.query(CalendarEvent).delete()
        deletion_summary["agent_logs"] = db.query(AgentActivityLog).delete()
        deletion_summary["messages"] = db.query(Message).delete()
        deletion_summary["principal_memory"] = db.query(PrincipalMemory).delete()
        deletion_summary["decision_patterns"] = db.query(DecisionPattern).delete()
        deletion_summary["contact_contexts"] = db.query(ContactContext).delete()
        deletion_summary["queue_tasks"] = db.query(TaskQueue).delete()
        deletion_summary["gmail_accounts"] = db.query(GmailAccount).delete()
        deletion_summary["user_settings"] = db.query(UserSettings).delete()  # Includes settings

        db.commit()

        return {
            "success": True,
            "message": "All user data has been permanently deleted.",
            "deleted": deletion_summary
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete data: {str(e)}")
