import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

import httpx
from sqlalchemy.orm import Session

from app.infra.config import get_settings
from app.security.encryption import encrypt_token, decrypt_token
from app.data.models import OutlookAccount

logger = logging.getLogger(__name__)


class OutlookClient:
    """
    Microsoft Graph client for Outlook email.
    Uses stored OAuth credentials from OutlookAccount.
    """

    def __init__(self, db: Optional[Session] = None, user_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._current_email: Optional[str] = None

    def _get_client_id(self) -> str:
        return get_settings().MICROSOFT_CLIENT_ID

    def _get_client_secret(self) -> str:
        return get_settings().MICROSOFT_CLIENT_SECRET

    def _token_endpoint(self) -> str:
        return "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    def _graph_headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise Exception("Outlook not authenticated. Please connect your Microsoft account.")
        return {"Authorization": f"Bearer {self._access_token}"}

    def load_credentials(self, email: Optional[str] = None) -> bool:
        if not self.db:
            return False

        query = self.db.query(OutlookAccount)
        if self.user_id:
            query = query.filter(OutlookAccount.user_id == self.user_id)
        if email:
            query = query.filter(OutlookAccount.email == email)
        account = query.first()
        if not account:
            logger.warning("No Outlook account found in database")
            return False

        try:
            self._access_token = decrypt_token(account.access_token)
            self._refresh_token = decrypt_token(account.refresh_token) if account.refresh_token else None
        except ValueError as e:
            logger.error("Failed to decrypt Outlook tokens: %s", e)
            return False

        self._token_expiry = account.token_expiry
        self._current_email = account.email

        if self._token_expiry and self._token_expiry < datetime.now(timezone.utc):
            if not self._refresh_token:
                logger.warning("Outlook token expired and no refresh token available")
                return False
            if not self._refresh_access_token(account):
                return False

        return True

    def _refresh_access_token(self, account: OutlookAccount) -> bool:
        client_id = self._get_client_id()
        client_secret = self._get_client_secret()
        if not client_id or not client_secret:
            logger.error("MICROSOFT_CLIENT_ID or MICROSOFT_CLIENT_SECRET not configured")
            return False

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "scope": "https://graph.microsoft.com/.default offline_access",
        }

        try:
            resp = httpx.post(self._token_endpoint(), data=data, timeout=10.0)
            if resp.status_code != 200:
                logger.error("Failed to refresh Outlook token: %s", resp.text)
                return False
            payload = resp.json()
            self._access_token = payload.get("access_token")
            new_refresh = payload.get("refresh_token") or self._refresh_token
            expires_in = int(payload.get("expires_in", 3600))
            self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            account.access_token = encrypt_token(self._access_token)
            account.refresh_token = encrypt_token(new_refresh) if new_refresh else None
            account.token_expiry = self._token_expiry
            account.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        except Exception as e:
            logger.error("Outlook token refresh failed: %s", e)
            return False

    def get_profile(self) -> Dict[str, Any]:
        resp = httpx.get("https://graph.microsoft.com/v1.0/me", headers=self._graph_headers(), timeout=10.0)
        resp.raise_for_status()
        return resp.json()

    def get_messages(self, max_results: int = 10, query: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {
            "$top": max_results,
            "$select": "id,subject,receivedDateTime,bodyPreview,body,from,toRecipients,ccRecipients,bccRecipients,conversationId",
            "$orderby": "receivedDateTime desc",
        }
        if query:
            params["$search"] = f'"{query}"'
            headers = {**self._graph_headers(), "ConsistencyLevel": "eventual"}
        else:
            headers = self._graph_headers()
        resp = httpx.get(
            "https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages",
            headers=headers,
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_message_detail(self, message_id: str) -> Dict[str, Any]:
        resp = httpx.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers=self._graph_headers(),
            params={"$select": "id,subject,receivedDateTime,body,from,toRecipients,ccRecipients,bccRecipients,conversationId"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_sent_messages(self, since: Optional[datetime] = None, max_results: int = 100) -> List[Dict[str, Any]]:
        params = {
            "$top": max_results,
            "$select": "id,subject,receivedDateTime,bodyPreview,body,from,toRecipients,ccRecipients,bccRecipients,conversationId",
            "$orderby": "receivedDateTime desc",
        }
        if since:
            params["$filter"] = f"receivedDateTime ge {since.isoformat()}"
        resp = httpx.get(
            "https://graph.microsoft.com/v1.0/me/mailFolders/SentItems/messages",
            headers=self._graph_headers(),
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def send_message(self, subject: str, body: str, to: List[str], cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None):
        to_recipients = [{"emailAddress": {"address": addr}} for addr in to]
        cc_recipients = [{"emailAddress": {"address": addr}} for addr in (cc or [])]
        bcc_recipients = [{"emailAddress": {"address": addr}} for addr in (bcc or [])]
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": to_recipients,
                "ccRecipients": cc_recipients,
                "bccRecipients": bcc_recipients,
            },
            "saveToSentItems": True,
        }
        resp = httpx.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers=self._graph_headers(),
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        return True

    def send_reply(self, message_id: str, body: str) -> bool:
        payload = {"comment": body}
        resp = httpx.post(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/reply",
            headers=self._graph_headers(),
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        return True

    def get_delta_messages(self, delta_link: Optional[str] = None) -> Dict[str, Any]:
        url = delta_link or "https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages/delta"
        params = {"$select": "id,subject,receivedDateTime,bodyPreview,body,from,toRecipients,ccRecipients,bccRecipients,conversationId"}
        resp = httpx.get(url, headers=self._graph_headers(), params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
