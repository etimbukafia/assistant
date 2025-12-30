import base64
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.text import MIMEText

from .config import settings
from .encryption import encrypt_token, decrypt_token

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.events.freebusy'
]

# Redirect URI for OAuth callback
REDIRECT_URI = settings.OAUTH_REDIRECT_URI

class GmailClient:
    def __init__(self, db: Optional[Session] = None, credentials_file: str = "credentials.json"):
        """
        Initialize Gmail client with database session for token storage

        Args:
            db: SQLAlchemy database session (for multi-user support)
            credentials_file: Path to Google OAuth credentials JSON file
        """
        self.credentials_file = credentials_file
        self.db = db
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
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
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
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
            state=state
        )

        try:
            flow.fetch_token(code=code)
            self.creds = flow.credentials
            print(f"✓ Successfully fetched token")
            print(f"  Token scopes: {self.creds.scopes if hasattr(self.creds, 'scopes') else 'N/A'}")
        except Exception as e:
            print(f"✗ Failed to fetch token: {str(e)}")
            raise Exception(f"Failed to exchange code for token: {str(e)}")

        # Build Gmail service and get user email from profile
        # This is reliable and uses the scopes we already have
        try:
            self.service = build('gmail', 'v1', credentials=self.creds)
            print(f"✓ Successfully built Gmail service")
        except Exception as e:
            print(f"✗ Failed to build Gmail service: {str(e)}")
            raise Exception(f"Failed to build Gmail service: {str(e)}")

        try:
            profile = self.service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
            print(f"✓ Successfully got user email: {email}")
        except Exception as e:
            print(f"✗ Failed to get user profile: {str(e)}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Failed to get user email from Gmail API: {str(e)}")

        # Save credentials to database
        try:
            if self.db:
                self._save_to_database(email)
                print(f"✓ Successfully saved credentials to database")
            else:
                # Fallback to file storage if no database session
                self._save_to_file()
                print(f"✓ Successfully saved credentials to file")
        except Exception as e:
            print(f"✗ Failed to save credentials: {str(e)}")
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

        # Check if account already exists
        account = self.db.query(GmailAccount).filter(GmailAccount.email == email).first()

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
            email: Email account to load (if None, loads first available)

        Returns:
            bool: True if loaded successfully
        """
        from .models import GmailAccount

        # Get account from database
        query = self.db.query(GmailAccount)
        if email:
            account = query.filter(GmailAccount.email == email).first()
        else:
            # Load first account (for single-user MVP)
            account = query.first()

        if not account:
            return False

        # Decrypt tokens
        try:
            access_token = decrypt_token(account.access_token)
            refresh_token = decrypt_token(account.refresh_token) if account.refresh_token else None
        except ValueError as e:
            print(f"Failed to decrypt tokens: {e}")
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
                print(f"Failed to refresh token: {e}")
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
        """Get client ID from credentials file"""
        with open(self.credentials_file, 'r') as f:
            creds_data = json.load(f)
            return creds_data['web']['client_id']

    def _get_client_secret(self) -> str:
        """Get client secret from credentials file"""
        with open(self.credentials_file, 'r') as f:
            creds_data = json.load(f)
            return creds_data['web']['client_secret']

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

    def get_message_detail(self, message_id: str):
        """Get detailed message information"""
        if not self.service:
            self.authenticate()

        message = self.service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        recipient = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), None)

        body = self._get_message_body(message['payload'])

        return {
            'message_id': message['id'],
            'thread_id': message['threadId'],
            'subject': subject,
            'sender': sender,
            'recipient': recipient,
            'body': body,
            'received_at': self._parse_date(date) if date else datetime.now(timezone.utc)
        }

    def _get_message_body(self, payload):
        """Extract message body from payload"""
        body = ""

        if 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        elif 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'parts' in part:
                    body += self._get_message_body(part)

        return body

    def _parse_date(self, date_str: str):
        """Parse email date string to datetime"""
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now(timezone.utc)

    def send_message(self, to: str, subject: str, body: str):
        """Send an email"""
        if not self.service:
            self.authenticate()

        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent_message = self.service.users().messages().send(
            userId='me',
            body={'raw': raw}
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
            print(f"Failed to get history ID: {e}")
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
                print(f"History ID too old, need to re-sync: {e}")
                # Return empty list and current history ID to reset tracking
                current_id = self.get_current_history_id()
                return [], current_id or start_history_id

            print(f"Failed to get deleted messages: {e}")
            return [], start_history_id
