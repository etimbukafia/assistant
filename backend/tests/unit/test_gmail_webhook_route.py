import os
import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.data.models import GmailAccount
from app.routes.v1 import webhooks as webhooks_module


class DummyJsonRequest:
    def __init__(self, body: dict, headers: dict | None = None, query_params: dict | None = None):
        self._body = body
        self.headers = headers or {}
        self.query_params = query_params or {}

    async def json(self):
        return self._body


def _pubsub_body(email: str, history_id: str, message_id: str = "msg-1") -> dict:
    payload = {"emailAddress": email, "historyId": history_id}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return {
        "message": {
            "data": encoded,
            "messageId": message_id,
            "publishTime": "2026-02-23T12:00:00Z",
        },
        "subscription": "projects/test/subscriptions/gmail-notifications",
    }


@pytest.fixture
def gmail_session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


def _token_settings() -> SimpleNamespace:
    return SimpleNamespace(
        GMAIL_PUBSUB_SUBSCRIPTION="",
        GMAIL_WEBHOOK_TOKEN="test-token",
        GMAIL_WEBHOOK_REQUIRE_AUTH=False,
        GMAIL_WEBHOOK_AUDIENCE="",
        GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT="",
        API_URL="http://localhost:8000",
    )


@pytest.mark.asyncio
async def test_gmail_webhook_rejects_unauthorized_source(monkeypatch):
    monkeypatch.setattr(webhooks_module, "get_settings", _token_settings)

    request = DummyJsonRequest(_pubsub_body("ea@example.com", "100"), headers={})
    with pytest.raises(HTTPException) as exc_info:
        await webhooks_module.handle_gmail_push(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "unauthorized_webhook_source"


@pytest.mark.asyncio
async def test_gmail_webhook_deduplicates_delivery(monkeypatch, gmail_session_factory):
    monkeypatch.setattr(webhooks_module, "SessionLocal", gmail_session_factory)
    monkeypatch.setattr(webhooks_module, "get_settings", _token_settings)

    class FakeGmailClient:
        calls = 0

        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def get_new_message_ids(self, _history_id):
            FakeGmailClient.calls += 1
            return [], "110"

    monkeypatch.setattr(webhooks_module, "GmailClient", FakeGmailClient)

    setup_db = gmail_session_factory()
    setup_db.add(
        GmailAccount(
            email="ea@example.com",
            user_id="user-1",
            access_token="encrypted-token",
            refresh_token="encrypted-refresh",
            last_history_id="100",
        )
    )
    setup_db.commit()
    setup_db.close()

    headers = {"X-Webhook-Token": "test-token"}
    body = _pubsub_body("ea@example.com", "105", message_id="dup-mid-1")

    first = await webhooks_module.handle_gmail_push(DummyJsonRequest(body, headers=headers))
    second = await webhooks_module.handle_gmail_push(DummyJsonRequest(body, headers=headers))

    assert first["status"] == "ok"
    assert second["status"] == "duplicate"
    assert FakeGmailClient.calls == 1


@pytest.mark.asyncio
async def test_gmail_webhook_processing_failure_returns_generic_500(monkeypatch, gmail_session_factory):
    monkeypatch.setattr(webhooks_module, "SessionLocal", gmail_session_factory)
    monkeypatch.setattr(webhooks_module, "get_settings", _token_settings)

    class FailingGmailClient:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def get_new_message_ids(self, _history_id):
            raise RuntimeError("internal stack trace: secret")

    monkeypatch.setattr(webhooks_module, "GmailClient", FailingGmailClient)

    setup_db = gmail_session_factory()
    setup_db.add(
        GmailAccount(
            email="ea@example.com",
            user_id="user-1",
            access_token="encrypted-token",
            refresh_token="encrypted-refresh",
            last_history_id="100",
        )
    )
    setup_db.commit()
    setup_db.close()

    headers = {"X-Webhook-Token": "test-token"}
    with pytest.raises(HTTPException) as exc_info:
        await webhooks_module.handle_gmail_push(
            DummyJsonRequest(_pubsub_body("ea@example.com", "101", message_id="err-mid-1"), headers=headers)
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "gmail_webhook_processing_failed"


@pytest.mark.asyncio
async def test_gmail_webhook_history_id_is_monotonic(monkeypatch, gmail_session_factory):
    monkeypatch.setattr(webhooks_module, "SessionLocal", gmail_session_factory)
    monkeypatch.setattr(webhooks_module, "get_settings", _token_settings)

    class FakeGmailClient:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def get_new_message_ids(self, _history_id):
            # Return older history than current cursor.
            return [], "180"

    monkeypatch.setattr(webhooks_module, "GmailClient", FakeGmailClient)

    setup_db = gmail_session_factory()
    setup_db.add(
        GmailAccount(
            email="ea@example.com",
            user_id="user-1",
            access_token="encrypted-token",
            refresh_token="encrypted-refresh",
            last_history_id="200",
        )
    )
    setup_db.commit()
    setup_db.close()

    headers = {"X-Webhook-Token": "test-token"}
    await webhooks_module.handle_gmail_push(
        DummyJsonRequest(_pubsub_body("ea@example.com", "150", message_id="mono-mid-1"), headers=headers)
    )

    check_db = gmail_session_factory()
    account = check_db.query(GmailAccount).filter(GmailAccount.email == "ea@example.com").first()
    assert account.last_history_id == "200"
    check_db.close()
