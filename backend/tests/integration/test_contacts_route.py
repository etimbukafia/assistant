from datetime import datetime, timezone

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from app.data.models import Contact
from app.routes.v1 import contacts as contacts_routes
from app.security.auth import AuthenticatedUser


@pytest.fixture
def contacts_crud_client(db_session):
    app = fastapi.FastAPI()
    app.include_router(contacts_routes.router, prefix="/v1")

    user = AuthenticatedUser(
        user_id="user-contacts-1",
        email="test@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={"full_name": "Contact Tester"},
    )

    def override_get_current_user():
        return user

    def override_require_active_subscription():
        return user

    def override_get_db_for_user():
        yield db_session

    app.dependency_overrides[contacts_routes.get_current_user] = override_get_current_user
    app.dependency_overrides[contacts_routes.require_active_subscription] = override_require_active_subscription
    app.dependency_overrides[contacts_routes.get_db_for_user] = override_get_db_for_user

    with TestClient(app) as client:
        yield client, db_session, user


def test_contacts_list_returns_contact_collection(contacts_crud_client):
    client, db, user = contacts_crud_client
    db.add(
        Contact(
            user_id=user.user_id,
            name="Sarah Chen",
            email="sarah@example.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = client.get("/v1/contacts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["contacts"][0]["email"] == "sarah@example.com"


def test_contacts_crud_round_trip(contacts_crud_client):
    client, _, _ = contacts_crud_client

    create_response = client.post(
        "/v1/contacts",
        json={
            "name": "Jordan Lee",
            "email": "jordan@example.com",
            "role": "Chief of Staff",
            "organization": "Acme",
            "category": "vip",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()

    get_response = client.get(f"/v1/contacts/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Jordan Lee"

    update_response = client.put(
        f"/v1/contacts/{created['id']}",
        json={"name": "Jordan Lee", "category": "external"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["category"] == "external"

    lookup_response = client.post("/v1/contacts/lookup", json={"email": "jordan@example.com"})
    assert lookup_response.status_code == 200
    assert lookup_response.json()["id"] == created["id"]

    delete_response = client.delete(f"/v1/contacts/{created['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True, "id": created["id"]}
