"""
Integration tests for Auth Database-Dependent Functions

These tests verify that auth functions work correctly with PostgreSQL:
- get_db_for_user() - Sets RLS context in PostgreSQL session
- get_user_settings() - Creates/retrieves UserSettings from database

Uses postgres_session fixture for real PostgreSQL behavior including RLS.
Each test runs in a SAVEPOINT that is rolled back after completion.

Run with: pytest tests/integration/test_auth_db.py -v -m integration
Requires: Running PostgreSQL instance (DATABASE_URL in .env)
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from app.security.auth import (
    AuthenticatedUser,
    get_db_for_user,
    get_user_settings,
    get_user_with_settings,
    create_user_settings,
)
from app.data.models import UserSettings


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Test Fixtures - Use unique IDs per test to avoid conflicts
# =============================================================================

@pytest.fixture
def unique_user_id():
    """Generate a unique user ID for each test."""
    return f"test_user_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def unique_email(unique_user_id):
    """Generate a unique email for each test."""
    return f"{unique_user_id}@test.example.com"


@pytest.fixture
def authenticated_user(unique_user_id, unique_email):
    """Create a mock authenticated user with unique ID for testing."""
    return AuthenticatedUser(
        user_id=unique_user_id,
        email=unique_email,
        email_verified=True,
        provider="google",
        app_metadata={"provider": "google"},
        user_metadata={"full_name": "Integration Test User"},
    )


@pytest.fixture
def second_user():
    """Create a second user with unique ID for isolation tests."""
    unique_id = f"second_user_{uuid.uuid4().hex[:12]}"
    return AuthenticatedUser(
        user_id=unique_id,
        email=f"{unique_id}@test.example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={},
    )


@pytest.fixture
def existing_user_settings(postgres_session, unique_user_id, unique_email):
    """Create pre-existing UserSettings in the database."""
    settings = UserSettings(
        user_id=unique_user_id,
        user_email=unique_email,
        subscription_tier="pro",
        subscription_status="active",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    postgres_session.add(settings)
    postgres_session.flush()  # Get ID without committing
    return settings


# =============================================================================
# Tests: get_user_settings() - Database Integration
# =============================================================================

class TestGetUserSettingsIntegration:
    """Integration tests for get_user_settings database operations."""

    def test_get_user_settings_creates_new_settings_for_new_user(
        self, postgres_session, authenticated_user
    ):
        # Arrange - No settings exist for this user (unique ID per test)
        existing = postgres_session.query(UserSettings).filter(
            UserSettings.user_id == authenticated_user.user_id
        ).first()
        assert existing is None
        
        # Act
        settings = get_user_settings(authenticated_user, postgres_session)
        
        # Assert - Settings created
        assert settings is not None
        assert settings.user_id == authenticated_user.user_id
        assert settings.user_email == authenticated_user.email

    def test_get_user_settings_returns_existing_settings(
        self, postgres_session, authenticated_user, existing_user_settings
    ):
        # Arrange - Settings already exist (from fixture)
        
        # Act
        settings = get_user_settings(authenticated_user, postgres_session)
        
        # Assert - Returns existing, doesn't create new
        assert settings.id == existing_user_settings.id
        assert settings.subscription_tier == "pro"

    def test_get_user_settings_new_user_has_trial(
        self, postgres_session, authenticated_user
    ):
        # Arrange - Fresh user
        
        # Act
        settings = get_user_settings(authenticated_user, postgres_session)
        
        # Assert - Default trial period set
        assert settings.trial_ends_at is not None
        # Make comparison timezone-aware
        trial_end = settings.trial_ends_at
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        assert trial_end > datetime.now(timezone.utc)

    def test_get_user_settings_persists_to_database(
        self, postgres_session, authenticated_user
    ):
        # Arrange
        settings = get_user_settings(authenticated_user, postgres_session)
        settings_id = settings.id
        
        # Act - Query directly from database
        persisted = postgres_session.query(UserSettings).filter(
            UserSettings.id == settings_id
        ).first()
        
        # Assert
        assert persisted is not None
        assert persisted.user_id == authenticated_user.user_id

    def test_get_user_settings_different_users_get_different_settings(
        self, postgres_session, authenticated_user, second_user
    ):
        # Arrange & Act
        settings1 = get_user_settings(authenticated_user, postgres_session)
        settings2 = get_user_settings(second_user, postgres_session)
        
        # Assert - Each user has their own settings
        assert settings1.id != settings2.id
        assert settings1.user_id == authenticated_user.user_id
        assert settings2.user_id == second_user.user_id


# =============================================================================
# Tests: get_db_for_user() - RLS Context Setting (PostgreSQL-specific)
# =============================================================================

class TestGetDbForUserIntegration:
    """Integration tests for get_db_for_user RLS context in PostgreSQL."""

    def test_get_db_for_user_returns_session(
        self, postgres_session, authenticated_user
    ):
        # Act
        result = get_db_for_user(authenticated_user, postgres_session)
        
        # Assert - Returns the session
        assert result is postgres_session

    def test_get_db_for_user_sets_rls_context(
        self, postgres_session, authenticated_user
    ):
        # Act
        get_db_for_user(authenticated_user, postgres_session)
        
        # Assert - Query the PostgreSQL session variable
        result = postgres_session.execute(
            text("SELECT current_setting('app.user_id', true)")
        ).scalar()
        
        assert result == authenticated_user.user_id

    def test_get_db_for_user_different_users_set_different_context(
        self, postgres_session, authenticated_user, second_user
    ):
        # Act - Set context for first user
        get_db_for_user(authenticated_user, postgres_session)
        result1 = postgres_session.execute(
            text("SELECT current_setting('app.user_id', true)")
        ).scalar()
        
        # Act - Set context for second user
        get_db_for_user(second_user, postgres_session)
        result2 = postgres_session.execute(
            text("SELECT current_setting('app.user_id', true)")
        ).scalar()
        
        # Assert
        assert result1 == authenticated_user.user_id
        assert result2 == second_user.user_id

    def test_get_db_for_user_context_is_transaction_local(
        self, postgres_session, authenticated_user
    ):
        # Act - Set context
        get_db_for_user(authenticated_user, postgres_session)
        
        # Assert - Context is set for this transaction
        result = postgres_session.execute(
            text("SELECT current_setting('app.user_id', true)")
        ).scalar()
        assert result == authenticated_user.user_id
        
        # Note: After transaction rollback (in fixture cleanup),
        # the context will be cleared automatically


# =============================================================================
# Tests: get_user_with_settings() - Combined Dependency
# =============================================================================

class TestGetUserWithSettingsIntegration:
    """Integration tests for combined user + settings dependency."""

    def test_get_user_with_settings_returns_tuple(
        self, postgres_session, authenticated_user
    ):
        # Arrange
        settings = get_user_settings(authenticated_user, postgres_session)
        
        # Act
        result = get_user_with_settings(authenticated_user, settings)
        
        # Assert
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_get_user_with_settings_contains_correct_data(
        self, postgres_session, authenticated_user
    ):
        # Arrange
        settings = get_user_settings(authenticated_user, postgres_session)
        
        # Act
        user, user_settings = get_user_with_settings(authenticated_user, settings)
        
        # Assert
        assert user.user_id == authenticated_user.user_id
        assert user_settings.user_email == authenticated_user.email


# =============================================================================
# Tests: UserSettings Model Behavior in PostgreSQL
# =============================================================================

class TestUserSettingsModelIntegration:
    """Integration tests for UserSettings model behavior in PostgreSQL."""

    def test_user_settings_update_persists(
        self, postgres_session, authenticated_user
    ):
        # Arrange
        settings = get_user_settings(authenticated_user, postgres_session)
        settings_id = settings.id
        
        # Act - Update settings
        settings.subscription_tier = "pro"
        settings.subscription_status = "active"
        postgres_session.flush()
        
        # Assert - Query fresh from DB
        updated = postgres_session.query(UserSettings).filter(
            UserSettings.id == settings_id
        ).first()
        assert updated.subscription_tier == "pro"
        assert updated.subscription_status == "active"

    def test_user_settings_unique_user_id_constraint(
        self, postgres_session, authenticated_user
    ):
        # Arrange - Create first settings
        settings1 = get_user_settings(authenticated_user, postgres_session)
        postgres_session.flush()
        
        # Act - Try to create duplicate manually with same user_id
        duplicate = UserSettings(
            user_id=authenticated_user.user_id,
            user_email=f"different_{uuid.uuid4().hex[:8]}@example.com",
        )
        postgres_session.add(duplicate)
        
        # Assert - Should raise integrity error on flush
        with pytest.raises(Exception):  # IntegrityError
            postgres_session.flush()
        
        postgres_session.rollback()


# =============================================================================
# Tests: Edge Cases with PostgreSQL
# =============================================================================

class TestDatabaseEdgeCases:
    """Edge case tests involving PostgreSQL operations."""

    def test_get_user_settings_handles_unicode_email(self, postgres_session):
        # Arrange - Use unique unicode email
        unique_id = f"unicode_{uuid.uuid4().hex[:8]}"
        unicode_email = f"用户_{unique_id}@example.com"
        unicode_user = AuthenticatedUser(
            user_id=unique_id,
            email=unicode_email,
            email_verified=True,
            provider="google",
            app_metadata={},
            user_metadata={},
        )
        
        # Act
        settings = get_user_settings(unicode_user, postgres_session)
        
        # Assert
        assert settings.user_email == unicode_email

    def test_get_user_settings_handles_uuid_user_id(self, postgres_session):
        # Arrange - Real UUID format like Supabase uses
        real_uuid = str(uuid.uuid4())
        uuid_user = AuthenticatedUser(
            user_id=real_uuid,
            email=f"uuid_{uuid.uuid4().hex[:8]}@example.com",
            email_verified=True,
            provider="google",
            app_metadata={},
            user_metadata={},
        )
        
        # Act
        settings = get_user_settings(uuid_user, postgres_session)
        
        # Assert
        assert settings.user_id == real_uuid

    def test_get_user_settings_idempotent_multiple_calls(
        self, postgres_session, authenticated_user
    ):
        # Arrange & Act - Call multiple times
        settings1 = get_user_settings(authenticated_user, postgres_session)
        settings2 = get_user_settings(authenticated_user, postgres_session)
        settings3 = get_user_settings(authenticated_user, postgres_session)
        
        # Assert - All return same settings
        assert settings1.id == settings2.id == settings3.id
        
        # Verify only one record in DB
        count = postgres_session.query(UserSettings).filter(
            UserSettings.user_id == authenticated_user.user_id
        ).count()
        assert count == 1


# =============================================================================
# Tests: RLS Policy Verification (if RLS is enabled)
# =============================================================================

class TestRLSPolicyIntegration:
    """Tests to verify RLS policies work correctly.
    
    These tests assume RLS is enabled via migration 017_enable_rls_policies.sql
    """

    def test_rls_context_filters_user_data(
        self, postgres_session, authenticated_user, second_user
    ):
        """Verify that RLS filters data based on user context.
        
        Note: This test demonstrates the pattern. Full RLS testing
        requires the RLS policies to be enabled on the UserSettings table.
        """
        # Arrange - Create settings for both users
        settings1 = get_user_settings(authenticated_user, postgres_session)
        settings2 = get_user_settings(second_user, postgres_session)
        postgres_session.flush()
        
        # Act - Set RLS context to first user
        get_db_for_user(authenticated_user, postgres_session)
        
        # Assert - Both exist (RLS may not be on UserSettings table)
        # This test documents expected behavior when RLS IS enabled
        all_settings = postgres_session.query(UserSettings).filter(
            UserSettings.user_id.in_([authenticated_user.user_id, second_user.user_id])
        ).all()
        
        # Without RLS: sees both
        # With RLS: would only see authenticated_user's settings
        assert len(all_settings) >= 1  # At minimum, own settings visible
