import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.v1 import telemetry as telemetry_routes
from app.security.auth import AuthenticatedUser
from app.security import auth as auth_module
from app.infra.config import Settings
from app.data.models import UITelemetryEvent


@pytest.fixture
def telemetry_test_client(db_session):
    app = FastAPI()
    app.include_router(telemetry_routes.router, prefix="/v1")

    user = AuthenticatedUser(
        user_id="user-telemetry-1",
        email="telemetry@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={},
    )

    def override_get_current_user():
        return user

    def override_get_db_for_user():
        yield db_session

    app.dependency_overrides[telemetry_routes.get_current_user] = override_get_current_user
    app.dependency_overrides[telemetry_routes.require_admin_user] = override_get_current_user
    app.dependency_overrides[telemetry_routes.get_db_for_user] = override_get_db_for_user
    app.dependency_overrides[telemetry_routes.get_db] = override_get_db_for_user

    with TestClient(app) as client:
        yield client, db_session, user


def test_telemetry_ingest_persists_events(telemetry_test_client):
    client, db, user = telemetry_test_client

    response = client.post(
        "/v1/telemetry/events",
        json={
            "events": [
                {
                    "event_name": "chat_chip_clicked",
                    "event_id": "evt-1",
                    "event_payload": {"chip": "draft_email"},
                    "page_path": "/dashboard/chat",
                    "session_id": "abc",
                },
                {
                    "event_name": "mention_selected",
                    "event_id": "evt-2",
                    "event_payload": {"mention_type": "contact"},
                    "page_path": "/dashboard/chat",
                },
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 2

    rows = db.query(UITelemetryEvent).filter(UITelemetryEvent.user_id == user.user_id).all()
    assert len(rows) == 2
    names = {r.event_name for r in rows}
    assert names == {"chat_chip_clicked", "mention_selected"}


def test_telemetry_ingest_dedupes_by_event_id(telemetry_test_client):
    client, db, user = telemetry_test_client
    payload = {
        "events": [
            {
                "event_id": "evt-dedupe-1",
                "event_name": "chat_chip_clicked",
                "event_payload": {"chip": "draft_email"},
            }
        ]
    }

    first = client.post("/v1/telemetry/events", json=payload)
    second = client.post("/v1/telemetry/events", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["accepted"] == 1
    assert first.json()["deduped"] == 0
    assert second.json()["accepted"] == 0
    assert second.json()["deduped"] == 1

    rows = db.query(UITelemetryEvent).filter(
        UITelemetryEvent.user_id == user.user_id,
        UITelemetryEvent.event_id == "evt-dedupe-1",
    ).all()
    assert len(rows) == 1


def test_telemetry_dashboard_returns_funnel_metrics(telemetry_test_client):
    client, db, user = telemetry_test_client
    db.add_all(
        [
            UITelemetryEvent(user_id=user.user_id, event_name="chat_chip_clicked"),
            UITelemetryEvent(user_id=user.user_id, event_name="chat_chip_clicked"),
            UITelemetryEvent(user_id=user.user_id, event_name="chat_message_sent"),
            UITelemetryEvent(user_id=user.user_id, event_name="chat_action_approved"),
        ]
    )
    db.commit()

    response = client.get("/v1/telemetry/dashboard", params={"days": 7})
    assert response.status_code == 200
    payload = response.json()
    assert payload["funnel"]["chip_clicked"] == 2
    assert payload["funnel"]["message_sent"] == 1
    assert payload["funnel"]["action_approved"] >= 1
    assert payload["funnel"]["click_to_send_rate"] == 0.5


def test_telemetry_dashboard_aggregates_globally_for_admin(telemetry_test_client):
    client, db, user = telemetry_test_client
    db.add_all(
        [
            UITelemetryEvent(user_id=user.user_id, event_name="chat_chip_clicked"),
            UITelemetryEvent(user_id="user-telemetry-2", event_name="chat_chip_clicked"),
            UITelemetryEvent(user_id="user-telemetry-2", event_name="chat_message_sent"),
        ]
    )
    db.commit()

    response = client.get("/v1/telemetry/dashboard", params={"days": 7})
    assert response.status_code == 200
    payload = response.json()
    assert payload["funnel"]["chip_clicked"] == 2
    assert payload["funnel"]["message_sent"] == 1


def test_telemetry_dashboard_denies_non_admin(db_session):
    app = FastAPI()
    app.include_router(telemetry_routes.router, prefix="/v1")

    user = AuthenticatedUser(
        user_id="user-telemetry-3",
        email="non-admin@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={},
    )

    def override_current_user():
        return user

    def override_settings():
        return Settings(ADMIN_EMAILS="admin@example.com")

    def override_get_db_for_user():
        yield db_session

    app.dependency_overrides[auth_module.get_current_user] = override_current_user
    app.dependency_overrides[auth_module.get_settings] = override_settings
    app.dependency_overrides[telemetry_routes.get_db_for_user] = override_get_db_for_user
    app.dependency_overrides[telemetry_routes.get_db] = override_get_db_for_user

    with TestClient(app) as client:
        response = client.get("/v1/telemetry/dashboard", params={"days": 7})
        assert response.status_code == 403
