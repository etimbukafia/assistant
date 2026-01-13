from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.infra.config import get_settings, Settings
from app.security.auth import get_db_for_user, get_settings as get_app_settings # Watch out for name collision with config.get_settings
from app.integrations.gmail import GmailClient, get_gmail_client

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/gmail")
def start_gmail_auth(gmail_client: GmailClient = Depends(get_gmail_client)):
    """
    Start Gmail OAuth flow

    Returns authorization URL that user should visit to grant permissions
    """
    return {"auth_url": gmail_client.get_authorization_url()}


@router.get("/google/callback")
def gmail_callback(
    code: str,
    state: str,
    settings: Settings = Depends(get_settings),
    gmail_client: GmailClient = Depends(get_gmail_client)
):
    """
    OAuth callback endpoint - Google redirects here after user grants permissions

    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection
    """
    try:
        credentials = gmail_client.exchange_code_for_token(code)
        
        # Verify that credentials are valid
        email_address = gmail_client.get_profile_email()
        
        return {
            "status": "success", 
            "message": "Gmail authentication successful",
            "email": email_address
        }
    except Exception as e:
        # In a real app we might redirect to frontend with error param
        return {"status": "error", "message": str(e)}


@router.get("/status")
def gmail_auth_status(gmail_client: GmailClient = Depends(get_gmail_client)):
    """Check if Gmail is authenticated"""
    is_authenticated = gmail_client.is_authenticated()
    email = None
    
    if is_authenticated:
        try:
            email = gmail_client.get_profile_email()
        except:
            pass
            
    return {
        "is_authenticated": is_authenticated,
        "email": email
    }


@router.post("/gmail/revoke")
def revoke_gmail_auth(db: Session = Depends(get_db_for_user)):
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
    from app.data.models import (
        GmailAccount, Message, Task, TaskQueue,
        PrincipalMemory, DecisionPattern, ContactContext,
        CalendarEvent, AgentActivity, SchedulingSuggestion
    )
    
    # 1. Delete dependent data first
    db.query(Task).delete()
    db.query(TaskQueue).delete()
    db.query(SchedulingSuggestion).delete()
    db.query(CalendarEvent).delete()
    db.query(AgentActivity).delete()
    
    # 2. Delete main data
    db.query(Message).delete()
    db.query(PrincipalMemory).delete()
    db.query(DecisionPattern).delete()
    db.query(ContactContext).delete()
    
    # 3. Delete account credentials
    db.query(GmailAccount).delete()
    
    db.commit()
    
    return {"status": "success", "message": "Gmail authorization revoked and data cleared"}
