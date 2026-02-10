"""
Thread State Service

Manages thread state for state-based email processing.
Threads are state machines. Messages are state updates.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.data.models import ThreadState, Task, Message
from app.processors.ai import AIProcessor

logger = logging.getLogger(__name__)


class ThreadStateService:
    """
    Service for managing thread state.

    Core principle: Each new message updates the thread state incrementally.
    No full thread transcript re-analysis.
    """

    def __init__(self, db: Session, ai_processor: Optional[AIProcessor] = None, assistant_name: str = "Donna"):
        self.db = db
        self.ai_processor = ai_processor or AIProcessor(assistant_name=assistant_name)

    def get_or_create_thread_state(self, thread_id: str) -> ThreadState:
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
        thread_state = self.db.query(ThreadState).filter(
            ThreadState.thread_id == thread_id
        ).with_for_update().first()

        if not thread_state:
            # Create new - handle race condition with upsert pattern
            try:
                thread_state = ThreadState(
                    thread_id=thread_id,
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
                thread_state = self.db.query(ThreadState).filter(
                    ThreadState.thread_id == thread_id
                ).with_for_update().first()

                # Defensive check - should never happen but prevents silent failures
                if not thread_state:
                    raise RuntimeError(
                        f"Failed to get or create ThreadState for thread_id={thread_id}. "
                        "IntegrityError occurred but subsequent fetch returned None."
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
            thread_state = self.get_or_create_thread_state(thread_id)
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

            # Update message count and last message reference
            thread_state.message_count += 1
            thread_state.last_message_id = message.id
            if is_first_message:
                thread_state.first_message_id = message.id
                thread_state.subject = message.subject

            # Add sender to participants if not already present
            self._add_participant(thread_state, message.sender, "sender")

            self.db.commit()

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
            "last_action": thread_state.last_action,
            "message_count": thread_state.message_count
        }

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
                    # Parse ISO format datetime string
                    deadline = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
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
            title=task_data.get("title"),
            description=task_data.get("description"),
            task_type=task_data.get("task_type", "explicit"),
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
                "user_id": task.user_id,
                "event_name": "task_created",
                "event_payload": {
                    "task_id": task.id,
                    "user_id": task.user_id,
                    "message_id": message.id,
                    "source": "thread_state_service"
                }
            },
            db=self.db
        )
        
        logger.info(f"Created task '{task_data.get('title')}' (id={task.id}) for thread {thread_state.thread_id}")

    def _add_participant(
        self,
        thread_state: ThreadState,
        email: str,
        role: str = "participant"
    ):
        """Add a participant to thread if not already present."""
        if not email:
            return

        participants = thread_state.participants or []
        existing_emails = {p.get("email", "").lower() for p in participants}

        if email.lower() not in existing_emails:
            participants.append({
                "email": email,
                "name": email.split("@")[0],  # Simple name extraction
                "role": role
            })
            thread_state.participants = participants

    def get_thread_summary(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of thread state for display.

        Args:
            thread_id: Gmail thread ID

        Returns:
            Dict with thread state summary or None if not found
        """
        thread_state = self.db.query(ThreadState).filter(
            ThreadState.thread_id == thread_id
        ).first()

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
                "sender": message.sender
            }
            
            # Check if thread state exists OR if we're already creating it in this batch
            existing_state = self.db.query(ThreadState).filter(
                ThreadState.thread_id == message.thread_id
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
                    thread_state = self._create_thread_state(message.thread_id)
                    self._apply_init_result(thread_state, message, ai_result)
                    self.db.commit()
                    
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
                    ThreadState.thread_id == thread_id
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
                        self.db.commit()
                        
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

    def _create_thread_state(self, thread_id: str) -> ThreadState:
        """Create a new thread state record."""
        thread_state = ThreadState(
            thread_id=thread_id,
            message_count=0,
            needs_reply=True,
            open_tasks=[],
            decisions=[],
            participants=[]
        )
        self.db.add(thread_state)
        return thread_state
