from datetime import datetime, timezone

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from app.data.models import Contact
from app.routes.v1 import contacts as contacts_routes
from app.security.auth import AuthenticatedUser


@pytest.fixture
def contacts_test_client(db_session):
    app = fastapi.FastAPI()
    app.include_router(contacts_routes.router, prefix="/v1")

    user = AuthenticatedUser(
        user_id="user-123",
        email="test@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={"full_name": "Contact Tester"},
    )

    def override_get_current_user():
        return user

    def override_get_db_for_user():
        yield db_session

    app.dependency_overrides[contacts_routes.get_current_user] = override_get_current_user
    app.dependency_overrides[contacts_routes.get_db_for_user] = override_get_db_for_user

    with TestClient(app) as client:
        yield client, db_session, user


def test_contact_brief_route_returns_brief(contacts_test_client):
    client, db, user = contacts_test_client
    contact = Contact(
        user_id=user.user_id,
        name="Sarah Chen",
        email="sarah@example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    response = client.get(f"/v1/contacts/{contact.id}/brief")
    assert response.status_code == 200
    payload = response.json()
    assert payload["contact"]["id"] == contact.id
    assert payload["contact"]["email"] == "sarah@example.com"


def test_contact_brief_route_returns_404_for_missing_contact(contacts_test_client):
    client, _, _ = contacts_test_client
    response = client.get("/v1/contacts/99999/brief")
    assert response.status_code == 404
