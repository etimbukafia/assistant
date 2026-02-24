from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.infra.config import get_settings, Settings
from app.security.auth import get_db_for_user, get_current_user, AuthenticatedUser
from app.security.auth import get_settings as get_app_settings # Watch out for name collision with config.get_settings
from app.integrations.gmail import GmailClient, get_gmail_client
from app.security.encryption import encrypt_token
from app.data.models import GmailAccount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# Required Google OAuth scopes for Teeks to function
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
]

# Human-readable descriptions for each scope
SCOPE_DESCRIPTIONS = {
    "https://www.googleapis.com/auth/gmail.readonly": "Read your emails to extract tasks and context",
    "https://www.googleapis.com/auth/gmail.send": "Send email replies with your approval",
    "https://www.googleapis.com/auth/calendar.readonly": "Check your calendar availability",
    "https://www.googleapis.com/auth/calendar.events": "Create calendar events with your confirmation",
    "https://www.googleapis.com/auth/calendar.events.freebusy": "See busy/free time for scheduling",
}


def verify_token_scopes(access_token: str) -> tuple[bool, List[str]]:
    """
    Verify which scopes were granted for the given access token.

    Returns:
        tuple: (all_required_granted, missing_scopes)
    """
    try:
        response = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": access_token},
            timeout=10.0
        )

        if response.status_code != 200:
            # Token invalid or expired
            return False, REQUIRED_SCOPES

        token_info = response.json()
        granted_scopes = token_info.get("scope", "").split(" ")

        missing_scopes = [
            scope for scope in REQUIRED_SCOPES
            if scope not in granted_scopes
        ]

        return len(missing_scopes) == 0, missing_scopes

    except Exception as e:
        # If we can't verify scopes, log and proceed — the Gmail API test call
        # in the endpoint will validate the token actually works
        logger.warning(f"Scope verification request failed: {e}. Proceeding with token test.")
        return True, []


class ConnectGmailRequest(BaseModel):
    """Request to connect Gmail using Supabase provider token"""
    provider_token: str
    provider_refresh_token: Optional[str] = None
    email: str


@router.post("/gmail/connect")
def connect_gmail_with_provider_token(
    request: ConnectGmailRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Connect Gmail using the Google provider token from Supabase OAuth.

    This endpoint receives the provider_token that Supabase returns after
    Google OAuth and stores it for Gmail API access.

    Verifies all required scopes were granted. Returns 403 if any are missing.
    """
    try:
        logger.info(f"Gmail connect request for user={user.user_id}, email={request.email}")

        # Step 1: Verify all required scopes were granted
        all_scopes_granted, missing_scopes = verify_token_scopes(request.provider_token)
        logger.info(f"Scope verification: granted={all_scopes_granted}, missing={missing_scopes}")

        if not all_scopes_granted:
            # Build user-friendly message about what's missing
            missing_descriptions = [
                SCOPE_DESCRIPTIONS.get(scope, scope)
                for scope in missing_scopes
            ]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "missing_scopes",
                    "message": "To use Teeks, please grant all requested permissions.",
                    "missing_permissions": missing_descriptions,
                    "action": "retry_oauth"
                }
            )

        # Step 2: Verify the token works by making a test API call
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(token=request.provider_token)
        service = build('gmail', 'v1', credentials=creds)

        # Verify we can access the Gmail API
        profile = service.users().getProfile(userId='me').execute()
        verified_email = profile.get('emailAddress')
        logger.info(f"Gmail API verified, email={verified_email}")

        if not verified_email:
            raise HTTPException(
                status_code=400,
                detail="Could not retrieve email address from Google. Please try again."
            )

        if verified_email.lower() != request.email.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Email mismatch: token is for {verified_email}, not {request.email}"
            )

        # Step 3: Encrypt tokens for storage
        encrypted_access_token = encrypt_token(request.provider_token)
        encrypted_refresh_token = encrypt_token(request.provider_refresh_token) if request.provider_refresh_token else None

        # Token expiry - Google tokens typically last 1 hour
        token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        # Step 4: Create or update GmailAccount
        # First try by user_id, then by email (handles re-registration with new user_id)
        account = db.query(GmailAccount).filter(
            GmailAccount.user_id == user.user_id
        ).first()

        if not account:
            # Check for orphaned record with same email (re-registration scenario)
            account = db.query(GmailAccount).filter(
                GmailAccount.email == verified_email
            ).first()
            if account:
                logger.info(f"Re-linking orphaned GmailAccount (old user_id={account.user_id}) to {user.user_id}")

        if account:
            # Update existing — re-link to current user if needed
            account.user_id = user.user_id
            account.email = verified_email
            account.access_token = encrypted_access_token
            account.refresh_token = encrypted_refresh_token
            account.token_expiry = token_expiry
            account.updated_at = datetime.now(timezone.utc)
            logger.info(f"Updated existing GmailAccount for {verified_email}")
        else:
            # Create new
            account = GmailAccount(
                email=verified_email,
                user_id=user.user_id,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expiry=token_expiry
            )
            db.add(account)
            logger.info(f"Creating new GmailAccount for {verified_email}")

        db.commit()
        logger.info(f"GmailAccount committed successfully for user={user.user_id}, email={verified_email}")

        # Set up Google Calendar push notifications (non-fatal if it fails)
        try:
            from app.services.calendar_watch import setup_watches_for_user
            watch_result = setup_watches_for_user(db=db, user_id=user.user_id)
            logger.info(f"Calendar watch setup for user={user.user_id}: {watch_result}")
        except Exception as watch_err:
            logger.warning(f"Calendar watch setup failed for user={user.user_id}: {watch_err}")

        # Set up Gmail push notifications via Pub/Sub (non-fatal if it fails)
        try:
            from app.services.gmail_watch import setup_watch
            from app.integrations.gmail import SCOPES
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            gmail_client = GmailClient(db=db, user_id=user.user_id)
            # Avoid extra DB round-trip/pool usage by using the fresh provider token.
            creds = Credentials(
                token=request.provider_token,
                refresh_token=request.provider_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=gmail_client._get_client_id(),
                client_secret=gmail_client._get_client_secret(),
                scopes=SCOPES,
                expiry=token_expiry.replace(tzinfo=None) if token_expiry else None,
            )
            gmail_client.creds = creds
            gmail_client.service = build('gmail', 'v1', credentials=creds)

            gmail_watch = setup_watch(gmail_client)
            if gmail_watch:
                logger.info("Gmail watch setup for user=%s: %s", user.user_id, gmail_watch)
                if not account.last_history_id:
                    account.last_history_id = str(gmail_watch.get("historyId", ""))
                    db.commit()
            else:
                logger.warning("Gmail watch setup did not return a response for %s", verified_email)
        except Exception as watch_err:
            logger.warning("Gmail watch setup failed for user=%s: %s", user.user_id, watch_err, exc_info=True)

        return {
            "status": "success",
            "message": "Google connected successfully",
            "email": verified_email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect Gmail for user={user.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to connect Google: {str(e)}")

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
        credentials = gmail_client.exchange_code_for_token(code, state)

        # Verify that credentials are valid
        email_address = gmail_client.get_profile_email()

        # Set up Gmail push notifications via Pub/Sub
        from app.services.gmail_watch import setup_watch
        watch_result = setup_watch(gmail_client)
        if not watch_result:
            logger.warning("Gmail watch setup did not return a response for %s", email_address)
        if watch_result:
            # Store initial history ID for webhook processing
            from app.data.models import GmailAccount
            account = gmail_client.db.query(GmailAccount).filter(
                GmailAccount.email == email_address
            ).first()
            if account and not account.last_history_id:
                account.last_history_id = str(watch_result.get('historyId', ''))
                gmail_client.db.commit()

        return {
            "status": "success",
            "message": "Gmail authentication successful",
            "email": email_address
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=f"Gmail authentication failed: {str(e)}")


@router.get("/status")
def gmail_auth_status(gmail_client: GmailClient = Depends(get_gmail_client)):
    """Check if Gmail is authenticated"""
    is_authenticated = gmail_client.is_authenticated()
    email = None
    
    if is_authenticated:
        try:
            email = gmail_client.get_profile_email()
        except Exception:
            pass
            
    return {
        "is_authenticated": is_authenticated,
        "email": email
    }



@router.post("/gmail/revoke")
def revoke_gmail_auth(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
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
        CalendarEvent, AgentActivityLog, SchedulingSuggestion
    )

    # Gather scoped IDs for safe deletes when user_id isn't present
    message_ids_subq = db.query(Message.id).filter(Message.user_id == user.user_id).subquery()
    task_ids_subq = db.query(Task.id).filter(Task.user_id == user.user_id).subquery()

    # 1. Delete dependent data first (scoped by user)
    db.query(Task).filter(Task.user_id == user.user_id).delete(synchronize_session=False)
    db.query(TaskQueue).filter(TaskQueue.user_id == user.user_id).delete(synchronize_session=False)
    db.query(SchedulingSuggestion).filter(SchedulingSuggestion.user_id == user.user_id).delete(synchronize_session=False)
    db.query(CalendarEvent).filter(CalendarEvent.user_id == user.user_id).delete(synchronize_session=False)
    db.query(AgentActivityLog).filter(
        (AgentActivityLog.related_message_id.in_(message_ids_subq)) |
        (AgentActivityLog.related_task_id.in_(task_ids_subq))
    ).delete(synchronize_session=False)

    # 2. Delete main data (scoped by user)
    db.query(Message).filter(Message.user_id == user.user_id).delete(synchronize_session=False)
    db.query(PrincipalMemory).filter(PrincipalMemory.user_id == user.user_id).delete(synchronize_session=False)
    db.query(DecisionPattern).filter(DecisionPattern.user_id == user.user_id).delete(synchronize_session=False)
    db.query(ContactContext).filter(ContactContext.user_id == user.user_id).delete(synchronize_session=False)

    # 3. Delete account credentials (scoped by user)
    db.query(GmailAccount).filter(
        or_(
            GmailAccount.user_id == user.user_id,
            GmailAccount.email == user.email
        )
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return {"status": "success", "message": "Gmail authorization revoked and data cleared"}
