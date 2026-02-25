"""
Integration Tests for Gmail Webhook Endpoint (POST /v1/webhooks/gmail)

Tests webhook security, payload validation, delivery deduplication,
history cursor behavior, error handling, and audit logging.

Uses in-memory SQLite via the shared db_engine fixture.
"""

import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.data.models import GmailAccount, WebhookDelivery, WebhookLog
from app.routes.v1 import webhooks as webhooks_module
from app.services.email_filter import FilterAction

pytestmark = pytest.mark.integration


# =============================================================================
# Helpers
# =============================================================================

class DummyRequest:
    """Minimal request stub that satisfies handle_gmail_push."""

    def __init__(self, body, *, headers=None, query_params=None, raise_on_json=False):
        self._body = body
        self._raise_on_json = raise_on_json
        self.headers = headers or {}
        self.query_params = query_params or {}

    async def json(self):
        if self._raise_on_json:
            raise ValueError("malformed json")
        return self._body


def _pubsub_body(
    email: str,
    history_id: str,
    message_id: str = "msg-1",
    subscription: str = "projects/test/subscriptions/gmail-push",
) -> dict:
    """Build a well-formed Pub/Sub push body."""
    payload = {"emailAddress": email, "historyId": history_id}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return {
        "message": {
            "data": encoded,
            "messageId": message_id,
            "publishTime": "2026-02-24T12:00:00Z",
        },
        "subscription": subscription,
    }


def _settings_with_token(token="test-token", subscription="") -> SimpleNamespace:
    return SimpleNamespace(
        GMAIL_PUBSUB_SUBSCRIPTION=subscription,
        GMAIL_WEBHOOK_TOKEN=token,
        GMAIL_WEBHOOK_REQUIRE_AUTH=False,
        GMAIL_WEBHOOK_AUDIENCE="",
        GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT="",
        API_URL="http://localhost:8000",
    )


def _authed_headers(token="test-token") -> dict:
    return {"X-Webhook-Token": token}


class StubGmailClient:
    """GmailClient replacement that returns no new messages."""

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id

    def get_new_message_ids(self, _history_id):
        return [], "500"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture
def seed_account(session_factory):
    """Insert a GmailAccount and return a helper to query it back."""

    def _seed(email="user@example.com", user_id="user-1", last_history_id="100"):
        db = session_factory()
        db.add(
            GmailAccount(
                email=email,
                user_id=user_id,
                access_token="enc-tok",
                refresh_token="enc-ref",
                last_history_id=last_history_id,
            )
        )
        db.commit()
        db.close()

    return _seed


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch, session_factory):
    """Wire the webhook module to use in-memory SQLite and the token settings."""
    monkeypatch.setattr(webhooks_module, "SessionLocal", session_factory)
    monkeypatch.setattr(webhooks_module, "get_settings", _settings_with_token)
    monkeypatch.setattr(webhooks_module, "GmailClient", StubGmailClient)


# =============================================================================
# 1. Auth / Security
# =============================================================================

class TestGmailWebhookAuth:

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self):
        """Unauthorized request (missing token) returns 401."""
        body = _pubsub_body("a@b.com", "100")
        req = DummyRequest(body, headers={})

        with pytest.raises(HTTPException) as exc:
            await webhooks_module.handle_gmail_push(req)

        assert exc.value.status_code == 401
        assert exc.value.detail == "unauthorized_webhook_source"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        """Unauthorized request (wrong token) returns 401."""
        body = _pubsub_body("a@b.com", "100")
        req = DummyRequest(body, headers={"X-Webhook-Token": "wrong-token"})

        with pytest.raises(HTTPException) as exc:
            await webhooks_module.handle_gmail_push(req)

        assert exc.value.status_code == 401
        assert exc.value.detail == "unauthorized_webhook_source"

    @pytest.mark.asyncio
    async def test_subscription_mismatch_returns_401(self, monkeypatch):
        """If GMAIL_PUBSUB_SUBSCRIPTION is set and doesn't match, reject with 401."""
        monkeypatch.setattr(
            webhooks_module,
            "get_settings",
            lambda: _settings_with_token(
                token="test-token",
                subscription="projects/prod/subscriptions/gmail-push",
            ),
        )
        body = _pubsub_body(
            "a@b.com", "100",
            subscription="projects/OTHER/subscriptions/gmail-push",
        )
        req = DummyRequest(body, headers=_authed_headers())

        with pytest.raises(HTTPException) as exc:
            await webhooks_module.handle_gmail_push(req)

        assert exc.value.status_code == 401
        assert exc.value.detail == "unauthorized_webhook_source"


# =============================================================================
# 2. Payload Validation
# =============================================================================

class TestGmailWebhookPayloadValidation:

    @pytest.mark.asyncio
    async def test_malformed_json_returns_ignored(self, monkeypatch):
        """Malformed JSON body returns 200 with reason=invalid_json."""
        # Suppress the audit log since it opens its own session.
        monkeypatch.setattr(webhooks_module, "_log_webhook_event", lambda *a, **kw: None)

        req = DummyRequest(None, headers=_authed_headers(), raise_on_json=True)
        result = await webhooks_module.handle_gmail_push(req)

        assert result == {"status": "ignored", "reason": "invalid_json"}

    @pytest.mark.asyncio
    async def test_missing_message_data_returns_ignored(self, monkeypatch):
        """Missing Pub/Sub message.data returns 200 with reason=no_data."""
        monkeypatch.setattr(webhooks_module, "_log_webhook_event", lambda *a, **kw: None)

        body = {"message": {"messageId": "m-1"}, "subscription": "x"}
        req = DummyRequest(body, headers=_authed_headers())
        result = await webhooks_module.handle_gmail_push(req)

        assert result == {"status": "ignored", "reason": "no_data"}

    @pytest.mark.asyncio
    async def test_invalid_base64_returns_ignored(self, monkeypatch):
        """Invalid base64 payload returns 200 with reason=decode_failed."""
        monkeypatch.setattr(webhooks_module, "_log_webhook_event", lambda *a, **kw: None)

        body = {
            "message": {"data": "%%%NOT_BASE64%%%", "messageId": "m-1"},
            "subscription": "x",
        }
        req = DummyRequest(body, headers=_authed_headers())
        result = await webhooks_module.handle_gmail_push(req)

        assert result == {"status": "ignored", "reason": "decode_failed"}

    @pytest.mark.asyncio
    async def test_missing_email_in_payload_returns_ignored(self, monkeypatch):
        """Missing emailAddress in decoded payload returns 200 with reason=no_email."""
        monkeypatch.setattr(webhooks_module, "_log_webhook_event", lambda *a, **kw: None)

        # Encode a payload that has historyId but no emailAddress.
        payload = {"historyId": "999"}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        body = {
            "message": {"data": encoded, "messageId": "m-1"},
            "subscription": "x",
        }
        req = DummyRequest(body, headers=_authed_headers())
        result = await webhooks_module.handle_gmail_push(req)

        assert result == {"status": "ignored", "reason": "no_email"}


# =============================================================================
# 3. Account Lookup
# =============================================================================

class TestGmailWebhookAccountLookup:

    @pytest.mark.asyncio
    async def test_unknown_account_returns_ignored(self):
        """emailAddress not linked to any account returns reason=unknown_account."""
        body = _pubsub_body("nobody@example.com", "100", message_id="unk-1")
        req = DummyRequest(body, headers=_authed_headers())
        result = await webhooks_module.handle_gmail_push(req)

        assert result == {"status": "ignored", "reason": "unknown_account"}


# =============================================================================
# 4. Deduplication
# =============================================================================

class TestGmailWebhookDeduplication:

    @pytest.mark.asyncio
    async def test_duplicate_message_id_is_idempotent(self, seed_account):
        """Duplicate Pub/Sub messageId returns {status: 'duplicate'}."""
        seed_account(email="dup@example.com", user_id="u-dup", last_history_id="100")

        body = _pubsub_body("dup@example.com", "105", message_id="dup-mid-1")
        headers = _authed_headers()

        first = await webhooks_module.handle_gmail_push(DummyRequest(body, headers=headers))
        second = await webhooks_module.handle_gmail_push(DummyRequest(body, headers=headers))

        assert first["status"] == "ok"
        assert second["status"] == "duplicate"


# =============================================================================
# 5. History Cursor Initialization
# =============================================================================

class TestGmailWebhookCursorInit:

    @pytest.mark.asyncio
    async def test_first_webhook_initializes_cursor(self, session_factory):
        """First webhook for an account with empty last_history_id initializes cursor."""
        db = session_factory()
        db.add(
            GmailAccount(
                email="new@example.com",
                user_id="u-new",
                access_token="enc",
                refresh_token="enc",
                last_history_id=None,  # empty cursor
            )
        )
        db.commit()
        db.close()

        body = _pubsub_body("new@example.com", "42", message_id="init-1")
        result = await webhooks_module.handle_gmail_push(
            DummyRequest(body, headers=_authed_headers())
        )

        assert result["status"] == "initialized"
        assert result["history_id"] == "42"

        # Verify cursor was persisted.
        check = session_factory()
        acct = check.query(GmailAccount).filter(GmailAccount.email == "new@example.com").first()
        assert acct.last_history_id == "42"
        check.close()


# =============================================================================
# 6. No New Messages
# =============================================================================

class TestGmailWebhookNoNewMessages:

    @pytest.mark.asyncio
    async def test_no_new_messages_returns_zero(self, seed_account):
        """Webhook with no new messages returns {status: 'ok', new_messages: 0}."""
        seed_account(email="quiet@example.com", user_id="u-quiet", last_history_id="200")

        body = _pubsub_body("quiet@example.com", "210", message_id="quiet-1")
        result = await webhooks_module.handle_gmail_push(
            DummyRequest(body, headers=_authed_headers())
        )

        assert result["status"] == "ok"
        assert result["new_messages"] == 0


# =============================================================================
# 7. Monotonic History Cursor
# =============================================================================

class TestGmailWebhookMonotonicCursor:

    @pytest.mark.asyncio
    async def test_history_id_never_regresses(self, seed_account, session_factory):
        """last_history_id never regresses when out-of-order historyId is received."""
        seed_account(email="mono@example.com", user_id="u-mono", last_history_id="500")

        # Notification carries an older historyId; GmailClient also returns older.
        body = _pubsub_body("mono@example.com", "300", message_id="mono-1")
        await webhooks_module.handle_gmail_push(
            DummyRequest(body, headers=_authed_headers())
        )

        check = session_factory()
        acct = check.query(GmailAccount).filter(GmailAccount.email == "mono@example.com").first()
        assert acct.last_history_id == "500"
        check.close()


# =============================================================================
# 8. Processing Failure
# =============================================================================

class TestGmailWebhookProcessingFailure:

    @pytest.mark.asyncio
    async def test_processing_failure_returns_generic_500(self, monkeypatch, seed_account):
        """Processing failures return 500 with generic detail (no leak)."""
        seed_account(email="err@example.com", user_id="u-err", last_history_id="100")

        class BrokenGmailClient:
            def __init__(self, db, user_id):
                pass

            def get_new_message_ids(self, _):
                raise RuntimeError("internal secret stack trace")

        monkeypatch.setattr(webhooks_module, "GmailClient", BrokenGmailClient)
        monkeypatch.setattr(webhooks_module, "_log_webhook_event", lambda *a, **kw: None)

        body = _pubsub_body("err@example.com", "110", message_id="err-1")
        with pytest.raises(HTTPException) as exc:
            await webhooks_module.handle_gmail_push(
                DummyRequest(body, headers=_authed_headers())
            )

        assert exc.value.status_code == 500
        assert exc.value.detail == "gmail_webhook_processing_failed"
        # Ensure internal details are NOT in the detail string.
        assert "secret" not in exc.value.detail


# =============================================================================
# 9. Webhook Delivery Persistence
# =============================================================================

class TestGmailWebhookDeliveryPersistence:

    @pytest.mark.asyncio
    async def test_successful_processing_records_delivery(self, seed_account, session_factory):
        """Successful processing inserts a row in webhook_deliveries for source=gmail."""
        seed_account(email="ok@example.com", user_id="u-ok", last_history_id="100")

        body = _pubsub_body("ok@example.com", "110", message_id="persist-1")
        result = await webhooks_module.handle_gmail_push(
            DummyRequest(body, headers=_authed_headers())
        )
        assert result["status"] == "ok"

        db = session_factory()
        delivery = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.source == "gmail",
                WebhookDelivery.delivery_id == "persist-1",
            )
            .first()
        )
        assert delivery is not None
        assert delivery.event_type == "gmail_push"
        assert delivery.customer_id == "ok@example.com"
        db.close()

    @pytest.mark.asyncio
    async def test_initialized_cursor_records_delivery(self, session_factory):
        """Cursor initialization also records a delivery row."""
        db = session_factory()
        db.add(
            GmailAccount(
                email="init2@example.com",
                user_id="u-init2",
                access_token="enc",
                refresh_token="enc",
                last_history_id=None,
            )
        )
        db.commit()
        db.close()

        body = _pubsub_body("init2@example.com", "10", message_id="init-del-1")
        result = await webhooks_module.handle_gmail_push(
            DummyRequest(body, headers=_authed_headers())
        )
        assert result["status"] == "initialized"

        db = session_factory()
        delivery = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.source == "gmail",
                WebhookDelivery.delivery_id == "init-del-1",
            )
            .first()
        )
        assert delivery is not None
        db.close()


# =============================================================================
# 10. Webhook Audit Log
# =============================================================================

class TestGmailWebhookAuditLog:
    """
    _log_webhook_event opens its own SessionLocal() connection.  With
    in-memory SQLite each connection gets a separate database, so we
    spy on the function call instead of querying the log table.
    """

    @pytest.mark.asyncio
    async def test_successful_processing_writes_audit_log(self, monkeypatch, seed_account):
        """webhook_logs includes source=gmail, event_type=gmail_push, processed=True.

        The audit log on success is only written when the full message-processing
        path runs (not the early "no new messages" return), so we need a stub
        that returns at least one message.
        """
        seed_account(email="log@example.com", user_id="u-log", last_history_id="100")

        class OneMessageGmailClient:
            def __init__(self, db, user_id):
                pass

            def get_new_message_ids(self, _history_id):
                return ["gmail-msg-abc"], "120"

            def get_message_detail(self, msg_id):
                return {
                    "message_id": msg_id,
                    "thread_id": "thread-1",
                    "sender": "alice@example.com",
                    "recipient": "log@example.com",
                    "subject": "Hello",
                    "body": "Test body",
                    "received_at": "2026-02-24T12:00:00Z",
                }

        monkeypatch.setattr(webhooks_module, "GmailClient", OneMessageGmailClient)
        monkeypatch.setattr(webhooks_module, "encrypt_body", lambda b: b)
        monkeypatch.setattr(
            webhooks_module,
            "EmailFilterService",
            lambda db, user_id: SimpleNamespace(
                apply_filters=lambda **kw: SimpleNamespace(action=FilterAction.SKIP),
            ),
        )

        log_calls = []
        monkeypatch.setattr(
            webhooks_module,
            "_log_webhook_event",
            lambda *a, **kw: log_calls.append((a, kw)),
        )

        body = _pubsub_body("log@example.com", "110", message_id="log-1")
        result = await webhooks_module.handle_gmail_push(
            DummyRequest(body, headers=_authed_headers())
        )
        assert result["status"] == "ok"

        assert len(log_calls) == 1
        args, kwargs = log_calls[0]
        assert args == ("gmail", "gmail_push", True)
        assert kwargs.get("customer_id") == "log@example.com"

    @pytest.mark.asyncio
    async def test_invalid_json_writes_error_audit_log(self, monkeypatch):
        """Malformed JSON logs an error entry in webhook_logs."""
        calls = []
        monkeypatch.setattr(
            webhooks_module,
            "_log_webhook_event",
            lambda *a, **kw: calls.append((a, kw)),
        )

        req = DummyRequest(None, headers=_authed_headers(), raise_on_json=True)
        await webhooks_module.handle_gmail_push(req)

        assert len(calls) == 1
        args, _ = calls[0]
        assert args == ("gmail", "gmail_push", False, "invalid_json")
