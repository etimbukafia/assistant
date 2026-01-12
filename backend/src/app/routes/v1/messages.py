from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.gmail_integration import GmailClient, get_gmail_client, encrypt_body
from app.models import Message, GmailAccount, Task, ThreadState, SchedulingSuggestion
from app.schemas import (
    SyncResponse, MessagesListResponse, MessageResponse, 
    DraftReplyRequest, DraftReplyResponse
)
from app.worker import handle_process_email_batch
from app.queue import queue_service
from core.events import emit_event
from app.ai_processor import AIProcessor
from app.thread_state_service import ThreadStateService

router = APIRouter(prefix="/messages", tags=["Messages"])

# Global AI processor (stateless)
ai_processor = AIProcessor()

@router.post("/sync", response_model=SyncResponse)
async def sync_messages(
    background_tasks: BackgroundTasks,
    max_results: int = 3,
    query: str = "",
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
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

    try:
        # Fetch messages from Gmail
        messages = gmail_client.get_messages(max_results=max_results, query=query)

        synced_count = 0
        message_ids = []

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
                user_id=user.user_id,
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
                    payload={"message_id": msg_id, "user_id": user.user_id},
                    user_id=user.user_id,
                    db=db
                )

            # Trigger immediate batch processing
            await queue_service.process_batch_now(
                user_id=user.user_id,
                task_type="process_email",
                handler=handle_process_email_batch,
                db=db
            )

            # Emit events for other handlers (attachments, task extraction, etc.)
            for msg_id in message_ids:
                emit_event(
                    event_name="message_received",
                    payload={"message_id": msg_id, "user_id": user.user_id},
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


@router.post("/sync/deletions")
def sync_deletions(
    db: Session = Depends(get_db_for_user),
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


@router.post("/sync/sent")
def sync_sent_messages(
    db: Session = Depends(get_db_for_user),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    Sync sent messages from Gmail to update ThreadState.needs_reply.
    
    Rule: "Any outbound message from the user clears ThreadState.needs_reply."
    
    This is deterministic (no LLM) - if sender is user, clear needs_reply.
    """
    
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


@router.get("/", response_model=MessagesListResponse)
def get_messages(
    skip: int = 0,
    limit: int = 3,
    needs_reply: bool = None,
    db: Session = Depends(get_db_for_user)
):
    """Get all messages with optional filtering and their associated tasks.

    RLS automatically filters to current user's messages.
    """
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

        messages = [MessageResponse(**msg_dict) for msg_dict in message_dicts]

    return MessagesListResponse(messages=messages, total=total)


@router.get("/new")
def get_new_messages(
    since: datetime,
    db: Session = Depends(get_db_for_user)
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
    
    messages_response = [MessageResponse(**msg_dict) for msg_dict in message_dicts]
    
    return {"messages": messages_response, "count": len(messages_response)}


@router.get("/{message_id}", response_model=MessageResponse)
def get_message(message_id: int, db: Session = Depends(get_db_for_user)):
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

    return MessageResponse(**msg_dict)

@router.post("/{message_id}/draft-reply", response_model=DraftReplyResponse)
def draft_reply(
    message_id: int,
    request: DraftReplyRequest = None,
    db: Session = Depends(get_db_for_user)
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

@router.post("/{message_id}/reprocess")
def reprocess_message(message_id: int, db: Session = Depends(get_db_for_user)):
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
    
    # Check for scheduling intent to upgrade UI
    if ai_results.get("scheduling_intent"):
        message.scheduling_intent = True
        message.scheduling_intent_type = ai_results.get("scheduling_intent_type")
        message.scheduling_intent_confidence = ai_results.get("scheduling_intent_confidence")

    db.commit()

    return {"message": "Message reprocessed successfully"}


@router.patch("/{message_id}/status")
def update_message_status(
    message_id: int,
    status: str,
    db: Session = Depends(get_db_for_user)
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


@router.post("/{message_id}/done")
def mark_message_done(message_id: int, db: Session = Depends(get_db_for_user)):
    """Mark a message as done"""
    from app.pattern_tracker import track_message_action

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = "done"
    db.commit()

    # Track pattern for learning (especially if marked done without replying)
    track_message_action(db, "mark_done", message)

    return {"message": "Message marked as done", "id": message_id}


@router.post("/{message_id}/archive")
def archive_message(message_id: int, db: Session = Depends(get_db_for_user)):
    """Archive a message"""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = "archived"
    db.commit()

    return {"message": "Message archived", "id": message_id}


@router.delete("/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db_for_user)):
    """Permanently delete a message and all related data"""

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
