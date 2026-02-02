"""
Chat Service

CRUD operations for chat sessions, messages, and pending actions.
Handles session lifecycle including cleanup of expired sessions.

Processing Strategy: Optimistic Sync with Async Fallback
- Reflection mode: Always synchronous (immediate, warm responses)
- Action mode: Try sync first, fallback to async for:
  - Tool calls detected
  - Processing timeout (>8s)
  - High server load
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import uuid
import re
import logging

from sqlalchemy.orm import Session

from app.data.models import ChatSession, ChatMessage, ChatPendingAction, Task, PrincipalMemory, TaskQueue
from app.jobs.task_queue import queue_service
from .orchestrator import ChatOrchestrator

logger = logging.getLogger(__name__)

# Timeout for synchronous processing (seconds)
SYNC_TIMEOUT_SECONDS = 8.0

# Timeout for async messages stuck in "processing" state (TTL on read)
PROCESSING_TIMEOUT_MINUTES = 2


class ProcessingStatus(str, Enum):
    """Chat message processing status."""
    COMPLETE = "complete"
    PROCESSING = "processing"
    FAILED = "failed"


@dataclass
class ChatResponse:
    """Unified response for chat messages."""
    status: ProcessingStatus
    message_id: Optional[int] = None
    job_id: Optional[str] = None
    response: Optional[str] = None
    pending_actions: Optional[List[Dict]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"status": self.status.value}
        if self.message_id:
            result["message_id"] = self.message_id
        if self.job_id:
            result["job_id"] = self.job_id
        if self.response:
            result["response"] = self.response
        if self.pending_actions:
            result["pending_actions"] = self.pending_actions
        if self.error:
            result["error"] = self.error
        return result


# Patterns that suggest tool usage will be needed
TOOL_INTENT_PATTERNS = [
    # Email operations
    r"\b(search|find|look for|show me).*(email|message|mail)",
    r"\b(draft|write|compose|reply).*(email|message|response)",
    r"\bemail.*(from|about|regarding)",

    # Task operations
    r"\b(create|add|make|new).*(task|todo|reminder)",
    r"\b(list|show|what).*(task|todo)",
    r"\bmark.*(done|complete|finished)",

    # Calendar operations
    r"\b(schedule|book|set up).*(meeting|call|appointment)",
    r"\b(calendar|availability|free time)",
    r"\bwhat.*meeting",

    # Memory operations
    r"\bremember.*(that|this|my)",
    r"\bprefer(ence)?",

    # General action keywords
    r"\b(update|change|modify|edit|delete|remove|cancel)",
]

# Compiled patterns for efficiency
_TOOL_INTENT_RE = [re.compile(p, re.IGNORECASE) for p in TOOL_INTENT_PATTERNS]


def detect_tool_intent(message: str) -> bool:
    """
    Detect if a message likely requires tool usage.

    Used to decide between sync and async processing paths.
    Returns True if the message appears to need tools.
    """
    for pattern in _TOOL_INTENT_RE:
        if pattern.search(message):
            return True
    return False 


class ChatService:
    """
    Service layer for chat operations.
    
    Responsibilities:
    - Session CRUD
    - Message management
    - Pending action approval/rejection
    - Session cleanup
    """
    
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
    
    # =========================================================================
    # Session Operations
    # =========================================================================
    
    def create_session(
        self, 
        session_type: str = "command",
        user_first_name: Optional[str] = None
    ) -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            session_type: 'command' (30 days) or 'reflection' (24 hours)
            user_first_name: User's first name (from JWT) for personalization
        """
        if session_type not in ("command", "reflection"):
            session_type = "command"
        
        # Initialize state with user info for personalization
        initial_state = {}
        if user_first_name:
            initial_state["user_first_name"] = user_first_name
        
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            session_type=session_type,
            title=None,  # Can be set later based on first message
            created_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
            state=initial_state
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID."""
        return self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == self.user_id
        ).first()
    
    def list_sessions(self, limit: int = 20) -> List[ChatSession]:
        """List user's sessions, most recent first."""
        return self.db.query(ChatSession).filter(
            ChatSession.user_id == self.user_id
        ).order_by(ChatSession.last_activity_at.desc()).limit(limit).all()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True
    
    def update_session_title(self, session_id: str, title: str) -> Optional[ChatSession]:
        """Update session title."""
        session = self.get_session(session_id)
        if session:
            session.title = title
            self.db.commit()
        return session
    
    # =========================================================================
    # Message Operations
    # =========================================================================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> ChatMessage:
        """Add a message to a session."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
            message_metadata=metadata or {}
        )
        
        self.db.add(message)
        
        # Update session activity
        session = self.get_session(session_id)
        if session:
            session.last_activity_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """
        Get messages for a session (with user_id verification).
        
        Also performs TTL-on-read cleanup: auto-expires messages stuck 
        in 'processing' state for longer than PROCESSING_TIMEOUT_MINUTES.
        """
        # Verify session ownership first
        session = self.get_session(session_id)
        if not session:
            return []
        
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()
        
        # TTL-on-read: auto-expire stuck processing messages
        timeout_cutoff = datetime.now(timezone.utc) - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)
        updated_any = False
        
        for msg in messages:
            metadata = msg.message_metadata or {}
            if (metadata.get("status") == "processing" and 
                msg.created_at < timeout_cutoff):
                # Expire this stuck message
                msg.content = "I apologize, my response timed out. Please try again."
                msg.message_metadata = {
                    **metadata,
                    "status": "timeout",
                    "error": "Processing exceeded time limit",
                    "timed_out_at": datetime.now(timezone.utc).isoformat()
                }
                updated_any = True
                logger.warning(f"Auto-expired stuck message {msg.id} (created {msg.created_at})")
        
        if updated_any:
            self.db.commit()
        
        return messages
    
    # =========================================================================
    # Pending Action Operations
    # =========================================================================
    
    def get_pending_actions(self, session_id: str) -> List[ChatPendingAction]:
        """Get pending actions for a session (with user_id verification)."""
        # Verify session ownership first
        session = self.get_session(session_id)
        if not session:
            return []
        
        return self.db.query(ChatPendingAction).filter(
            ChatPendingAction.session_id == session_id,
            ChatPendingAction.status == "pending"
        ).order_by(ChatPendingAction.created_at.asc()).all()
    
    def get_pending_action(self, action_id: str) -> Optional[ChatPendingAction]:
        """Get a specific pending action."""
        action = self.db.query(ChatPendingAction).filter(
            ChatPendingAction.id == action_id
        ).first()
        
        # Verify ownership via session
        if action:
            session = self.get_session(action.session_id)
            if not session:
                return None
        
        return action
    
    def approve_action(self, action_id: str) -> Dict[str, Any]:
        """
        Approve and execute a pending action.
        
        Returns:
            Dict with 'success', 'result', and optionally 'error'
        """
        action = self.get_pending_action(action_id)
        if not action:
            return {"success": False, "error": "Action not found"}
        
        if action.status != "pending":
            return {"success": False, "error": f"Action already {action.status}"}
        
        try:
            result = self._execute_approved_action(action)
            action.status = "approved"
            self.db.commit()
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error executing action {action_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def reject_action(self, action_id: str) -> Dict[str, Any]:
        """Reject a pending action."""
        action = self.get_pending_action(action_id)
        if not action:
            return {"success": False, "error": "Action not found"}
        
        if action.status != "pending":
            return {"success": False, "error": f"Action already {action.status}"}
        
        action.status = "rejected"
        self.db.commit()
        return {"success": True}
    
    def _execute_approved_action(self, action: ChatPendingAction) -> Dict[str, Any]:
        """Execute an approved action based on its type."""
        action_type = action.action_type
        data = action.action_data
        
        if action_type == "create_task":
            return self._execute_create_task(data)
        elif action_type == "update_principal_memory":
            return self._execute_update_memory(data)
        elif action_type == "draft_reply":
            return self._execute_draft_reply(data)
        elif action_type == "add_to_calendar":
            return self._execute_add_calendar(data)
        elif action_type == "cancel_meeting":
            return self._execute_cancel_meeting(data)
        elif action_type == "reschedule_meeting":
            return self._execute_reschedule_meeting(data)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    def _execute_create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task from approved action."""
        due_date = None
        if data.get("due_date"):
            try:
                due_date = datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
            except ValueError:
                pass
        
        task = Task(
            user_id=self.user_id,
            title=data.get("title", "New Task"),
            description=data.get("description", ""),
            priority=data.get("priority", "medium"),
            status="pending",
            task_type="explicit",
            due_date=due_date,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        return {"task_id": task.id, "title": task.title}
    
    def _execute_update_memory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update principal memory from approved action."""
        key = data.get("key")
        value = data.get("value")
        context_type = data.get("context_type", "drafting")
        
        # Check if preference already exists
        existing = self.db.query(PrincipalMemory).filter(
            PrincipalMemory.user_id == self.user_id,
            PrincipalMemory.key == key,
            PrincipalMemory.context_type == context_type
        ).first()
        
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            memory = PrincipalMemory(
                user_id=self.user_id,
                key=key,
                value=value,
                context_type=context_type,
                source="chat"
            )
            self.db.add(memory)
        
        self.db.commit()
        return {"key": key, "value": value}
    
    def _execute_draft_reply(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate and store a draft reply using CommunicationModule.
        """
        from app.agents.modules.communication import CommunicationModule
        from app.data.models import Message
        
        email_id = data.get("email_id")
        if not email_id:
            return {"success": False, "error": "No email_id provided"}
        
        # Verify email ownership
        email = self.db.query(Message).filter(
            Message.id == email_id,
            Message.user_id == self.user_id
        ).first()
        
        if not email:
            return {"success": False, "error": "Email not found"}
        
        # Use CommunicationModule to generate the draft
        from core.llm.config import LLMConfig
        comm_module = CommunicationModule(llm_config=LLMConfig.for_chat())
        
        result = comm_module.generate_reply(
            message_id=email_id,
            tone=data.get("tone", "professional"),
            intent=data.get("intent"),
            additional_context="\n".join(data.get("key_points", [])),
            db=self.db,
            user_id=self.user_id
        )
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to generate draft")
            }
        
        # Store draft in message metadata or return for frontend display
        return {
            "success": True,
            "email_id": email_id,
            "draft": result.get("draft"),
            "subject_line": result.get("subject_line"),
            "tone_used": result.get("tone_used"),
            "status": "draft_created",
            "note": "Draft ready for review and editing"
        }
    
    def _execute_add_calendar(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create calendar event."""
        from app.data.models import CalendarEvent
        
        start_time = datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(data["end_time"].replace("Z", "+00:00"))
        
        event = CalendarEvent(
            user_id=self.user_id,
            title=data.get("title"),
            description=data.get("description", ""),
            start_time=start_time,
            end_time=end_time,
            participants=data.get("participants", []),
            status="pending",
            provider="local"
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        return {"event_id": event.id, "title": event.title}
    
    def _execute_cancel_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a calendar event."""
        from app.data.models import CalendarEvent
        
        event_id = data.get("event_id")
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()
        
        if not event:
            raise ValueError("Event not found")
        
        event.status = "cancelled"
        self.db.commit()
        
        return {"event_id": event_id, "status": "cancelled"}
    
    def _execute_reschedule_meeting(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Reschedule a calendar event."""
        from app.data.models import CalendarEvent
        
        event_id = data.get("event_id")
        event = self.db.query(CalendarEvent).filter(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()
        
        if not event:
            raise ValueError("Event not found")
        
        event.start_time = datetime.fromisoformat(data["new_start_time"].replace("Z", "+00:00"))
        event.end_time = datetime.fromisoformat(data["new_end_time"].replace("Z", "+00:00"))
        self.db.commit()
        
        return {"event_id": event_id, "new_start_time": data["new_start_time"]}
    
    # =========================================================================
    # Cleanup Operations
    # =========================================================================
    
    def cleanup_expired_sessions(self) -> Dict[str, int]:
        """
        Delete expired sessions based on retention policy.
        
        - Reflection sessions: 24 hours
        - Command sessions: 30 days
        
        Returns:
            Dict with counts of deleted sessions by type
        """
        now = datetime.now(timezone.utc)
        reflection_cutoff = now - timedelta(hours=24)
        command_cutoff = now - timedelta(days=30)
        
        # Delete reflection sessions older than 24 hours
        reflection_deleted = self.db.query(ChatSession).filter(
            ChatSession.session_type == "reflection",
            ChatSession.last_activity_at < reflection_cutoff
        ).delete(synchronize_session=False)
        
        # Delete command sessions older than 30 days
        command_deleted = self.db.query(ChatSession).filter(
            ChatSession.session_type == "command",
            ChatSession.last_activity_at < command_cutoff
        ).delete(synchronize_session=False)
        
        self.db.commit()
        
        return {
            "reflection_deleted": reflection_deleted,
            "command_deleted": command_deleted
        }
    
    # =========================================================================
    # High-level Chat Flow
    # =========================================================================

    async def send_message(
        self,
        session_id: str,
        content: str
    ) -> ChatResponse:
        """
        Send a message and get AI response.

        Processing Strategy:
        - Reflection mode: Always synchronous (warm, immediate)
        - Action mode: Optimistic sync with async fallback
          - If tool intent detected → async immediately
          - Otherwise try sync with timeout → fallback to async

        Returns:
            ChatResponse with status, message/job info
        """
        session = self.get_session(session_id)
        if not session:
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error="Session not found"
            )

        # Save user message
        user_msg = self.add_message(session_id, "user", content)

        # Auto-generate title from first message if not set
        if not session.title and session.session_type == "command":
            session.title = content[:50] + ("..." if len(content) > 50 else "")
            self.db.commit()

        # REFLECTION MODE: Always synchronous
        if session.session_type == "reflection":
            return await self._process_sync(session, content, user_msg.id)

        # ACTION MODE: Optimistic sync with async fallback
        # Check if message likely needs tools
        if detect_tool_intent(content):
            logger.info(f"Tool intent detected, using async path for session {session_id}")
            return self._enqueue_async(session, content, user_msg.id)

        # Try synchronous processing with timeout
        try:
            return await asyncio.wait_for(
                self._process_sync(session, content, user_msg.id),
                timeout=SYNC_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.info(f"Sync timeout, falling back to async for session {session_id}")
            return self._enqueue_async(session, content, user_msg.id)

    async def _process_sync(
        self,
        session: ChatSession,
        content: str,
        user_message_id: int
    ) -> ChatResponse:
        """
        Process message synchronously.

        Used for:
        - All reflection mode messages
        - Action mode messages that don't need tools
        """
        try:
            orchestrator = ChatOrchestrator(self.db, self.user_id)
            result = await orchestrator.process_message(session, content)

            # Save assistant response
            assistant_msg = self.add_message(
                session.id,
                "assistant",
                result.get("response", ""),
                metadata={"state": result.get("state", {})}
            )

            # Create pending actions
            pending_actions = []
            for pa_data in result.get("pending_actions", []):
                pa = ChatPendingAction(
                    id=str(uuid.uuid4()),
                    session_id=session.id,
                    message_id=assistant_msg.id,
                    action_type=pa_data["action_type"],
                    action_data=pa_data["action_data"],
                    status="pending",
                    created_at=datetime.now(timezone.utc)
                )
                self.db.add(pa)
                pending_actions.append({
                    "id": pa.id,
                    "action_type": pa.action_type,
                    "action_data": pa.action_data,
                    "status": pa.status,
                    "message_id": pa.message_id
                })

            self.db.commit()

            return ChatResponse(
                status=ProcessingStatus.COMPLETE,
                message_id=assistant_msg.id,
                response=assistant_msg.content,
                pending_actions=pending_actions if pending_actions else None
            )

        except Exception as e:
            logger.error(f"Sync processing failed: {e}")
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error=str(e)
            )

    def _enqueue_async(
        self,
        session: ChatSession,
        content: str,
        user_message_id: int
    ) -> ChatResponse:
        """
        Enqueue message for async processing.

        Creates a job in TaskQueue and returns job_id for polling.
        """
        job_id = str(uuid.uuid4())

        # Add placeholder assistant message with job tracking
        placeholder_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content="",  # Empty content, will be filled by worker
            created_at=datetime.now(timezone.utc),
            message_metadata={"job_id": job_id, "status": "processing"}
        )
        self.db.add(placeholder_msg)

        # Update session activity
        session.last_activity_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(placeholder_msg)

        # Enqueue the job
        queue_service.enqueue(
            task_type="process_chat_message",
            payload={
                "job_id": job_id,
                "session_id": session.id,
                "user_id": self.user_id,
                "content": content,
                "user_message_id": user_message_id,
                "assistant_message_id": placeholder_msg.id
            },
            db=self.db
        )

        logger.info(f"Enqueued chat job {job_id} for session {session.id}")

        return ChatResponse(
            status=ProcessingStatus.PROCESSING,
            job_id=job_id,
            message_id=placeholder_msg.id
        )

    def get_job_status(self, job_id: str) -> ChatResponse:
        """
        Check the status of an async chat job.

        Returns:
            ChatResponse with current status and response if complete
        """
        from sqlalchemy import cast, String

        # Find the message with this job_id
        # Use text search since JSON queries vary by database
        messages = self.db.query(ChatMessage).join(
            ChatSession, ChatMessage.session_id == ChatSession.id
        ).filter(
            ChatSession.user_id == self.user_id
        ).all()

        # Find message with matching job_id in metadata
        message = None
        for msg in messages:
            metadata = msg.message_metadata or {}
            if metadata.get("job_id") == job_id:
                message = msg
                break

        if not message:
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                error="Job not found"
            )

        metadata = message.message_metadata or {}

        # Check if still processing
        if metadata.get("status") == "processing":
            # TTL check: auto-expire if stuck too long
            timeout_cutoff = datetime.now(timezone.utc) - timedelta(minutes=PROCESSING_TIMEOUT_MINUTES)
            if message.created_at < timeout_cutoff:
                # Expire this stuck message
                message.content = "I apologize, my response timed out. Please try again."
                message.message_metadata = {
                    **metadata,
                    "status": "timeout",
                    "error": "Processing exceeded time limit",
                    "timed_out_at": datetime.now(timezone.utc).isoformat()
                }
                self.db.commit()
                logger.warning(f"Auto-expired stuck job {job_id} (message {message.id})")
                
                return ChatResponse(
                    status=ProcessingStatus.FAILED,
                    job_id=job_id,
                    message_id=message.id,
                    error="Processing timed out. Please try again."
                )
            
            return ChatResponse(
                status=ProcessingStatus.PROCESSING,
                job_id=job_id,
                message_id=message.id
            )

        # Check if timed out (already expired by another path)
        if metadata.get("status") == "timeout":
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                job_id=job_id,
                message_id=message.id,
                error=metadata.get("error", "Processing timed out")
            )

        # Check if failed
        if metadata.get("status") == "failed":
            return ChatResponse(
                status=ProcessingStatus.FAILED,
                job_id=job_id,
                error=metadata.get("error", "Processing failed")
            )

        # Complete - return the response
        pending_actions = self.get_pending_actions_for_message(message.id)

        return ChatResponse(
            status=ProcessingStatus.COMPLETE,
            message_id=message.id,
            response=message.content,
            pending_actions=[
                {
                    "id": pa.id,
                    "action_type": pa.action_type,
                    "action_data": pa.action_data,
                    "status": pa.status,
                    "message_id": pa.message_id
                }
                for pa in pending_actions
            ] if pending_actions else None
        )

    def get_pending_actions_for_message(self, message_id: int) -> List[ChatPendingAction]:
        """Get pending actions for a specific message."""
        return self.db.query(ChatPendingAction).filter(
            ChatPendingAction.message_id == message_id,
            ChatPendingAction.status == "pending"
        ).all()

    # =========================================================================
    # Legacy method for backwards compatibility
    # =========================================================================

    async def send_message_legacy(
        self,
        session_id: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Legacy send_message method for backwards compatibility.

        Returns dict format expected by older clients.
        """
        response = await self.send_message(session_id, content)

        if response.status == ProcessingStatus.FAILED:
            return {"success": False, "error": response.error}

        if response.status == ProcessingStatus.PROCESSING:
            return {
                "success": True,
                "status": "processing",
                "job_id": response.job_id,
                "message_id": response.message_id
            }

        # Complete
        session = self.get_session(session_id)
        user_msg = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user"
        ).order_by(ChatMessage.created_at.desc()).first()

        assistant_msg = self.db.query(ChatMessage).get(response.message_id)

        return {
            "success": True,
            "user_message": {
                "id": user_msg.id if user_msg else None,
                "role": "user",
                "content": content,
                "created_at": user_msg.created_at.isoformat() if user_msg else None
            },
            "assistant_message": {
                "id": response.message_id,
                "role": "assistant",
                "content": response.response,
                "created_at": assistant_msg.created_at.isoformat() if assistant_msg else None
            },
            "pending_actions": response.pending_actions or []
        }
