"""
Chat API Routes

REST endpoints for AI Chat feature.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, User
from ..database import get_db_for_user
from ..chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    session_type: str = "command"  # 'command' or 'reflection'


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class SessionResponse(BaseModel):
    id: str
    user_id: str
    session_type: str
    title: Optional[str]
    created_at: str
    last_activity_at: str
    message_count: Optional[int] = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class PendingActionResponse(BaseModel):
    id: str
    session_id: str
    message_id: Optional[int]
    action_type: str
    action_data: dict
    status: str
    created_at: str

    class Config:
        from_attributes = True


# =============================================================================
# Session Endpoints
# =============================================================================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Create a new chat session."""
    service = ChatService(db, user.user_id)
    session = service.create_session(request.session_type)
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        session_type=session.session_type,
        title=session.title,
        created_at=session.created_at.isoformat(),
        last_activity_at=session.last_activity_at.isoformat(),
        message_count=0
    )


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """List user's chat sessions."""
    service = ChatService(db, user.user_id)
    sessions = service.list_sessions(limit=limit)
    
    return {
        "sessions": [
            {
                "id": s.id,
                "session_type": s.session_type,
                "title": s.title or ("Reflection" if s.session_type == "reflection" else "Work Chat"),
                "created_at": s.created_at.isoformat(),
                "last_activity_at": s.last_activity_at.isoformat(),
                "message_count": len(s.messages) if s.messages else 0
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Get a session with its messages and pending actions."""
    service = ChatService(db, user.user_id)
    session = service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = service.get_messages(session_id)
    pending_actions = service.get_pending_actions(session_id)
    
    return {
        "session": {
            "id": session.id,
            "session_type": session.session_type,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "state": session.state
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata
            }
            for m in messages
        ],
        "pending_actions": [
            {
                "id": pa.id,
                "message_id": pa.message_id,
                "action_type": pa.action_type,
                "action_data": pa.action_data,
                "status": pa.status,
                "created_at": pa.created_at.isoformat()
            }
            for pa in pending_actions
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Delete a chat session."""
    service = ChatService(db, user.user_id)
    success = service.delete_session(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"success": True}


# =============================================================================
# Message Endpoints
# =============================================================================

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Send a message and get AI response."""
    service = ChatService(db, user.user_id)
    
    # Verify session exists
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Process message
    result = await service.send_message(session_id, request.content)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to process message"))
    
    # Return the assistant's response in format frontend expects
    return {
        "id": result["assistant_message"]["id"],
        "role": "assistant",
        "content": result["assistant_message"]["content"],
        "created_at": result["assistant_message"]["created_at"],
        "pending_actions": result.get("pending_actions", [])
    }


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Get conversation history."""
    service = ChatService(db, user.user_id)
    
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = service.get_messages(session_id, limit=limit, offset=offset)
    
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata
            }
            for m in messages
        ]
    }


# =============================================================================
# Action Approval Endpoints
# =============================================================================

@router.post("/sessions/{session_id}/approve/{action_id}")
async def approve_action(
    session_id: str,
    action_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Approve a pending action."""
    service = ChatService(db, user.user_id)
    
    # Verify session ownership
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    result = service.approve_action(action_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to approve action"))
    
    return result


@router.post("/sessions/{session_id}/reject/{action_id}")
async def reject_action(
    session_id: str,
    action_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Reject a pending action."""
    service = ChatService(db, user.user_id)
    
    # Verify session ownership
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    result = service.reject_action(action_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to reject action"))
    
    return result
