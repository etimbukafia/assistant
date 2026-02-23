
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from app.data.models import UserSettings, GmailAccount

# Test data
TEST_USER_ID = "test_user_123"
TEST_EMAIL = "test@example.com"

@pytest.fixture
def mock_auth(test_client):
    """Override auth to return a test user."""
    from app.security.auth import get_current_user, AuthenticatedUser
    from app.main import app
    
    def override_user():
        return AuthenticatedUser(
            user_id=TEST_USER_ID,
            email=TEST_EMAIL,
            aud="authenticated",
            iss="supabase",
            sub=TEST_USER_ID
        )
    
    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def mock_settings(db_session):
    """Create basic user settings (no trial active initially)."""
    settings = UserSettings(
        user_id=TEST_USER_ID,
        user_email=TEST_EMAIL,
        trial_ends_at=None, # Deferred trial
        subscription_tier="trial",
        subscription_status="trialing" 
    )
    db_session.add(settings)
    db_session.commit()
    return settings

@pytest.fixture
def mock_gmail(db_session):
    """Create a linked Gmail account."""
    account = GmailAccount(
        user_id=TEST_USER_ID,
        email=TEST_EMAIL,
        access_token="enc_token",
        initial_sync_completed=False
    )
    db_session.add(account)
    db_session.commit()
    return account

@pytest.fixture
def mock_enqueue():
    """Mock the background task logic."""
    # We patch where it is IMPORTED in the router
    with patch("app.routes.v1.sync.enqueue_task") as mock:
        yield mock

def test_activate_trial(test_client, db_session, mock_auth, mock_settings):
    """Test explicit trial activation."""
    # 1. Verify initial state
    assert mock_settings.trial_ends_at is None
    
    # 2. Call activation endpoint
    response = test_client.post("/subscription/activate-trial")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "activated"
    assert data["days_remaining"] == 7
    
    # 3. Verify DB update
    db_session.refresh(mock_settings)
    assert mock_settings.trial_ends_at is not None
    assert mock_settings.trial_ends_at > datetime.now(timezone.utc)

def test_activate_trial_idempotent(test_client, db_session, mock_auth, mock_settings):
    """Test activating already active trial returns 200."""
    # Set active trial
    mock_settings.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=5)
    db_session.commit()
    
    response = test_client.post("/subscription/activate-trial")
    assert response.status_code == 200
    assert response.json()["status"] == "active"

def test_initial_sync_trigger(test_client, db_session, mock_auth, mock_settings, mock_gmail, mock_enqueue):
    """Test triggering initial sync handles feature gating and queuing."""
    # 1. Activate trial (prerequisite for feature access)
    mock_settings.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    db_session.commit()
    
    # 2. Trigger sync
    response = test_client.post("/gmail/sync/initial")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["hours_back"] == 24
    
    # 3. Verify backfill task queued
    mock_enqueue.assert_called_once()
    args, kwargs = mock_enqueue.call_args
    assert args[0] == "email_backfill" # task_name
    payload = args[1]
    assert payload["user_id"] == TEST_USER_ID
    assert payload["hours_back"] == 24

def test_initial_sync_already_done(test_client, db_session, mock_auth, mock_settings, mock_gmail, mock_enqueue):
    """Test idempotent sync request."""
    # 1. Setup
    mock_settings.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    mock_gmail.initial_sync_completed = True
    db_session.commit()
    
    # 2. Trigger sync
    response = test_client.post("/gmail/sync/initial")
    assert response.status_code == 200
    assert response.json()["status"] == "already_completed"
    
    # 3. Verify NOT queued
    mock_enqueue.assert_not_called()

def test_sync_requires_payment(test_client, db_session, mock_auth, mock_settings, mock_gmail):
    """Test sync endpoint requires active trial/sub."""
    # 1. Ensure no trial
    mock_settings.trial_ends_at = None
    mock_settings.subscription_status = "inactive"
    db_session.commit()
    
    # 2. Trigger sync -> Should fail 402
    response = test_client.post("/gmail/sync/initial")
    assert response.status_code == 402
