import pytest

from app.data.models import UserSettings, OutlookAccount

TEST_USER_ID = "test_user_456"
TEST_EMAIL = "test_outlook@example.com"


@pytest.fixture
def mock_auth(test_client):
    from app.security.auth import get_current_user, AuthenticatedUser
    from app.main import app

    def override_user():
        return AuthenticatedUser(
            user_id=TEST_USER_ID,
            email=TEST_EMAIL,
            aud="authenticated",
            iss="supabase",
            sub=TEST_USER_ID,
        )

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_disconnect_provider_defaults_to_current(test_client, db_session, mock_auth):
    settings = UserSettings(
        user_id=TEST_USER_ID,
        user_email=TEST_EMAIL,
        connected_provider="microsoft",
    )
    db_session.add(settings)
    db_session.add(
        OutlookAccount(
            user_id=TEST_USER_ID,
            email=TEST_EMAIL,
            access_token="enc-token",
        )
    )
    db_session.commit()

    resp = test_client.post("/auth/provider/disconnect", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"

    db_session.refresh(settings)
    assert settings.connected_provider == "none"
    account = db_session.query(OutlookAccount).filter(OutlookAccount.user_id == TEST_USER_ID).first()
    assert account is None
