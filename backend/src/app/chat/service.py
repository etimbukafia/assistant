"""
Chat Service

CRUD operations for chat sessions, messages, and pending actions.
Handles session lifecycle including cleanup of expired sessions.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging

from sqlalchemy.orm import Session

from app.data.models import ChatSession, ChatMessage, ChatPendingAction, Task, PrincipalMemory
from .orchestrator import ChatOrchestrator

logger = logging.getLogger(__name__) 


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
    
    def create_session(self, session_type: str = "command") -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            session_type: 'command' (30 days) or 'reflection' (24 hours)
        """
        if session_type not in ("command", "reflection"):
            session_type = "command"
        
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=self.user_id,
            session_type=session_type,
            title=None,  # Can be set later based on first message
            created_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
            state={}
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
            metadata=metadata or {}
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
        """Get messages for a session (with user_id verification)."""
        # Verify session ownership first
        session = self.get_session(session_id)
        if not session:
            return []
        
        return self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()
    
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
        comm_module = CommunicationModule(db=self.db)
        
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
    ) -> Dict[str, Any]:
        """
        Send a message and get AI response.
        
        This is the main entry point for chat interactions.
        
        Returns:
            Dict with 'user_message', 'assistant_message', 'pending_actions'
        """
        session = self.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        # Save user message
        user_msg = self.add_message(session_id, "user", content)
        
        # Process through orchestrator
        orchestrator = ChatOrchestrator(self.db, self.user_id)
        result = await orchestrator.process_message(session, content)
        
        # Save assistant response
        assistant_msg = self.add_message(
            session_id,
            "assistant",
            result.get("response", ""),
            metadata={"state": result.get("state", {})}
        )
        
        # Create pending actions
        pending_actions = []
        for pa_data in result.get("pending_actions", []):
            pa = ChatPendingAction(
                id=str(uuid.uuid4()),
                session_id=session_id,
                message_id=assistant_msg.id,
                action_type=pa_data["action_type"],
                action_data=pa_data["action_data"],
                status="pending",
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(pa)
            pending_actions.append(pa)
        
        self.db.commit()
        
        # Auto-generate title from first message if not set
        if not session.title and session.session_type == "command":
            session.title = content[:50] + ("..." if len(content) > 50 else "")
            self.db.commit()
        
        return {
            "success": True,
            "user_message": {
                "id": user_msg.id,
                "role": user_msg.role,
                "content": user_msg.content,
                "created_at": user_msg.created_at.isoformat()
            },
            "assistant_message": {
                "id": assistant_msg.id,
                "role": assistant_msg.role,
                "content": assistant_msg.content,
                "created_at": assistant_msg.created_at.isoformat()
            },
            "pending_actions": [
                {
                    "id": pa.id,
                    "action_type": pa.action_type,
                    "action_data": pa.action_data,
                    "status": pa.status,
                    "message_id": pa.message_id
                }
                for pa in pending_actions
            ]
        }
