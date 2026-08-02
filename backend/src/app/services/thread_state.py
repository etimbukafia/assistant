"""
Thread State Service

Manages thread state for state-based email processing.
Threads are state machines. Messages are state updates.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from email.utils import getaddresses, parseaddr

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_

from app.data.models import ThreadState, Task, Message
from app.processors.ai import AIProcessor
from app.services.entity_cache_coordinator import EntityCacheCoordinator

logger = logging.getLogger(__name__)
cache_coordinator = EntityCacheCoordinator()
_TENANT_ID = "default"


class ThreadStateService:
    """
    Service for managing thread state.

    Core principle: Each new message updates the thread state incrementally.
    No full thread transcript re-analysis.
    """

    def __init__(self, db: Session, ai_processor: Optional[AIProcessor] = None, assistant_name: str = "Teeks", task_detection_instructions: str = ""):
        self.db = db
        self.task_detection_instructions = task_detection_instructions
        self.ai_processor = ai_processor or AIProcessor(assistant_name=assistant_name)

    def get_or_create_thread_state(self, thread_id: str, user_id: Optional[str] = None) -> ThreadState:
        """
        Get existing thread state or create a new one.

        Uses SELECT FOR UPDATE to prevent race conditions when
        multiple messages from the same thread are processed concurrently.

        Args:
            thread_id: Gmail thread ID

        Returns:
            ThreadState object

        Raises:
            RuntimeError: If thread state cannot be created or fetched after retry
        """
        from sqlalchemy.exc import IntegrityError

        # Try to get existing with row lock
        base_query = self.db.query(ThreadState).filter(ThreadState.thread_id == thread_id)
        if user_id:
            base_query = base_query.filter(
                or_(ThreadState.user_id == user_id, ThreadState.user_id.is_(None))
            )
        thread_state = base_query.with_for_update().first()

        if not thread_state:
            # Create new - handle race condition with upsert pattern
            try:
                thread_state = ThreadState(
                    thread_id=thread_id,
                    user_id=user_id,
                    open_tasks=[],
                    decisions=[],
                    participants=[],
                    message_count=0
                )
                self.db.add(thread_state)
                self.db.flush()  # Get ID without committing
            except IntegrityError:
                # Another process created it - rollback and fetch
                self.db.rollback()
                retry_query = self.db.query(ThreadState).filter(ThreadState.thread_id == thread_id)
                if user_id:
                    retry_query = retry_query.filter(
                        or_(ThreadState.user_id == user_id, ThreadState.user_id.is_(None))
                    )
                thread_state = retry_query.with_for_update().first()

                # Defensive check - should never happen but prevents silent failures
                if not thread_state:
                    raise RuntimeError(
                        f"Failed to get or create ThreadState for thread_id={thread_id}. "
                        "IntegrityError occurred but subsequent fetch returned None."
                    )

        if thread_state and user_id and not thread_state.user_id:
            thread_state.user_id = user_id
        if thread_state and user_id and thread_state.user_id not in (None, user_id):
            raise RuntimeError(
                f"ThreadState ownership mismatch for thread_id={thread_id}. "
                f"existing_user_id={thread_state.user_id} requested_user_id={user_id}"
            )

        return thread_state

    def process_message(
        self,
        message: Message,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a new message using thread state approach.

        This is the main entry point for state-based processing:
        1. Get or create thread state
        2. If first message: initialize state
        3. If subsequent: update state incrementally
        4. Apply task updates
        5. Return results

        Args:
            message: Message database object
            message_data: Dict with subject, body, sender

        Returns:
            Processing results with summary, needs_reply, tasks, etc.
        """
        thread_id = message.thread_id
        thread_state = None
        ai_result = {}

        try:
            # Get or create thread state
            thread_state = self.get_or_create_thread_state(thread_id, user_id=message.user_id)
            is_first_message = thread_state.message_count == 0

            if is_first_message:
                # Initialize thread state from first message
                ai_result = self.ai_processor.init_thread_state(message_data)
                self._apply_init_result(thread_state, message, ai_result)
            else:
                # Update thread state incrementally
                current_state = self._thread_state_to_dict(thread_state)
                ai_result = self.ai_processor.update_thread_state(current_state, message_data)
                self._apply_update_result(thread_state, message, ai_result)

            # Record token usage for this user
            if message.user_id:
                self.ai_processor.record_and_reset_tokens(
                    db=self.db,
                    user_id=message.user_id,
                    operation="email_processing"
                )

            self._sync_message_metadata(thread_state, message, is_first_message=is_first_message)

            self.db.commit()

            if message.user_id:
                cache_coordinator.invalidate_thread_related_contact(
                    db=self.db,
                    tenant_id=_TENANT_ID,
                    user_id=message.user_id,
                    thread_id=thread_id,
                )

        except Exception as e:
            # Rollback to release any locks and prevent stuck transactions
            self.db.rollback()
            logger.error(f"Error processing message {message.id}: {e}")
            raise

        # Extract scheduling intent from main AI result (merged into prompts)
        scheduling_intent = ai_result.get("scheduling_intent", False)
        scheduling_intent_type = ai_result.get("scheduling_intent_type", "none") if scheduling_intent else None
        scheduling_intent_confidence = ai_result.get("scheduling_intent_confidence", 0.0) if scheduling_intent else None

        # Return results in the expected format
        return {
            "summary": thread_state.summary,
            "needs_reply": thread_state.needs_reply,
            "extracted_tasks": ai_result.get("tasks", ai_result.get("new_tasks", [])),
            "extracted_dates": [],  # Thread state approach focuses on tasks
            "extracted_people": [p.get("email") for p in (thread_state.participants or [])],
            "extracted_decisions": thread_state.decisions or [],
            "scheduling_intent": scheduling_intent,
            "scheduling_intent_type": scheduling_intent_type,
            "scheduling_intent_confidence": scheduling_intent_confidence
        }

    def _thread_state_to_dict(self, thread_state: ThreadState) -> Dict[str, Any]:
        """Convert ThreadState to dict for AI processing."""
        return {
            "summary": thread_state.summary,
            "open_tasks": thread_state.open_tasks or [],
            "decisions": thread_state.decisions or [],
            "participants": thread_state.participants or [],
            "action_points": thread_state.action_points or [],
            "last_action": thread_state.last_action,
            "message_count": thread_state.message_count
        }

    def _sync_message_metadata(
        self,
        thread_state: ThreadState,
        message: Message,
        *,
        is_first_message: bool,
    ) -> None:
        """Keep thread state metadata aligned across single and batch processing."""
        thread_state.user_id = thread_state.user_id or message.user_id
        thread_state.message_count = (thread_state.message_count or 0) + 1
        thread_state.last_message_id = message.id
        if is_first_message or thread_state.first_message_id is None:
            thread_state.first_message_id = message.id
            thread_state.subject = thread_state.subject or message.subject
        if message.contact_id and thread_state.contact_id is None:
            thread_state.contact_id = message.contact_id

        self._add_participant(thread_state, message.sender, "sender", contact_id=message.contact_id)
        for recipient in self._iter_recipient_addresses(message.recipient):
            self._add_participant(thread_state, recipient, "recipient")

    @staticmethod
    def _iter_recipient_addresses(recipient_value: Optional[str]) -> List[str]:
        raw = (recipient_value or "").strip()
        if not raw:
            return []

        values: list[str] = []
        for display_name, email in getaddresses([raw]):
            candidate = (email or "").strip()
            if not candidate:
                continue
            formatted = f"{display_name} <{candidate}>" if display_name else candidate
            if formatted not in values:
                values.append(formatted)
        return values

    def _apply_init_result(
        self,
        thread_state: ThreadState,
        message: Message,
        ai_result: Dict[str, Any]
    ):
        """Apply initialization result to thread state."""
        thread_state.summary = ai_result.get("summary", message.subject)
        thread_state.last_action = ai_result.get("last_action", "New conversation started")
        thread_state.last_action_by = ai_result.get("last_action_by", message.sender)
        thread_state.last_action_at = datetime.now(timezone.utc)
        thread_state.needs_reply = ai_result.get("needs_reply", True)
        thread_state.action_points = ai_result.get("action_points", [])

        # Create tasks from init result
        tasks = ai_result.get("tasks", [])
        for task_data in tasks:
            self._create_thread_task(thread_state, message, task_data)

        # Store decisions
        decisions = ai_result.get("decisions", [])
        thread_state.decisions = [
            {
                "decision": d.get("decision"),
                "made_by": d.get("made_by", message.sender),
                "made_at": datetime.now(timezone.utc).isoformat(),
                "source_message_id": message.id
            }
            for d in decisions
        ]

    def _apply_update_result(
        self,
        thread_state: ThreadState,
        message: Message,
        ai_result: Dict[str, Any]
    ):
        """Apply update result to thread state."""
        # Update summary if changed
        if ai_result.get("summary_update"):
            thread_state.summary = ai_result["summary_update"]

        # Update last action
        thread_state.last_action = ai_result.get("last_action", "New message received")
        thread_state.last_action_by = ai_result.get("last_action_by", message.sender)
        thread_state.last_action_at = datetime.now(timezone.utc)
        thread_state.needs_reply = ai_result.get("needs_reply", True)

        # Update action points (full replacement from AI)
        if "action_points" in ai_result:
            thread_state.action_points = ai_result["action_points"]

        # Process task updates (mark completed/superseded)
        task_updates = ai_result.get("task_updates", [])
        self._apply_task_updates(thread_state, task_updates)

        # Create new tasks
        new_tasks = ai_result.get("new_tasks", [])
        for task_data in new_tasks:
            self._create_thread_task(thread_state, message, task_data)

        # Add new decisions
        new_decisions = ai_result.get("new_decisions", [])
        if new_decisions:
            current_decisions = thread_state.decisions or []
            for d in new_decisions:
                current_decisions.append({
                    "decision": d.get("decision"),
                    "made_by": d.get("made_by", message.sender),
                    "made_at": datetime.now(timezone.utc).isoformat(),
                    "source_message_id": message.id
                })
            thread_state.decisions = current_decisions

    def _apply_task_updates(
        self,
        thread_state: ThreadState,
        task_updates: List[Dict[str, Any]]
    ):
        """Apply task status updates (completed/superseded)."""
        if not task_updates:
            return

        open_tasks = thread_state.open_tasks or []

        for update in task_updates:
            existing_title = update.get("existing_task_title", "").lower()
            new_status = update.get("new_status")

            if not existing_title or not new_status:
                continue

            # Find matching task in thread state
            for task in open_tasks:
                if task.get("title", "").lower() == existing_title:
                    task["status"] = new_status
                    logger.info(f"Updated thread task '{existing_title}' to status '{new_status}'")
                    break

            # Also update in Task table
            thread_tasks = self.db.query(Task).filter(
                Task.thread_id == thread_state.thread_id,
                Task.status.in_(["pending_approval", "approved"])
            ).all()

            for db_task in thread_tasks:
                if db_task.title.lower() == existing_title:
                    if new_status == "completed":
                        db_task.status = "completed"
                        db_task.completed_at = datetime.now(timezone.utc)
                    elif new_status == "superseded":
                        db_task.status = "superseded"
                    logger.info(f"Updated Task #{db_task.id} to status '{new_status}'")

        thread_state.open_tasks = open_tasks
        flag_modified(thread_state, "open_tasks")

    def _create_thread_task(
        self,
        thread_state: ThreadState,
        message: Message,
        task_data: Dict[str, Any]
    ):
        """Create a task at thread level."""
        # Check for duplicate in thread
        existing_titles = {t.get("title", "").lower() for t in (thread_state.open_tasks or [])}
        new_title = task_data.get("title", "").lower()

        if new_title in existing_titles:
            logger.info(f"Skipping duplicate task '{task_data.get('title')}' in thread")
            return

        # Generate unique task ID for thread state tracking
        task_uuid = str(uuid.uuid4())[:8]

        # Add to thread state
        open_tasks = thread_state.open_tasks or []
        open_tasks.append({
            "id": task_uuid,
            "title": task_data.get("title"),
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_message_id": message.id
        })
        thread_state.open_tasks = open_tasks

        # Parse deadline from AI response (Smart Todo List)
        deadline = None
        deadline_source = None
        deadline_confidence = None
        deadline_data = task_data.get("deadline")

        if deadline_data and isinstance(deadline_data, dict):
            try:
                date_str = deadline_data.get("date")
                if date_str:
                    deadline = self._parse_deadline_date(date_str, message)
                    if deadline:
                        deadline_source = deadline_data.get("source", "inferred")
                        deadline_confidence = deadline_data.get("confidence", 0.7)
                        logger.info(f"Extracted deadline '{date_str}' ({deadline_source}) for task '{task_data.get('title')}'")
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse deadline for task: {e}")

        # Determine if urgency is AI-suggested (priority=urgent set by AI)
        priority = task_data.get("priority", "normal")
        urgency_suggested_by_ai = (priority == "urgent")

        # Create Task in database
        task = Task(
            thread_id=thread_state.thread_id,
            message_id=message.id,
            user_id=message.user_id,
            title=task_data.get("title"),
            description=task_data.get("description"),
            task_type=task_data.get("task_type", "other"),
            task_signal=task_data.get("task_signal", "explicit"),
            priority=priority,
            source_snippet=task_data.get("source_snippet"),
            status="pending_approval",
            # Deadline fields (Smart Todo List)
            deadline=deadline,
            deadline_source=deadline_source,
            deadline_confidence=deadline_confidence,
            deadline_user_confirmed=False,  # AI suggestions need user confirmation
            urgency_suggested_by_ai=urgency_suggested_by_ai
        )
        self.db.add(task)
        self.db.flush()  # Get task.id for event emission
        
        # Emit task_created event for reminder scheduling
        from app.jobs.queue import enqueue_task
        enqueue_task(
            task_type="emit_event",
            payload={
                "user_id": message.user_id,
                "event_name": "task_created",
                "event_payload": {
                    "task_id": task.id,
                    "user_id": message.user_id,
                    "message_id": message.id,
                    "source": "thread_state_service"
                }
            },
            db=self.db
        )

    def _parse_deadline_date(self, date_str: str, message: Message) -> Optional[datetime]:
        """Parse deadline dates with relative weekday support (e.g., 'by Friday')."""
        raw = " ".join(str(date_str or "").split()).strip()
        if not raw:
            return None

        # Try ISO first.
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            pass

        lowered = raw.lower()
        lowered = lowered.replace("by ", "").replace("on ", "").replace("before ", "")
        lowered = lowered.replace("next ", "").strip()

        anchor = message.received_at or message.created_at or datetime.now(timezone.utc)
        anchor = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)

        if lowered in {"today"}:
            return anchor.replace(hour=17, minute=0, second=0, microsecond=0)
        if lowered in {"tomorrow"}:
            return (anchor + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)

        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        if lowered in weekdays:
            target = weekdays[lowered]
            current = anchor.weekday()
            delta = (target - current) % 7
            if delta == 0:
                delta = 7  # always prefer future
            target_dt = anchor + timedelta(days=delta)
            return target_dt.replace(hour=17, minute=0, second=0, microsecond=0)

        return None
        
        logger.info(f"Created task '{task_data.get('title')}' (id={task.id}) for thread {thread_state.thread_id}")

    def _add_participant(
        self,
        thread_state: ThreadState,
        email: str,
        role: str = "participant",
        contact_id: Optional[int] = None,
    ):
        """Add a participant to thread if not already present."""
        if not email:
            return

        participants = thread_state.participants or []
        display_name, parsed_email = parseaddr(email or "")
        normalized_email = (parsed_email or email or "").strip().lower()
        if not normalized_email or "@" not in normalized_email:
            return
        existing_emails = {p.get("email", "").lower() for p in participants}

        if normalized_email not in existing_emails:
            participants.append({
                "email": normalized_email,
                "name": (display_name or normalized_email.split("@")[0]).strip(),  # Prefer header display name when available
                "role": role
            })
            if contact_id:
                participants[-1]["contact_id"] = int(contact_id)
            thread_state.participants = participants
            return

        # Update existing participant with contact link if missing.
        if contact_id:
            for participant in participants:
                if (participant.get("email", "").lower() == normalized_email) and (not participant.get("contact_id")):
                    participant["contact_id"] = int(contact_id)
                    thread_state.participants = participants
                    break

    def get_thread_summary(self, thread_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a summary of thread state for display.

        Args:
            thread_id: Gmail thread ID

        Returns:
            Dict with thread state summary or None if not found
        """
        query = self.db.query(ThreadState).filter(ThreadState.thread_id == thread_id)
        if user_id:
            query = query.filter(ThreadState.user_id == user_id)
        thread_state = query.first()

        if not thread_state:
            return None

        # Count open tasks
        open_task_count = len([
            t for t in (thread_state.open_tasks or [])
            if t.get("status") == "open"
        ])

        return {
            "thread_id": thread_state.thread_id,
            "subject": thread_state.subject,
            "summary": thread_state.summary,
            "message_count": thread_state.message_count,
            "open_task_count": open_task_count,
            "decision_count": len(thread_state.decisions or []),
            "participant_count": len(thread_state.participants or []),
            "needs_reply": thread_state.needs_reply,
            "last_action": thread_state.last_action,
            "last_action_by": thread_state.last_action_by,
            "updated_at": thread_state.updated_at.isoformat() if thread_state.updated_at else None
        }

    def process_messages_batch(
        self,
        messages: List[Message]
    ) -> List[Dict[str, Any]]:
        """
        Process multiple messages with batched LLM calls where possible.
        
        Groups messages by:
        - New threads: Batches init_thread_state calls (1 API call for N messages)
        - Existing threads: Processes sequentially per thread (state dependencies)
        
        Args:
            messages: List of Message objects to process
            
        Returns:
            List of processing results in same order as input
        """
        if not messages:
            return []
        
        # Separate new threads from existing
        new_thread_msgs = []  # (index, message, message_data)
        existing_thread_msgs = {}  # thread_id -> [(index, message, message_data)]
        threads_being_created = set()  # Track threads we'll create in this batch
        
        for i, message in enumerate(messages):
            message_data = {
                "subject": message.subject,
                "body": message.decrypted_body or message.body or "",
                "sender": message.sender,
                "custom_instructions": self.task_detection_instructions,
            }
            
            # Check if thread state exists OR if we're already creating it in this batch
            existing_state = self.db.query(ThreadState).filter(
                ThreadState.thread_id == message.thread_id,
                or_(ThreadState.user_id == message.user_id, ThreadState.user_id.is_(None)),
            ).first()
            
            if existing_state or message.thread_id in threads_being_created:
                # Treat as existing thread (process after init)
                if message.thread_id not in existing_thread_msgs:
                    existing_thread_msgs[message.thread_id] = []
                existing_thread_msgs[message.thread_id].append((i, message, message_data))
            else:
                # New thread - mark it and add first message to init batch
                threads_being_created.add(message.thread_id)
                new_thread_msgs.append((i, message, message_data))
        
        # Prepare results array
        results = [None] * len(messages)
        
        # Batch process new threads (single API call)
        if new_thread_msgs:
            logger.info(f"Batch processing {len(new_thread_msgs)} new threads")
            messages_data = [item[2] for item in new_thread_msgs]
            batch_results = self.ai_processor.init_thread_state_batch(messages_data)

            # Record token usage for the batch (use first message's user_id)
            first_user_id = new_thread_msgs[0][1].user_id if new_thread_msgs else None
            if first_user_id:
                self.ai_processor.record_and_reset_tokens(
                    db=self.db,
                    user_id=first_user_id,
                    operation="email_processing_batch"
                )

            # Apply results to each message
            for (idx, message, msg_data), ai_result in zip(new_thread_msgs, batch_results):
                try:
                    thread_state = self._create_thread_state(message.thread_id, user_id=message.user_id)
                    self._apply_init_result(thread_state, message, ai_result)
                    self._sync_message_metadata(thread_state, message, is_first_message=True)
                    self.db.commit()
                    if message.user_id:
                        cache_coordinator.invalidate_thread_related_contact(
                            db=self.db,
                            tenant_id=_TENANT_ID,
                            user_id=message.user_id,
                            thread_id=thread_state.thread_id,
                        )
                    
                    # Build result
                    scheduling_intent = ai_result.get("scheduling_intent", False)
                    scheduling_intent_type = ai_result.get("scheduling_intent_type", "none") if scheduling_intent else None
                    scheduling_intent_confidence = ai_result.get("scheduling_intent_confidence", 0.0) if scheduling_intent else None
                    
                    results[idx] = {
                        "summary": thread_state.summary,
                        "needs_reply": thread_state.needs_reply,
                        "extracted_tasks": ai_result.get("tasks", []),
                        "extracted_dates": [],
                        "extracted_people": [p.get("email") for p in (thread_state.participants or [])],
                        "extracted_decisions": thread_state.decisions or [],
                        "scheduling_intent": scheduling_intent,
                        "scheduling_intent_type": scheduling_intent_type,
                        "scheduling_intent_confidence": scheduling_intent_confidence
                    }
                except Exception as e:
                    logger.error(f"Failed to process new thread for message {message.id}: {e}")
                    self.db.rollback()
                    results[idx] = {"_error": True, "message_id": message.id, "error": str(e)}
        
        # Process existing threads - batch first messages, sequential for same-thread follow-ups
        if existing_thread_msgs:
            # Sort messages within each thread
            for thread_id in existing_thread_msgs:
                existing_thread_msgs[thread_id].sort(key=lambda x: x[1].received_at)
            
            # Collect first message from each thread for batching
            first_msgs = []  # [(thread_id, idx, message, msg_data, thread_state)]
            remaining_msgs = {}  # thread_id -> [(idx, message, msg_data)]
            
            for thread_id, thread_msgs in existing_thread_msgs.items():
                # Get current thread state
                thread_state = self.db.query(ThreadState).filter(
                    ThreadState.thread_id == thread_id,
                    or_(ThreadState.user_id == thread_msgs[0][1].user_id, ThreadState.user_id.is_(None)),
                ).first()
                
                if thread_state and thread_msgs:
                    first_idx, first_msg, first_data = thread_msgs[0]
                    first_msgs.append((thread_id, first_idx, first_msg, first_data, thread_state))
                    
                    if len(thread_msgs) > 1:
                        remaining_msgs[thread_id] = thread_msgs[1:]
            
            # Batch process first messages from different threads
            if first_msgs:
                logger.info(f"Batch processing first messages from {len(first_msgs)} existing threads")
                batch_items = [{
                    'thread_state': self._thread_state_to_dict(item[4]),
                    'message_data': item[3]
                } for item in first_msgs]

                batch_results = self.ai_processor.update_thread_state_batch(batch_items)

                # Record token usage for the batch
                first_user_id = first_msgs[0][2].user_id if first_msgs else None
                if first_user_id:
                    self.ai_processor.record_and_reset_tokens(
                        db=self.db,
                        user_id=first_user_id,
                        operation="email_processing_batch"
                    )

                # Apply results
                for (thread_id, idx, message, msg_data, thread_state), ai_result in zip(first_msgs, batch_results):
                    try:
                        self._apply_update_result(thread_state, message, ai_result)
                        self._sync_message_metadata(thread_state, message, is_first_message=False)
                        self.db.commit()
                        if message.user_id:
                            cache_coordinator.invalidate_thread_related_contact(
                                db=self.db,
                                tenant_id=_TENANT_ID,
                                user_id=message.user_id,
                                thread_id=thread_state.thread_id,
                            )
                        
                        scheduling_intent = ai_result.get("scheduling_intent", False)
                        scheduling_intent_type = ai_result.get("scheduling_intent_type", "none") if scheduling_intent else None
                        scheduling_intent_confidence = ai_result.get("scheduling_intent_confidence", 0.0) if scheduling_intent else None
                        
                        results[idx] = {
                            "summary": thread_state.summary,
                            "needs_reply": thread_state.needs_reply,
                            "extracted_tasks": ai_result.get("new_tasks", []),
                            "extracted_dates": [],
                            "extracted_people": [p.get("email") for p in (thread_state.participants or [])],
                            "extracted_decisions": ai_result.get("new_decisions", []),
                            "scheduling_intent": scheduling_intent,
                            "scheduling_intent_type": scheduling_intent_type,
                            "scheduling_intent_confidence": scheduling_intent_confidence
                        }
                    except Exception as e:
                        logger.error(f"Failed to apply update for message {message.id}: {e}")
                        self.db.rollback()
                        results[idx] = {"_error": True, "message_id": message.id, "error": str(e)}
            
            # Process remaining same-thread messages sequentially (state dependencies)
            for thread_id, thread_msgs in remaining_msgs.items():
                for idx, message, msg_data in thread_msgs:
                    try:
                        result = self.process_message(message, msg_data)
                        results[idx] = result
                    except Exception as e:
                        logger.error(f"Failed to process message {message.id}: {e}")
                        results[idx] = {"_error": True, "message_id": message.id, "error": str(e)}
        
        return results

    def _create_thread_state(self, thread_id: str, user_id: Optional[str] = None) -> ThreadState:
        """Create a new thread state record."""
        thread_state = ThreadState(
            thread_id=thread_id,
            user_id=user_id,
            message_count=0,
            needs_reply=True,
            open_tasks=[],
            decisions=[],
            participants=[]
        )
        self.db.add(thread_state)
        return thread_state
