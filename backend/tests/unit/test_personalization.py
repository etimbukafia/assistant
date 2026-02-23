
import pytest
from datetime import datetime, timezone, timedelta
from app.data.models import UserSettings

def test_user_settings_defaults():
    """Test defaults for new fields."""
    user = UserSettings(user_id="test", user_email="test@test.com")
    assert user.assistant_name == "Donna"
    assert user.onboarding_completed is False

def test_user_settings_custom_name():
    """Test setting custom assistant name."""
    user = UserSettings(
        user_id="test", 
        user_email="test@test.com",
        assistant_name="Jarvis",
        onboarding_completed=True
    )
    assert user.assistant_name == "Jarvis"
    assert user.onboarding_completed is True

def test_onboarding_completed_flag():
    """Test onboarding flag behavior."""
    user = UserSettings(user_id="test", user_email="test@test.com")
    assert not user.onboarding_completed
    
    user.onboarding_completed = True
    assert user.onboarding_completed
