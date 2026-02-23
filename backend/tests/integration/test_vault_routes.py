from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.data.models import VaultProposal, VaultNote, Message
from app.routes.v1 import vault as vault_routes
from app.security.auth import AuthenticatedUser


@pytest.fixture
def vault_test_client(db_session):
    app = FastAPI()
    app.include_router(vault_routes.router, prefix="/v1")

    user = AuthenticatedUser(
        user_id="user-123",
        email="test@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={"full_name": "Vault Tester"},
    )

    def override_get_current_user():
        return user

    def override_require_active_subscription():
        return user

    def override_get_db_for_user():
        yield db_session

    app.dependency_overrides[vault_routes.get_current_user] = override_get_current_user
    app.dependency_overrides[vault_routes.require_active_subscription] = override_require_active_subscription
    app.dependency_overrides[vault_routes.get_db_for_user] = override_get_db_for_user

    with TestClient(app) as client:
        yield client, db_session, user


def test_vault_create_and_list_notes(vault_test_client):
    client, _, _ = vault_test_client

    create_response = client.post(
        "/v1/vault/notes",
        json={
            "note_type": "decision",
            "title": "Q2 roadmap approved",
            "body": "Team agreed to focus on onboarding first.",
            "frontmatter": {"source": "meeting"},
        },
    )
    assert create_response.status_code == 200
    note = create_response.json()
    assert note["title"] == "Q2 roadmap approved"

    list_response = client.get("/v1/vault/notes")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    assert any(n["title"] == "Q2 roadmap approved" for n in payload["notes"])


def test_vault_approve_proposal_creates_note(vault_test_client):
    client, db, user = vault_test_client
    proposal = VaultProposal(
        user_id=user.user_id,
        proposal_type="create_note",
        proposed_data={
            "note_type": "commitment",
            "title": "Send pricing draft by Friday",
            "body": "Owner: Teeks. Due: Friday EOD.",
            "frontmatter": {"source": "email"},
        },
        diff_summary="Add commitment note",
        source_type="email_processing",
        source_id="thread-999",
        confidence=0.82,
        status="pending",
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    with patch("app.routes.v1.vault.PatternTracker") as tracker_cls:
        tracker_cls.return_value.track_action.return_value = None
        response = client.post(f"/v1/vault/proposals/{proposal.id}/approve")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["target_note_id"] is not None

    created_note = db.query(VaultNote).filter(VaultNote.id == data["target_note_id"]).first()
    assert created_note is not None
    assert created_note.title == "Send pricing draft by Friday"


def test_vault_emails_mentionable_filters(vault_test_client):
    client, db, user = vault_test_client
    db.add_all(
        [
            Message(
                message_id="msg-1",
                thread_id="thread-a",
                user_id=user.user_id,
                subject="Q1 strategic review",
                sender="alex@example.com",
                recipient="user@example.com",
                body="Body 1",
                received_at=datetime.now(timezone.utc),
            ),
            Message(
                message_id="msg-2",
                thread_id="thread-b",
                user_id=user.user_id,
                subject="Dinner plans",
                sender="friend@example.com",
                recipient="user@example.com",
                body="Body 2",
                received_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()

    response = client.get("/v1/vault/emails/mentionable", params={"q": "strategic"})
    assert response.status_code == 200
    emails = response.json()["emails"]
    assert len(emails) == 1
    assert emails[0]["subject"] == "Q1 strategic review"
    assert emails[0]["message_id"] is not None


def test_vault_notes_mentionable_filters(vault_test_client):
    client, _, _ = vault_test_client
    client.post(
        "/v1/vault/notes",
        json={
            "note_type": "project",
            "title": "Q2 Roadmap",
            "body": "Milestones and risks for roadmap execution.",
            "frontmatter": {"source": "manual"},
        },
    )
    client.post(
        "/v1/vault/notes",
        json={
            "note_type": "meeting",
            "title": "Finance Weekly",
            "body": "Weekly updates.",
            "frontmatter": {"source": "manual"},
        },
    )
    response = client.get("/v1/vault/notes/mentionable", params={"q": "roadmap"})
    assert response.status_code == 200
    notes = response.json()["notes"]
    assert len(notes) == 1
    assert notes[0]["title"] == "Q2 Roadmap"
    assert notes[0]["label"].startswith("@knowledge/")
