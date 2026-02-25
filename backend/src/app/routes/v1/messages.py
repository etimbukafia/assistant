import logging
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.security.auth import get_current_user, get_db, get_db_for_user, AuthenticatedUser, require_active_subscription
from app.security.encryption import encrypt_body
from app.integrations.gmail import GmailClient, get_gmail_client
from app.integrations.outlook import OutlookClient
from app.data.models import Message, GmailAccount, OutlookAccount, Task, ThreadState, SchedulingSuggestion, TaskQueue, UserSettings
from app.services.email_filter import EmailFilterService, FilterAction
from app.data.schemas import (
    SyncResponse, MessagesListResponse, MessageResponse,
    DraftReplyRequest, DraftReplyResponse,
    SendReplyRequest, SendReplyResponse,
    ThreadDetailResponse, ThreadStateResponse, ThreadMessageResponse,
    TaskListItem, SchedulingSuggestionResponse
)
from app.jobs.worker import handle_process_email_batch
from app.jobs.queue import queue_service
from core.events import emit_event
from app.processors.ai import AIProcessor
from app.services.thread_state import ThreadStateService
from core.cache import thread_cache
from app.services.entity_cache_coordinator import EntityCacheCoordinator

router = APIRouter(prefix="/messages", tags=["Messages"])
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

# Global AI processor (stateless)
ai_processor = AIProcessor()

@router.post("/sync", response_model=SyncResponse)
async def sync_messages(
    background_tasks: BackgroundTasks,
    max_results: int = 3,
    query: str = "",
    user: AuthenticatedUser = Depends(require_active_subscription),
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

        # Initialize filter service
        filter_service = EmailFilterService(db=db, user_id=user.user_id)

        synced_count = 0
        filtered_count = 0
        message_ids = []  # Messages to process with AI

        for msg_data in messages:
            # Check if message already exists
            existing = db.query(Message).filter(
                Message.message_id == msg_data['message_id']
            ).first()

            if existing:
                continue

            # Apply email filters
            gmail_labels = msg_data.get('gmail_labels', [])
            headers = msg_data.get('headers', {})
            body_preview = msg_data.get('body', '')[:200] if msg_data.get('body') else None
            filter_result = filter_service.apply_filters(
                gmail_labels=gmail_labels,
                sender_email=msg_data['sender'],
                subject=msg_data['subject'],
                headers=headers,
                body_preview=body_preview,
                thread_id=msg_data.get('thread_id'),
            )

            # Skip entirely if filter says so
            if filter_result.action == FilterAction.SKIP:
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
                processed=filter_result.action == FilterAction.METADATA_ONLY,  # Mark as processed if skipping AI
                has_attachments=bool(attachments),
                attachments=attachments,
            )

            db.add(message)
            db.flush()
            synced_count += 1

            # Only queue for AI processing if filter allows
            if filter_result.action == FilterAction.PROCESS:
                message_ids.append(message.id)
            else:
                filtered_count += 1

        # Store history ID for deletion tracking - Scoped to user
        account = db.query(GmailAccount).filter(GmailAccount.user_id == user.user_id).first()
        # Fallback: Try linking by email if not yet linked
        if not account:
            account = db.query(GmailAccount).filter(GmailAccount.email == user.email).first()
            if account and not account.user_id:
                account.user_id = user.user_id
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
            processed_count=len(message_ids),
            message=f"Synced {synced_count} messages ({len(message_ids)} processed, {filtered_count} filtered)."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync/deletions")
def sync_deletions(
    db: Session = Depends(get_db_for_user),
    user: AuthenticatedUser = Depends(require_active_subscription),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    Sync Gmail-side deletions to mark messages as source_deleted.

    This uses the Gmail History API to detect messages that were deleted
    from Gmail after being synced to our system.
    """
    # Get account with history ID
    account = db.query(GmailAccount).filter(GmailAccount.user_id == user.user_id).first()
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
    user: AuthenticatedUser = Depends(require_active_subscription),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    Sync sent messages from Gmail to update ThreadState.needs_reply.
    
    Rule: "Any outbound message from the user clears ThreadState.needs_reply."
    
    This is deterministic (no LLM) - if sender is user, clear needs_reply.
    """
    
    # Get account info
    account = db.query(GmailAccount).filter(GmailAccount.user_id == user.user_id).first()
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
    for thread_id in thread_ids_updated:
        cache_coordinator.invalidate_thread(_tenant_id(), user.user_id, thread_id)
    if thread_ids_updated:
        cache_coordinator.prewarm_action_chips(
            db=db,
            tenant_id=_tenant_id(),
            user_id=user.user_id,
        )

    # Update contact reply rates for threads where user replied
    # This powers Layer 3 relationship-based filtering
    if thread_ids_updated:
        from app.services.contact_stats import update_contact_on_reply
        for thread_id in thread_ids_updated:
            try:
                update_contact_on_reply(db, user.user_id, thread_id)
            except Exception as e:
                # Non-critical - log and continue
                import logging
                logging.warning(f"Failed to update contact stats for thread {thread_id}: {e}")

    return {
        "sent_messages_checked": len(sent_messages),
        "threads_updated": updated_count,
        "thread_ids": thread_ids_updated[:10],  # First 10 for debugging
        "message": f"Cleared needs_reply on {updated_count} threads where user replied"
    }


@router.get("/", response_model=MessagesListResponse)
def get_messages(
    limit: int = 3,
    offset: int = 0,
    needs_reply: bool = None,
    status: str = "inbox",
    db: Session = Depends(get_db_for_user)
):
    """Get all messages with optional filtering and their associated tasks.

    RLS automatically filters to current user's messages.
    Defaults to status=inbox to exclude archived/done messages including manual task placeholders.
    """
    query = db.query(Message).filter(Message.status == status)

    if needs_reply is not None:
        query = query.filter(Message.needs_reply == needs_reply)

    # Get total count for metadata
    total = query.count()

    # Get paginated messages
    messages = query.order_by(Message.received_at.desc()).offset(offset).limit(limit).all()

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
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_for_user)
):
    """
    Get messages received since timestamp.

    Used for polling - frontend checks for new items periodically.
    Only returns inbox messages (not archived/synced).
    """
    query = db.query(Message).filter(
        Message.received_at > since,
        Message.status == "inbox"
    ).order_by(Message.received_at.desc())

    total = query.count()
    messages = query.offset(offset).limit(limit).all()
    
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

    return {"messages": messages_response, "total": total, "limit": limit, "offset": offset}


@router.get("/processing-status")
def get_processing_status(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get count of emails currently being processed for this user."""
    count = db.query(TaskQueue).filter(
        TaskQueue.task_type == "process_email",
        TaskQueue.user_id == user.user_id,
        TaskQueue.status.in_(["pending", "in_progress"]),
    ).count()

    return {"processing_count": count}


@router.get("/thread/{thread_id}", response_model=ThreadDetailResponse)
def get_thread_detail(
    thread_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """
    Get full thread detail for the Thread Intelligence View.

    Returns thread state (summary, action points, decisions, participants),
    all messages in chronological order, linked tasks, and scheduling suggestions.

    Cached per user+thread for 5 minutes. Message bodies excluded from cache
    (no decrypted PII in memory). The intelligence view uses summary, action_points,
    decisions, participants, tasks — not the raw body.
    """

    def build():
        thread_state = db.query(ThreadState).filter(
            ThreadState.thread_id == thread_id
        ).first()

        messages = db.query(Message).filter(
            Message.thread_id == thread_id
        ).order_by(Message.received_at.asc()).all()

        if not messages:
            raise HTTPException(status_code=404, detail="Thread not found")

        thread_messages = [
            ThreadMessageResponse(
                id=msg.id,
                sender=msg.sender,
                subject=msg.subject,
                body=msg.decrypted_body,
                summary=msg.summary,
                received_at=msg.received_at,
                status=msg.status or "inbox",
                scheduling_intent=msg.scheduling_intent or False,
                scheduling_intent_type=msg.scheduling_intent_type,
            )
            for msg in messages
        ]

        tasks = db.query(Task).filter(
            Task.thread_id == thread_id
        ).order_by(Task.created_at.desc()).all()

        suggestions = db.query(SchedulingSuggestion).filter(
            SchedulingSuggestion.thread_id == thread_id,
            SchedulingSuggestion.status == "pending"
        ).order_by(SchedulingSuggestion.created_at.desc()).all()

        response = ThreadDetailResponse(
            thread_state=ThreadStateResponse(
                summary=thread_state.summary if thread_state else None,
                open_tasks=thread_state.open_tasks if thread_state else [],
                decisions=thread_state.decisions if thread_state else [],
                participants=thread_state.participants if thread_state else [],
                action_points=thread_state.action_points if thread_state else [],
                needs_reply=thread_state.needs_reply if thread_state else False,
                message_count=thread_state.message_count if thread_state else len(messages),
                last_action=thread_state.last_action if thread_state else None,
                last_action_by=thread_state.last_action_by if thread_state else None,
            ),
            messages=thread_messages,
            tasks=[TaskListItem.model_validate(t) for t in tasks],
            scheduling_suggestions=[SchedulingSuggestionResponse.model_validate(s) for s in suggestions],
        )

        # Strip bodies before caching — no decrypted PII in memory
        result = response.model_dump()
        for msg in result["messages"]:
            msg["body"] = ""
        return result

    result = thread_cache.get_or_build(user.user_id, thread_id, build)

    # Re-attach bodies from DB after cache lookup — bodies are never cached
    messages = db.query(Message).filter(
        Message.thread_id == thread_id
    ).order_by(Message.received_at.asc()).all()
    body_map = {msg.id: msg.decrypted_body for msg in messages}
    for msg in result["messages"]:
        msg["body"] = body_map.get(msg["id"], "")

    return result


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

    # Determine which module to use based on intent
    if message.scheduling_intent:
        from app.agents.modules.scheduling import SchedulingModule
        
        
        from core.llm.config import LLMConfig

        # Instantiate module with chat/drafting model
        scheduling_module = SchedulingModule(llm_config=LLMConfig.for_chat())
        
        # Use message intent type or default
        intent_type = message.scheduling_intent_type or "availability_request"
        
        # Fetch slots for context
        availability_context = scheduling_module.get_availability_context_string(
            db=db, 
            user_id=message.user_id
        )
        
        
        # Re-extract details to get full context for the draft
        details = scheduling_module.extract_scheduling_details(
            message_data['body'], 
            message_data['subject'], 
            message_data['sender']
        )
        
        # Let's re-use the availability context string logic but we need detailed slots for 'generate_draft_reply'.
        # For now, let's use a simplified flow or the detailed one.
        
        # Fetch actual availability data
        from datetime import datetime, timezone, timedelta
        start = datetime.now(timezone.utc)
        settings = db.query(GmailAccount).filter(GmailAccount.user_id == message.user_id).first() # settings actually in UserSettings
        # Skipping elaborate fetching here to keep it simple, or relying on what we can.
        
        # Let's call fetch_availability
        av_result = scheduling_module.fetch_availability(
            start_date=start.isoformat(),
            end_date=(start + timedelta(days=14)).isoformat(),
            db=db,
            user_id=message.user_id
        )
        suggested_slots = av_result.get("suggested_slots", [])
        tz = av_result.get("timezone", "UTC")
        
        draft = scheduling_module.generate_draft_reply(
            intent_type=intent_type,
            suggested_slots=suggested_slots,
            meeting_type=details.get("meeting_type", "meeting"),
            timezone_str=tz,
            sender_name=message.sender.split('<')[0].strip('" '),
            meeting_with=details.get("meeting_with", ""),
            mentioned_times=details.get("mentioned_times", []),
            sender_email=message.sender,
            db=db,
            user_id=message.user_id
        )

    else:
        from app.agents.modules.communication import CommunicationModule
        
        from core.llm.config import LLMConfig

        comm_module = CommunicationModule(llm_config=LLMConfig.for_chat())
        
        # Use generate_reply
        result = comm_module.generate_reply(
            message_body=message_data['body'],
            message_subject=message_data['subject'],
            sender_email=message_data['sender'],
            intent="reply",
            tone="Professional and helpful",
            additional_context=context,
            db=db,
            user_id=message.user_id
        )
        draft = result.get("draft", "")

    # Save draft to database
    message.draft_reply = draft
    db.commit()

    return DraftReplyResponse(draft=draft)


@router.post("/{message_id}/send-reply", response_model=SendReplyResponse)
def send_reply(
    message_id: int,
    request: SendReplyRequest,
    db: Session = Depends(get_db_for_user)
):
    """
    Send a reply to a message via Gmail.

    Uses the original message's thread_id and gmail_id for proper threading.
    After sending, marks the thread as no longer needing a reply.
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    try:
        if message.provider == "microsoft":
            outlook_account = db.query(OutlookAccount).filter(
                OutlookAccount.user_id == message.user_id
            ).first()
            if not outlook_account:
                return SendReplyResponse(sent=False, error="No Microsoft account connected")
            outlook_client = OutlookClient(db=db, user_id=message.user_id)
            if not outlook_client.load_credentials(email=outlook_account.email):
                return SendReplyResponse(sent=False, error="Microsoft credentials invalid")
            # Use external_message_id for reply
            external_id = message.external_message_id or message.message_id.replace("ms:", "")
            outlook_client.send_reply(external_id, request.body)
            result = {"id": external_id, "threadId": message.thread_id}
        else:
            # Get Gmail client for this user
            gmail_account = db.query(GmailAccount).filter(
                GmailAccount.user_id == message.user_id
            ).first()
            if not gmail_account:
                return SendReplyResponse(sent=False, error="No Gmail account connected")

            gmail_client = GmailClient(gmail_account)

            subject = request.subject or f"Re: {message.subject}"

            result = gmail_client.send_message(
                to=request.to,
                subject=subject,
                body=request.body,
                in_reply_to=message.gmail_id,
                thread_id=message.thread_id,
            )

        # Update thread state: no longer needs reply
        thread_state = db.query(ThreadState).filter(
            ThreadState.thread_id == message.thread_id,
            ThreadState.user_id == message.user_id,
        ).first()
        if thread_state:
            thread_state.needs_reply = False
            thread_state.last_outbound_at = datetime.now(timezone.utc)

        db.commit()

        _invalidate_thread_and_prewarm(db, message.user_id, message.thread_id)

        return SendReplyResponse(
            sent=True,
            message_id=result.get("id"),
            thread_id=result.get("threadId"),
        )

    except Exception as e:
        logger.error(f"Failed to send reply for message {message_id}: {e}")
        return SendReplyResponse(sent=False, error=str(e))


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

    # Fetch assistant name from user settings
    assistant_name = "Teeks"  # default
    if message.user_id:
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == message.user_id).first()
        if user_settings and user_settings.assistant_name:
            assistant_name = user_settings.assistant_name

    # Use state-based thread processing
    thread_state_service = ThreadStateService(db, assistant_name=assistant_name)
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

    _invalidate_thread_and_prewarm(db, message.user_id, message.thread_id)

    return {"message": "Message reprocessed successfully"}


@router.patch("/{message_id}/status")
def update_message_status(
    message_id: int,
    status: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
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

    _invalidate_thread_and_prewarm(db, user.user_id, message.thread_id)

    return {"message": f"Message marked as {status}", "id": message_id, "status": status}


@router.post("/{message_id}/done")
def mark_message_done(
    message_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Mark a message as done"""
    from app.intelligence.pattern_tracker import track_message_action

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = "done"
    db.commit()

    _invalidate_thread_and_prewarm(db, user.user_id, message.thread_id)

    # Track pattern for learning (especially if marked done without replying)
    track_message_action(db, "mark_done", message)

    return {"message": "Message marked as done", "id": message_id}


@router.post("/{message_id}/archive")
def archive_message(
    message_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Archive a message"""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.status = "archived"
    db.commit()

    _invalidate_thread_and_prewarm(db, user.user_id, message.thread_id)

    return {"message": "Message archived", "id": message_id}


@router.delete("/{message_id}")
def delete_message(
    message_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Permanently delete a message and all related data"""

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    thread_id = message.thread_id

    # Delete related tasks first (foreign key constraint)
    db.query(Task).filter(Task.message_id == message_id).delete(synchronize_session='fetch')

    # Delete related scheduling suggestions
    db.query(SchedulingSuggestion).filter(SchedulingSuggestion.message_id == message_id).delete(synchronize_session='fetch')

    # Flush to ensure deletes are sent to DB before message delete
    db.flush()

    # Now delete the message
    db.delete(message)
    db.commit()

    _invalidate_thread_and_prewarm(db, user.user_id, thread_id)

    return {"message": "Message deleted", "id": message_id}


# ========================================
# Initial Sync Endpoint (moved from sync.py)
# ========================================

from app.jobs.queue import enqueue_task

@router.post("/gmail/sync/initial")
def trigger_initial_sync(
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user)
):
    """
    Trigger initial email backfill for today's emails.

    Fetches emails from midnight (user's timezone) to now, ensuring
    users see all relevant emails from the current day on first sync.

    Called when:
    - First Gmail connection after trial activation
    - Returning subscriber after lapsed subscription
    """
    logger.info(f"Initial sync request for user_id={user.user_id}")
    gmail_account = db.query(GmailAccount).filter(
        GmailAccount.user_id == user.user_id
    ).first()

    if not gmail_account:
        logger.error(f"No GmailAccount found for user_id={user.user_id} — connectGmail may have failed")
        raise HTTPException(404, "No Gmail account connected")

    logger.info(f"GmailAccount found: email={gmail_account.email}, initial_sync_completed={gmail_account.initial_sync_completed}")
    if gmail_account.initial_sync_completed:
        # Already synced, use incremental
        return {"status": "already_completed", "sync_type": "incremental"}

    # Get user's timezone for calculating "today"
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.user_id
    ).first()
    user_timezone = user_settings.default_timezone if user_settings else "UTC"

    # Queue backfill job for today's emails (midnight to now in user's timezone)
    enqueue_task("email_backfill", {
        "user_id": user.user_id,
        "sync_mode": "today",  # New mode: fetch from midnight in user's timezone
        "user_timezone": user_timezone,
        "gmail_account_id": gmail_account.id
    })

    return {"status": "queued", "sync_type": "initial", "mode": "today", "timezone": user_timezone}


@router.post("/outlook/sync/initial")
def trigger_outlook_initial_sync(
    user: AuthenticatedUser = Depends(require_active_subscription),
    db: Session = Depends(get_db_for_user)
):
    """
    Trigger initial Outlook email backfill for today's emails.
    """
    logger.info(f"Outlook initial sync request for user_id={user.user_id}")
    outlook_account = db.query(OutlookAccount).filter(
        OutlookAccount.user_id == user.user_id
    ).first()

    if not outlook_account:
        logger.error(f"No OutlookAccount found for user_id={user.user_id}")
        raise HTTPException(404, "No Microsoft account connected")

    if outlook_account.initial_sync_completed:
        return {"status": "already_completed", "sync_type": "incremental"}

    # Use user's timezone for "today"
    user_settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.user_id
    ).first()
    user_timezone = user_settings.default_timezone if user_settings else "UTC"

    enqueue_task("outlook_email_backfill", {
        "user_id": user.user_id,
        "sync_mode": "today",
        "user_timezone": user_timezone,
        "outlook_account_id": outlook_account.id
    })

    return {"status": "queued", "sync_type": "initial", "mode": "today", "timezone": user_timezone}
