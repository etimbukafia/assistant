import pytest
from types import SimpleNamespace
from sqlalchemy.orm import sessionmaker

from app.data.models import OutlookAccount, OutlookWatchSubscription, WebhookDelivery, Message
from app.routes.v1 import webhooks as webhooks_module
from app.services.email_filter import FilterAction, FilterResult


class DummyJsonRequest:
    def __init__(self, body: dict, query_params: dict | None = None):
        self._body = body
        self.query_params = query_params or {}

    async def json(self):
        return self._body


@pytest.fixture
def outlook_session_factory(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


def _outlook_notification(sub_id: str, notification_id: str = "note-1") -> dict:
    return {
        "value": [
            {
                "subscriptionId": sub_id,
                "resource": "me/mailFolders('Inbox')/messages",
                "clientState": "secret",
                "id": notification_id,
                "sequenceNumber": 1,
            }
        ]
    }


@pytest.mark.asyncio
async def test_outlook_webhook_validation_token_returns_plain_text():
    req = DummyJsonRequest({}, query_params={"validationToken": "abc123"})
    resp = await webhooks_module.handle_outlook_push(req)
    assert resp.body == b"abc123"
    assert resp.media_type == "text/plain"


@pytest.mark.asyncio
async def test_outlook_webhook_deduplicates_delivery(monkeypatch, outlook_session_factory):
    monkeypatch.setattr(webhooks_module, "SessionLocal", outlook_session_factory)
    monkeypatch.setattr(webhooks_module, "encrypt_body", lambda b: b)

    class FakeOutlookClient:
        calls = 0

        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        def load_credentials(self, email=None):
            return True

        def get_delta_messages(self, _token):
            FakeOutlookClient.calls += 1
            return {
                "value": [
                    {
                        "id": "ms-msg-1",
                        "conversationId": "conv-1",
                        "subject": "Hello",
                        "receivedDateTime": "2026-02-24T12:00:00Z",
                        "body": {"content": "Hi"},
                        "from": {"emailAddress": {"address": "test@example.com"}},
                        "toRecipients": [{"emailAddress": {"address": "ea@example.com"}}],
                    }
                ],
                "@odata.deltaLink": "delta-1",
            }

    monkeypatch.setattr(webhooks_module, "OutlookClient", FakeOutlookClient)

    def _always_process(self, *args, **kwargs):
        return FilterResult(action=FilterAction.PROCESS)

    monkeypatch.setattr(webhooks_module.EmailFilterService, "apply_filters", _always_process)

    setup_db = outlook_session_factory()
    setup_db.add(
        OutlookAccount(
            email="ea@example.com",
            user_id="user-1",
            access_token="enc-token",
            refresh_token="enc-refresh",
        )
    )
    setup_db.add(
        OutlookWatchSubscription(
            user_id="user-1",
            subscription_id="sub-1",
            resource="me/mailFolders('Inbox')/messages",
            client_state="secret",
        )
    )
    setup_db.commit()
    setup_db.close()

    first = await webhooks_module.handle_outlook_push(
        DummyJsonRequest(_outlook_notification("sub-1", "note-1"))
    )
    second = await webhooks_module.handle_outlook_push(
        DummyJsonRequest(_outlook_notification("sub-1", "note-1"))
    )

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert FakeOutlookClient.calls == 1

    check_db = outlook_session_factory()
    delivery = check_db.query(WebhookDelivery).filter(WebhookDelivery.source == "outlook").first()
    assert delivery is not None
    message = check_db.query(Message).filter(Message.provider == "microsoft").first()
    assert message is not None
    check_db.close()
