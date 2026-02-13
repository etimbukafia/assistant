import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from fastapi import Depends # Added for dependency injection

from app.infra.config import get_settings
from app.security.encryption import encrypt_token, decrypt_token
# Added auth imports for dependency factory
from app.security.auth import AuthenticatedUser, get_current_user, get_db_for_user

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.events.freebusy'
]


def _get_redirect_uri() -> str:
    """Get Gmail OAuth redirect URI from settings."""
    return get_settings().GMAIL_OAUTH_REDIRECT_URI


def _get_client_config() -> dict:
    """Build OAuth client config from environment variables."""
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GMAIL_OAUTH_REDIRECT_URI],
        }
    }


class GmailClient:
    def __init__(
        self,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ):
        """
        Initialize Gmail client with database session for token storage

        Args:
            db: SQLAlchemy database session (for multi-user support)
            user_id: Authenticated user's ID (from Supabase auth.uid())
        """
        self.db = db
        self.user_id = user_id
        self.creds = None
        self.service = None
        self._flow_state = None
        self._current_email = None  # Track which account is loaded

    def get_authorization_url(self) -> tuple[str, str]:
        """
        Get Google OAuth authorization URL for web flow

        Returns:
            tuple: (auth_url, state) - URL to redirect user to, and state for validation
        """
        flow = Flow.from_client_config(
            _get_client_config(),
            scopes=SCOPES,
            redirect_uri=_get_redirect_uri()
        )

        auth_url, state = flow.authorization_url(
            access_type='offline',  # Get refresh token
            include_granted_scopes='false',  # Don't include previously granted scopes
            prompt='consent'  # Force consent to get refresh token
        )

        self._flow_state = state
        return auth_url, state

    def authenticate_with_code(self, code: str, state: str) -> Credentials:
        """
        Complete OAuth flow with authorization code from callback

        Args:
            code: Authorization code from Google callback
            state: State parameter for validation

        Returns:
            Credentials object
        """
        flow = Flow.from_client_config(
            _get_client_config(),
            scopes=SCOPES,
            redirect_uri=_get_redirect_uri(),
            state=state
        )

        try:
            flow.fetch_token(code=code)
            self.creds = flow.credentials
            logger.info("Successfully fetched token")
            logger.info(f"Token scopes: {self.creds.scopes if hasattr(self.creds, 'scopes') else 'N/A'}")
        except Exception as e:
            logger.error(f"Failed to fetch token: {str(e)}")
            raise Exception(f"Failed to exchange code for token: {str(e)}")

        # Build Gmail service and get user email from profile
        # This is reliable and uses the scopes we already have
        try:
            self.service = build('gmail', 'v1', credentials=self.creds)
            logger.info("Successfully built Gmail service")
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {str(e)}")
            raise Exception(f"Failed to build Gmail service: {str(e)}")

        try:
            profile = self.service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
            logger.info(f"Successfully got user email: {email}")
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}", exc_info=True)
            raise Exception(f"Failed to get user email from Gmail API: {str(e)}")

        # Save credentials to database
        try:
            if self.db:
                self._save_to_database(email)
                logger.info("Successfully saved credentials to database")
            else:
                # Fallback to file storage if no database session
                self._save_to_file()
                logger.info("Successfully saved credentials to file")
        except Exception as e:
            logger.error(f"Failed to save credentials: {str(e)}")
            raise Exception(f"Failed to save credentials: {str(e)}")

        self._current_email = email
        return self.creds

    def _save_to_database(self, email: str):
        """
        Save encrypted credentials to database

        Args:
            email: User's Gmail address
        """
        from .models import GmailAccount

        # Encrypt tokens before storing
        encrypted_access_token = encrypt_token(self.creds.token)
        encrypted_refresh_token = encrypt_token(self.creds.refresh_token) if self.creds.refresh_token else None

        # Google's auth library uses offset-naive datetimes
        # Strip timezone info to avoid comparison errors
        token_expiry = self.creds.expiry.replace(tzinfo=None) if self.creds.expiry else None

        # Check if account already exists for this user
        query = self.db.query(GmailAccount).filter(GmailAccount.email == email)
        if self.user_id:
            query = query.filter(GmailAccount.user_id == self.user_id)
        account = query.first()

        if account:
            # Update existing account
            account.access_token = encrypted_access_token
            account.refresh_token = encrypted_refresh_token
            account.token_expiry = token_expiry
            account.updated_at = datetime.now(timezone.utc)
        else:
            # Create new account
            account = GmailAccount(
                email=email,
                user_id=self.user_id,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expiry=token_expiry
            )
            self.db.add(account)

        self.db.commit()

    def _save_to_file(self):
        """
        Fallback: Save credentials to file (backward compatibility)
        """
        token_file = "token.json"
        with open(token_file, 'w') as token:
            token.write(self.creds.to_json())

    def load_credentials(self, email: Optional[str] = None) -> bool:
        """
        Load existing credentials from database (or file as fallback)

        Args:
            email: Specific email account to load (optional, loads first account if None)

        Returns:
            bool: True if credentials loaded and valid, False otherwise
        """
        # Try database first
        if self.db:
            return self._load_from_database(email)
        else:
            # Fallback to file storage
            return self._load_from_file()

    def _load_from_database(self, email: Optional[str] = None) -> bool:
        """
        Load and decrypt credentials from database

        Args:
            email: Email account to load (if None, loads first available for user)

        Returns:
            bool: True if loaded successfully
        """
        from .models import GmailAccount

        # Get account from database, filtered by user_id
        query = self.db.query(GmailAccount)
        if self.user_id:
            query = query.filter(GmailAccount.user_id == self.user_id)
        if email:
            query = query.filter(GmailAccount.email == email)
        account = query.first()

        if not account:
            logger.warning(f"No GmailAccount found for user_id={self.user_id}, email={email}")
            return False

        logger.info(f"Loaded GmailAccount for user_id={self.user_id}, email={account.email}")

        # Decrypt tokens
        try:
            access_token = decrypt_token(account.access_token)
            refresh_token = decrypt_token(account.refresh_token) if account.refresh_token else None
        except ValueError as e:
            logger.error(f"Failed to decrypt tokens: {e}. Encryption key may have changed.")
            return False

        # Google's auth library expects offset-naive datetimes
        # Strip timezone if present
        token_expiry = account.token_expiry
        if token_expiry and hasattr(token_expiry, 'tzinfo') and token_expiry.tzinfo is not None:
            token_expiry = token_expiry.replace(tzinfo=None)

        # Reconstruct credentials
        self.creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._get_client_id(),
            client_secret=self._get_client_secret(),
            scopes=SCOPES,
            expiry=token_expiry
        )

        # Refresh if expired
        if self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                # Save updated tokens back to database
                self._save_to_database(account.email)
            except Exception as e:
                logger.error(f"Gmail token refresh failed for {account.email}: {e}")
                return False

        if self.creds and self.creds.valid:
            self._current_email = account.email
            self.service = build('gmail', 'v1', credentials=self.creds)
            return True

        return False

    def _load_from_file(self) -> bool:
        """
        Fallback: Load credentials from file (backward compatibility)
        """
        token_file = "token.json"
        if not os.path.exists(token_file):
            return False

        self.creds = Credentials.from_authorized_user_file(token_file, SCOPES)

        # Refresh if expired
        if self.creds and self.creds.expired and self.creds.refresh_token:
            self.creds.refresh(Request())
            with open(token_file, 'w') as token:
                token.write(self.creds.to_json())

        if self.creds and self.creds.valid:
            self.service = build('gmail', 'v1', credentials=self.creds)
            return True

        return False

    def _get_client_id(self) -> str:
        """Get client ID from environment"""
        return get_settings().GOOGLE_CLIENT_ID

    def _get_client_secret(self) -> str:
        """Get client secret from environment"""
        return get_settings().GOOGLE_CLIENT_SECRET

    def exchange_code_for_token(self, code: str) -> Credentials:
        """
        Exchange authorization code for credentials.
        Wrapper around authenticate_with_code for backward compatibility.

        Args:
            code: Authorization code from Google callback

        Returns:
            Credentials object
        """
        state = self._flow_state
        return self.authenticate_with_code(code, state)

    def get_profile_email(self) -> Optional[str]:
        """
        Get the email address of the authenticated user.

        Returns:
            Email address string, or None if not available
        """
        if self._current_email:
            return self._current_email

        if not self.service:
            if not self.load_credentials():
                return None

        try:
            profile = self.service.users().getProfile(userId='me').execute()
            self._current_email = profile.get('emailAddress')
            return self._current_email
        except Exception as e:
            logger.error(f"Failed to get profile email: {e}")
            return None

    def is_authenticated(self) -> bool:
        """Check if client has valid credentials"""
        return self.creds is not None and self.creds.valid

    def get_messages(self, max_results: int = 2, query: str = ""):
        """Fetch messages from Gmail"""
        if not self.service:
            if not self.load_credentials():
                raise Exception("Not authenticated. Please authenticate first.")

        results = self.service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q=query
        ).execute()

        messages = results.get('messages', [])
        detailed_messages = []

        for msg in messages:
            detailed_msg = self.get_message_detail(msg['id'])
            if detailed_msg:
                detailed_messages.append(detailed_msg)

        return detailed_messages

    def get_sent_messages(self, since: datetime = None, max_results: int = 50) -> list:
        """
        Fetch sent messages from Gmail for outbound reply detection.
        
        Args:
            since: Only fetch messages sent after this datetime (optional)
            max_results: Maximum number of messages to fetch
            
        Returns:
            List of sent message details with thread_id, message_id, sent_at
        """
        if not self.service:
            if not self.load_credentials():
                raise Exception("Not authenticated. Please authenticate first.")
        
        # Build query for sent mail
        query = "in:sent"
        if since:
            # Gmail date format: YYYY/MM/DD
            date_str = since.strftime("%Y/%m/%d")
            query += f" after:{date_str}"
        
        results = self.service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q=query
        ).execute()
        
        messages = results.get('messages', [])
        sent_messages = []
        
        for msg in messages:
            try:
                # Get minimal message details (no full body needed)
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Date']
                ).execute()
                
                headers = message.get('payload', {}).get('headers', [])
                date = next((h['value'] for h in headers if h['name'] == 'Date'), None)
                
                sent_messages.append({
                    'message_id': message['id'],
                    'thread_id': message['threadId'],
                    'sent_at': self._parse_date(date) if date else datetime.now(timezone.utc)
                })
            except Exception as e:
                logger.warning(f"Failed to get sent message {msg['id']}: {e}")
                continue
        
        return sent_messages

    def get_message_detail(self, message_id: str):
        """Get detailed message information including Gmail labels"""
        if not self.service:
            if not self.load_credentials():
                raise Exception("Not authenticated. Please authenticate first.")

        message = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        payload = message.get('payload')
        if not payload:
            logger.warning(f"Message {message_id} has no payload")
            return None

        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        recipient = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), None)

        # Extract headers for filtering (bulk/automated email detection)
        list_unsubscribe = next((h['value'] for h in headers if h['name'].lower() == 'list-unsubscribe'), None)
        precedence = next((h['value'] for h in headers if h['name'].lower() == 'precedence'), None)
        auto_submitted = next((h['value'] for h in headers if h['name'].lower() == 'auto-submitted'), None)

        body = self._get_message_body(payload)

        # Extract Gmail labels (includes CATEGORY_* labels)
        gmail_labels = message.get('labelIds', [])

        return {
            'message_id': message['id'],
            'thread_id': message.get('threadId', ''),
            'subject': subject,
            'sender': sender,
            'recipient': recipient,
            'body': body,
            'received_at': self._parse_date(date) if date else datetime.now(timezone.utc),
            'attachments': self._get_attachment_metadata(payload, message['id']),
            'gmail_labels': gmail_labels,
            'headers': {
                'list_unsubscribe': list_unsubscribe,
                'precedence': precedence,
                'auto_submitted': auto_submitted,
            }
        }

    def _get_attachment_metadata(self, payload, message_id: str) -> list:
        """
        Extract attachment metadata from message payload.
        
        Returns:
            List of dicts with: filename, mime_type, size, attachment_id
        """
        attachments = []
        self._extract_attachments_recursive(payload, message_id, attachments)
        return attachments

    def _extract_attachments_recursive(self, part, message_id: str, attachments: list):
        """Recursively extract attachments from multipart messages."""
        # Check if this part is an attachment
        if 'filename' in part and part['filename']:
            attachment_id = part['body'].get('attachmentId')
            if attachment_id:
                attachments.append({
                    'filename': part['filename'],
                    'mime_type': part.get('mimeType', 'application/octet-stream'),
                    'size': part['body'].get('size', 0),
                    'attachment_id': attachment_id,
                    'message_id': message_id
                })
        
        # Recurse into parts
        if 'parts' in part:
            for subpart in part['parts']:
                self._extract_attachments_recursive(subpart, message_id, attachments)

    def download_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download attachment content from Gmail.
        
        Args:
            message_id: Gmail message ID
            attachment_id: Attachment ID from _get_attachment_metadata
            
        Returns:
            Raw file bytes, or None if download failed
        """
        if not self.service:
            if not self.load_credentials():
                return None

        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment.get('data', '')
            return base64.urlsafe_b64decode(data)
        except Exception as e:
            logger.warning(f"Failed to download attachment: {e}")
            return None

    def _get_message_body(self, payload):
        """Extract message body from payload"""
        body = ""

        if 'body' in payload and 'data' in payload['body']:
            try:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            except (UnicodeDecodeError, Exception) as e:
                logger.warning(f"Failed to decode message body: {e}")
                body = "[Message body could not be decoded]"
        elif 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    if 'data' in part.get('body', {}):
                        try:
                            body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        except (UnicodeDecodeError, Exception) as e:
                            logger.warning(f"Failed to decode message part: {e}")
                            continue
                elif 'parts' in part:
                    body += self._get_message_body(part)

        return body

    def _parse_date(self, date_str: str):
        """Parse email date string to datetime"""
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return datetime.now(timezone.utc)

    def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str = None,
        thread_id: str = None,
        html: bool = False,
    ):
        """
        Send an email, optionally as a threaded reply.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            in_reply_to: Message-ID header value for threading
            thread_id: Gmail thread ID to attach the reply to
            html: If True, send body as HTML
        """
        if not self.service:
            if not self.load_credentials():
                raise Exception("Not authenticated. Please authenticate first.")

        subtype = 'html' if html else 'plain'
        message = MIMEText(body, subtype)
        message['to'] = to
        message['subject'] = subject

        if in_reply_to:
            message['In-Reply-To'] = in_reply_to
            message['References'] = in_reply_to

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        send_body = {'raw': raw}
        if thread_id:
            send_body['threadId'] = thread_id

        sent_message = self.service.users().messages().send(
            userId='me',
            body=send_body
        ).execute()

        return sent_message

    def get_current_history_id(self) -> Optional[str]:
        """
        Get the current history ID from Gmail.
        This is used to start tracking deletions from the current point.

        Returns:
            Current history ID string, or None if failed
        """
        if not self.service:
            if not self.load_credentials():
                return None

        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('historyId')
        except Exception as e:
            logger.error(f"Failed to get history ID: {e}")
            return None

    def get_deleted_message_ids(self, start_history_id: str) -> tuple[list, Optional[str]]:
        """
        Check Gmail for deleted messages using History API.

        Args:
            start_history_id: History ID to start checking from

        Returns:
            tuple: (list of deleted message IDs, new history ID for next sync)
        """
        if not self.service:
            if not self.load_credentials():
                return [], start_history_id

        deleted_ids = []
        new_history_id = start_history_id

        try:
            # Get history since last check
            response = self.service.users().history().list(
                userId='me',
                startHistoryId=start_history_id,
                historyTypes=['messageDeleted']
            ).execute()

            history = response.get('history', [])
            for record in history:
                deleted = record.get('messagesDeleted', [])
                for msg in deleted:
                    deleted_ids.append(msg['message']['id'])

            # Get new history ID for next sync
            new_history_id = response.get('historyId', start_history_id)

            # Handle pagination if needed
            while 'nextPageToken' in response:
                response = self.service.users().history().list(
                    userId='me',
                    startHistoryId=start_history_id,
                    historyTypes=['messageDeleted'],
                    pageToken=response['nextPageToken']
                ).execute()

                history = response.get('history', [])
                for record in history:
                    deleted = record.get('messagesDeleted', [])
                    for msg in deleted:
                        deleted_ids.append(msg['message']['id'])

                new_history_id = response.get('historyId', new_history_id)

            return deleted_ids, new_history_id

        except Exception as e:
            # Handle case where history ID is too old (404 error)
            if 'notFound' in str(e) or '404' in str(e):
                logger.warning(f"History ID too old, need to re-sync: {e}")
                # Return empty list and current history ID to reset tracking
                current_id = self.get_current_history_id()
                return [], current_id or start_history_id

            logger.error(f"Failed to get deleted messages: {e}")
            return [], start_history_id


    def get_new_message_ids(self, start_history_id: str) -> tuple[list, Optional[str]]:
        """
        Get new inbox message IDs since a given history ID using the History API.

        Args:
            start_history_id: History ID to start checking from

        Returns:
            tuple: (list of new Gmail message IDs, new history ID for next check)
        """
        if not self.service:
            if not self.load_credentials():
                return [], start_history_id

        new_ids = []
        new_history_id = start_history_id

        try:
            response = self.service.users().history().list(
                userId='me',
                startHistoryId=start_history_id,
                historyTypes=['messageAdded'],
                labelId='INBOX'
            ).execute()

            history = response.get('history', [])
            for record in history:
                added = record.get('messagesAdded', [])
                for msg in added:
                    labels = msg['message'].get('labelIds', [])
                    if 'INBOX' in labels:
                        new_ids.append(msg['message']['id'])

            new_history_id = response.get('historyId', start_history_id)

            # Handle pagination
            while 'nextPageToken' in response:
                response = self.service.users().history().list(
                    userId='me',
                    startHistoryId=start_history_id,
                    historyTypes=['messageAdded'],
                    labelId='INBOX',
                    pageToken=response['nextPageToken']
                ).execute()

                history = response.get('history', [])
                for record in history:
                    added = record.get('messagesAdded', [])
                    for msg in added:
                        labels = msg['message'].get('labelIds', [])
                        if 'INBOX' in labels:
                            new_ids.append(msg['message']['id'])

                new_history_id = response.get('historyId', new_history_id)

            return new_ids, new_history_id

        except Exception as e:
            if 'notFound' in str(e) or '404' in str(e):
                logger.warning(f"History ID too old, resetting: {e}")
                current_id = self.get_current_history_id()
                return [], current_id or start_history_id

            logger.error(f"Failed to get new messages from history: {e}")
            return [], start_history_id


def get_gmail_client(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
) -> GmailClient:
    """Create GmailClient with database session and user context for token storage"""
    return GmailClient(db=db, user_id=user.user_id)
