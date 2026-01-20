"""
Unit tests for Auth Module (backend/src/app/security/auth.py)

Pre-Testing Checklist:
1. Business Logic? YES - JWT verification, token extraction, user parsing
2. Black Box? YES - Pure functions with clear inputs/outputs
3. Boundaries? Empty strings, malformed tokens, missing claims
4. External Dependencies? JWT library (mocked), Settings (mocked)
5. Happy Path? Valid JWT -> AuthenticatedUser
6. Failure Modes? Expired token, invalid signature, missing claims

Tests focus on:
- extract_token_from_header() - Bearer token extraction
- verify_jwt() - JWT validation and error handling
- AuthenticatedUser.from_jwt_payload() - JWT claims parsing
- create_user_settings() - Factory function
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from freezegun import freeze_time
import jwt as pyjwt

from app.security.auth import (
    AuthenticatedUser,
    extract_token_from_header,
    verify_jwt,
    create_user_settings,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def valid_jwt_payload():
    """Standard valid Supabase JWT payload."""
    return {
        "sub": "user-uuid-12345",
        "email": "test@example.com",
        "email_verified": True,
        "app_metadata": {"provider": "google"},
        "user_metadata": {
            "full_name": "Test User",
            "avatar_url": "https://example.com/avatar.jpg"
        },
        "aud": "authenticated",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }


@pytest.fixture
def jwt_secret():
    """Test JWT secret."""
    return "test-secret-key-32-chars-minimum"


@pytest.fixture
def valid_token(valid_jwt_payload, jwt_secret):
    """Generate a valid JWT token."""
    return pyjwt.encode(valid_jwt_payload, jwt_secret, algorithm="HS256")


@pytest.fixture
def expired_token(valid_jwt_payload, jwt_secret):
    """Generate an expired JWT token."""
    expired_payload = valid_jwt_payload.copy()
    expired_payload["exp"] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    return pyjwt.encode(expired_payload, jwt_secret, algorithm="HS256")


# =============================================================================
# Tests: extract_token_from_header()
# =============================================================================

class TestExtractTokenFromHeader:
    """Tests for Bearer token extraction from Authorization header."""

    def test_extract_token_with_valid_bearer_header_returns_token(self):
        # Arrange
        authorization = "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test"

    def test_extract_token_with_lowercase_bearer_returns_token(self):
        # Arrange
        authorization = "bearer some_token_value"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result == "some_token_value"

    def test_extract_token_with_none_returns_none(self):
        # Arrange
        authorization = None
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result is None

    def test_extract_token_with_empty_string_returns_none(self):
        # Arrange
        authorization = ""
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result is None

    def test_extract_token_with_only_bearer_keyword_returns_none(self):
        # Arrange
        authorization = "Bearer"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result is None

    def test_extract_token_with_wrong_scheme_returns_none(self):
        # Arrange
        authorization = "Basic dXNlcjpwYXNz"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result is None

    def test_extract_token_with_extra_spaces_returns_none(self):
        # Arrange - Three parts instead of two
        authorization = "Bearer token extra_part"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result is None


# =============================================================================
# Tests: verify_jwt()
# =============================================================================

class TestVerifyJwt:
    """Tests for JWT verification and decoding."""

    def test_verify_jwt_with_valid_token_returns_payload(self, valid_token, jwt_secret):
        # Arrange - token and secret from fixtures
        
        # Act
        result = verify_jwt(valid_token, jwt_secret)
        
        # Assert
        assert result["sub"] == "user-uuid-12345"
        assert result["email"] == "test@example.com"
        assert result["aud"] == "authenticated"

    def test_verify_jwt_with_expired_token_raises_401(self, expired_token, jwt_secret):
        # Arrange - expired token from fixture
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(expired_token, jwt_secret)
        
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_verify_jwt_with_invalid_signature_raises_401(self, valid_token):
        # Arrange
        from fastapi import HTTPException
        wrong_secret = "wrong-secret-key-32-chars-minimum"
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(valid_token, wrong_secret)
        
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    def test_verify_jwt_with_empty_secret_raises_500(self, valid_token):
        # Arrange
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(valid_token, "")
        
        assert exc_info.value.status_code == 500
        assert "JWT secret not configured" in exc_info.value.detail

    def test_verify_jwt_with_none_secret_raises_500(self, valid_token):
        # Arrange
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(valid_token, None)
        
        assert exc_info.value.status_code == 500

    def test_verify_jwt_with_malformed_token_raises_401(self, jwt_secret):
        # Arrange
        from fastapi import HTTPException
        malformed_token = "not.a.valid.jwt.token"
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(malformed_token, jwt_secret)
        
        assert exc_info.value.status_code == 401

    def test_verify_jwt_with_wrong_audience_raises_401(self, jwt_secret):
        # Arrange
        from fastapi import HTTPException
        payload = {
            "sub": "user-123",
            "email": "test@test.com",
            "aud": "wrong_audience",  # Not "authenticated"
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(token, jwt_secret)
        
        assert exc_info.value.status_code == 401

    def test_verify_jwt_with_missing_required_claims_raises_401(self, jwt_secret):
        # Arrange - Missing "sub" claim
        from fastapi import HTTPException
        payload = {
            "email": "test@test.com",
            "aud": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(token, jwt_secret)
        
        assert exc_info.value.status_code == 401


# =============================================================================
# Tests: AuthenticatedUser.from_jwt_payload()
# =============================================================================

class TestAuthenticatedUserFromJwtPayload:
    """Tests for creating AuthenticatedUser from JWT claims."""

    def test_from_jwt_payload_with_complete_payload_returns_user(self, valid_jwt_payload):
        # Arrange - payload from fixture
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        
        # Assert
        assert user.user_id == "user-uuid-12345"
        assert user.email == "test@example.com"
        assert user.email_verified is True
        assert user.provider == "google"

    def test_from_jwt_payload_extracts_metadata_correctly(self, valid_jwt_payload):
        # Arrange - payload from fixture
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        
        # Assert
        assert user.user_metadata["full_name"] == "Test User"
        assert user.app_metadata["provider"] == "google"

    def test_from_jwt_payload_with_missing_sub_raises_error(self):
        # Arrange
        payload = {
            "email": "test@example.com",
            "aud": "authenticated",
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            AuthenticatedUser.from_jwt_payload(payload)
        
        assert "missing sub or email" in str(exc_info.value)

    def test_from_jwt_payload_with_missing_email_raises_error(self):
        # Arrange
        payload = {
            "sub": "user-uuid-12345",
            "aud": "authenticated",
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            AuthenticatedUser.from_jwt_payload(payload)
        
        assert "missing sub or email" in str(exc_info.value)

    def test_from_jwt_payload_with_empty_sub_raises_error(self):
        # Arrange
        payload = {
            "sub": "",
            "email": "test@example.com",
        }
        
        # Act & Assert
        with pytest.raises(ValueError):
            AuthenticatedUser.from_jwt_payload(payload)

    def test_from_jwt_payload_with_minimal_payload_uses_defaults(self):
        # Arrange
        payload = {
            "sub": "user-uuid-12345",
            "email": "test@example.com",
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.user_id == "user-uuid-12345"
        assert user.email_verified is False  # Default
        assert user.provider == "google"  # Default
        assert user.app_metadata == {}
        assert user.user_metadata == {}


# =============================================================================
# Tests: AuthenticatedUser Properties
# =============================================================================

class TestAuthenticatedUserProperties:
    """Tests for AuthenticatedUser computed properties."""

    def test_display_name_returns_full_name_when_available(self, valid_jwt_payload):
        # Arrange
        user = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        
        # Act
        result = user.display_name
        
        # Assert
        assert result == "Test User"

    def test_display_name_returns_name_when_full_name_missing(self):
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "john@example.com",
            "user_metadata": {"name": "John Doe"},
        }
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Act
        result = user.display_name
        
        # Assert
        assert result == "John Doe"

    def test_display_name_returns_email_prefix_when_no_name(self):
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "john.doe@example.com",
            "user_metadata": {},
        }
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Act
        result = user.display_name
        
        # Assert
        assert result == "john.doe"

    def test_avatar_url_returns_avatar_url_when_available(self, valid_jwt_payload):
        # Arrange
        user = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        
        # Act
        result = user.avatar_url
        
        # Assert
        assert result == "https://example.com/avatar.jpg"

    def test_avatar_url_returns_picture_when_avatar_url_missing(self):
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {"picture": "https://example.com/picture.jpg"},
        }
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Act
        result = user.avatar_url
        
        # Assert
        assert result == "https://example.com/picture.jpg"

    def test_avatar_url_returns_none_when_no_avatar(self):
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {},
        }
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Act
        result = user.avatar_url
        
        # Assert
        assert result is None


# =============================================================================
# Tests: create_user_settings()
# =============================================================================

class TestCreateUserSettings:
    """Tests for UserSettings factory function."""

    @freeze_time("2026-01-19 12:00:00", tz_offset=0)
    def test_create_user_settings_returns_valid_settings(self):
        # Arrange
        user_id = "user-uuid-12345"
        email = "test@example.com"
        
        # Act
        settings = create_user_settings(user_id, email)
        
        # Assert
        assert settings.user_id == user_id
        assert settings.user_email == email

    @freeze_time("2026-01-19 12:00:00", tz_offset=0)
    def test_create_user_settings_sets_trial_end_date(self):
        # Arrange
        user_id = "user-uuid-12345"
        email = "test@example.com"
        trial_days = 7
        
        # Act
        settings = create_user_settings(user_id, email, trial_days=trial_days)
        
        # Assert
        expected_end = datetime(2026, 1, 26, 12, 0, 0, tzinfo=timezone.utc)
        assert settings.trial_ends_at == expected_end

    @freeze_time("2026-01-19 12:00:00", tz_offset=0)
    def test_create_user_settings_with_custom_trial_days(self):
        # Arrange
        user_id = "user-uuid-12345"
        email = "test@example.com"
        trial_days = 14
        
        # Act
        settings = create_user_settings(user_id, email, trial_days=trial_days)
        
        # Assert
        expected_end = datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc)
        assert settings.trial_ends_at == expected_end


# =============================================================================
# Tests: AuthenticatedUser Immutability
# =============================================================================

class TestAuthenticatedUserImmutability:
    """Tests to verify AuthenticatedUser is frozen (immutable)."""

    def test_authenticated_user_is_immutable(self, valid_jwt_payload):
        # Arrange
        user = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        
        # Act & Assert
        with pytest.raises(AttributeError):
            user.user_id = "new-id"

    def test_authenticated_user_equality_based_on_user_id(self, valid_jwt_payload):
        # Arrange
        user1 = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        user2 = AuthenticatedUser.from_jwt_payload(valid_jwt_payload)
        
        # Act & Assert
        assert user1 == user2
        assert user1.user_id == user2.user_id


# =============================================================================
# Tests: get_current_user() - FastAPI Dependency
# =============================================================================

class TestGetCurrentUser:
    """Tests for the get_current_user FastAPI dependency."""

    @pytest.fixture
    def mock_settings(self, jwt_secret):
        """Mock Settings with JWT secret."""
        settings = MagicMock()
        settings.SUPABASE_JWT_SECRET = jwt_secret
        return settings

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token_returns_user(
        self, valid_token, mock_settings
    ):
        # Arrange
        from app.security.auth import get_current_user
        authorization = f"Bearer {valid_token}"
        
        # Act
        user = await get_current_user(authorization, mock_settings)
        
        # Assert
        assert user.user_id == "user-uuid-12345"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_current_user_without_token_raises_401(self, mock_settings):
        # Arrange
        from app.security.auth import get_current_user
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None, mock_settings)
        
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_with_empty_header_raises_401(self, mock_settings):
        # Arrange
        from app.security.auth import get_current_user
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("", mock_settings)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_with_expired_token_raises_401(
        self, expired_token, mock_settings
    ):
        # Arrange
        from app.security.auth import get_current_user
        from fastapi import HTTPException
        authorization = f"Bearer {expired_token}"
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization, mock_settings)
        
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token_raises_401(self, mock_settings):
        # Arrange
        from app.security.auth import get_current_user
        from fastapi import HTTPException
        authorization = "Bearer invalid.token.here"
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization, mock_settings)
        
        assert exc_info.value.status_code == 401


# =============================================================================
# Tests: get_current_user_optional() - FastAPI Dependency
# =============================================================================

class TestGetCurrentUserOptional:
    """Tests for the optional auth dependency."""

    @pytest.fixture
    def mock_settings(self, jwt_secret):
        """Mock Settings with JWT secret."""
        settings = MagicMock()
        settings.SUPABASE_JWT_SECRET = jwt_secret
        return settings

    @pytest.mark.asyncio
    async def test_get_current_user_optional_with_valid_token_returns_user(
        self, valid_token, mock_settings
    ):
        # Arrange
        from app.security.auth import get_current_user_optional
        authorization = f"Bearer {valid_token}"
        
        # Act
        user = await get_current_user_optional(authorization, mock_settings)
        
        # Assert
        assert user is not None
        assert user.user_id == "user-uuid-12345"

    @pytest.mark.asyncio
    async def test_get_current_user_optional_without_token_returns_none(
        self, mock_settings
    ):
        # Arrange
        from app.security.auth import get_current_user_optional
        
        # Act
        user = await get_current_user_optional(None, mock_settings)
        
        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_with_invalid_token_returns_none(
        self, mock_settings
    ):
        # Arrange
        from app.security.auth import get_current_user_optional
        authorization = "Bearer invalid.token.here"
        
        # Act
        user = await get_current_user_optional(authorization, mock_settings)
        
        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_with_expired_token_returns_none(
        self, expired_token, mock_settings
    ):
        # Arrange
        from app.security.auth import get_current_user_optional
        authorization = f"Bearer {expired_token}"
        
        # Act
        user = await get_current_user_optional(authorization, mock_settings)
        
        # Assert
        assert user is None


# =============================================================================
# Tests: require_active_subscription() - FastAPI Dependency
# =============================================================================

class TestRequireActiveSubscription:
    """Tests for subscription requirement dependency."""

    @pytest.fixture
    def mock_user(self, valid_jwt_payload):
        """Create a mock authenticated user."""
        return AuthenticatedUser.from_jwt_payload(valid_jwt_payload)

    @pytest.fixture
    def active_settings(self):
        """Mock UserSettings with active subscription."""
        settings = MagicMock()
        settings.is_active = True
        settings.subscription_tier = "pro"
        settings.subscription_status = "active"
        return settings

    @pytest.fixture
    def inactive_settings(self):
        """Mock UserSettings with inactive subscription."""
        settings = MagicMock()
        settings.is_active = False
        settings.subscription_tier = "free"
        settings.subscription_status = "expired"
        return settings

    def test_require_active_subscription_with_active_user_returns_user(
        self, mock_user, active_settings
    ):
        # Arrange
        from app.security.auth import require_active_subscription
        
        # Act
        result = require_active_subscription(mock_user, active_settings)
        
        # Assert
        assert result == mock_user

    def test_require_active_subscription_with_inactive_user_raises_402(
        self, mock_user, inactive_settings
    ):
        # Arrange
        from app.security.auth import require_active_subscription
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            require_active_subscription(mock_user, inactive_settings)
        
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "subscription_required"


# =============================================================================
# Tests: require_pro_tier() - FastAPI Dependency
# =============================================================================

class TestRequireProTier:
    """Tests for Pro tier requirement dependency."""

    @pytest.fixture
    def mock_user(self, valid_jwt_payload):
        """Create a mock authenticated user."""
        return AuthenticatedUser.from_jwt_payload(valid_jwt_payload)

    @pytest.fixture
    def pro_settings(self):
        """Mock UserSettings with Pro tier."""
        settings = MagicMock()
        settings.subscription_tier = "pro"
        return settings

    @pytest.fixture
    def free_settings(self):
        """Mock UserSettings with free tier."""
        settings = MagicMock()
        settings.subscription_tier = "free"
        return settings

    @pytest.fixture
    def trial_settings(self):
        """Mock UserSettings with trial tier."""
        settings = MagicMock()
        settings.subscription_tier = "trial"
        return settings

    def test_require_pro_tier_with_pro_user_returns_user(
        self, mock_user, pro_settings
    ):
        # Arrange
        from app.security.auth import require_pro_tier
        
        # Act
        result = require_pro_tier(mock_user, pro_settings)
        
        # Assert
        assert result == mock_user

    def test_require_pro_tier_with_free_user_raises_402(
        self, mock_user, free_settings
    ):
        # Arrange
        from app.security.auth import require_pro_tier
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            require_pro_tier(mock_user, free_settings)
        
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["error"] == "pro_required"
        assert exc_info.value.detail["current_tier"] == "free"

    def test_require_pro_tier_with_trial_user_raises_402(
        self, mock_user, trial_settings
    ):
        # Arrange
        from app.security.auth import require_pro_tier
        from fastapi import HTTPException
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            require_pro_tier(mock_user, trial_settings)
        
        assert exc_info.value.status_code == 402
        assert exc_info.value.detail["current_tier"] == "trial"


# =============================================================================
# Tests: Edge Cases & Boundary Conditions
# =============================================================================

class TestEdgeCasesTokenExtraction:
    """Edge case tests for token extraction."""

    def test_extract_token_with_very_long_token_returns_token(self):
        # Arrange - Token with 10,000 characters
        long_token = "a" * 10000
        authorization = f"Bearer {long_token}"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result == long_token
        assert len(result) == 10000

    def test_extract_token_with_special_characters_in_token(self):
        # Arrange - JWT can contain base64url characters: A-Z, a-z, 0-9, -, _, .
        special_token = "eyJ0eXAi.abc-123_XYZ.signature-here_ok"
        authorization = f"Bearer {special_token}"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result == special_token

    def test_extract_token_with_whitespace_only_header_returns_none(self):
        # Arrange
        authorization = "   "
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result is None

    def test_extract_token_case_sensitivity_of_bearer(self):
        # Arrange - Mixed case should still work
        authorization = "BEARER my_token"
        
        # Act
        result = extract_token_from_header(authorization)
        
        # Assert
        assert result == "my_token"


class TestEdgeCasesAuthenticatedUser:
    """Edge case tests for AuthenticatedUser parsing."""

    def test_from_jwt_payload_with_unicode_email(self):
        # Arrange - International email address
        payload = {
            "sub": "user-123",
            "email": "用户@example.com",
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.email == "用户@example.com"

    def test_from_jwt_payload_with_unicode_name(self):
        # Arrange - International name
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {"full_name": "名前 Müller 姓名"},
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.display_name == "名前 Müller 姓名"

    def test_from_jwt_payload_with_emoji_in_name(self):
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {"full_name": "John 🚀 Doe"},
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.display_name == "John 🚀 Doe"

    def test_from_jwt_payload_with_very_long_email(self):
        # Arrange - 254 characters is max valid email length
        local_part = "a" * 64
        domain = "b" * 185 + ".com"
        long_email = f"{local_part}@{domain}"
        payload = {
            "sub": "user-123",
            "email": long_email,
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.email == long_email

    def test_from_jwt_payload_with_special_chars_in_email_prefix(self):
        # Arrange - Valid email special characters
        payload = {
            "sub": "user-123",
            "email": "user+tag.name@example.com",
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.display_name == "user+tag.name"

    def test_from_jwt_payload_with_deeply_nested_metadata(self):
        # Arrange
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "user_metadata": {
                "level1": {
                    "level2": {
                        "level3": "deep_value"
                    }
                }
            },
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.user_metadata["level1"]["level2"]["level3"] == "deep_value"

    def test_display_name_with_empty_string_values_falls_back(self):
        # Arrange - Empty strings should fall back
        payload = {
            "sub": "user-123",
            "email": "john@example.com",
            "user_metadata": {"full_name": "", "name": ""},
        }
        
        # Act
        user = AuthenticatedUser.from_jwt_payload(payload)
        
        # Assert
        assert user.display_name == "john"


class TestEdgeCasesUserSettings:
    """Edge case tests for create_user_settings."""

    @freeze_time("2026-01-19 12:00:00", tz_offset=0)
    def test_create_user_settings_with_zero_trial_days(self):
        # Arrange - Edge case: 0 trial days
        
        # Act
        settings = create_user_settings("user-123", "test@example.com", trial_days=0)
        
        # Assert - Trial ends immediately
        expected_end = datetime(2026, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
        assert settings.trial_ends_at == expected_end

    @freeze_time("2026-01-19 12:00:00", tz_offset=0)
    def test_create_user_settings_with_negative_trial_days(self):
        # Arrange - Edge case: negative trial days (already expired)
        
        # Act
        settings = create_user_settings("user-123", "test@example.com", trial_days=-1)
        
        # Assert - Trial ended yesterday
        expected_end = datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc)
        assert settings.trial_ends_at == expected_end

    @freeze_time("2026-01-19 12:00:00", tz_offset=0)
    def test_create_user_settings_with_large_trial_days(self):
        # Arrange - 365 day trial
        
        # Act
        settings = create_user_settings("user-123", "test@example.com", trial_days=365)
        
        # Assert
        expected_end = datetime(2027, 1, 19, 12, 0, 0, tzinfo=timezone.utc)
        assert settings.trial_ends_at == expected_end

    def test_create_user_settings_with_uuid_user_id(self):
        # Arrange - Real UUID format
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Act
        settings = create_user_settings(user_id, "test@example.com")
        
        # Assert
        assert settings.user_id == user_id


class TestEdgeCasesJwtVerification:
    """Edge case tests for JWT verification."""

    def test_verify_jwt_with_token_missing_iat_claim(self, jwt_secret):
        # Arrange - iat (issued at) is not required
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "aud": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }
        token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Act
        result = verify_jwt(token, jwt_secret)
        
        # Assert - Should work without iat
        assert result["sub"] == "user-123"

    def test_verify_jwt_with_token_expiring_in_1_second(self, jwt_secret):
        # Arrange - Token about to expire
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "aud": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(seconds=30)).timestamp()),
        }
        token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Act - Should still be valid
        result = verify_jwt(token, jwt_secret)
        
        # Assert
        assert result["sub"] == "user-123"

    def test_verify_jwt_with_extra_claims_preserves_them(self, jwt_secret):
        # Arrange - Extra custom claims
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "aud": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "custom_claim": "custom_value",
            "roles": ["admin", "user"],
        }
        token = pyjwt.encode(payload, jwt_secret, algorithm="HS256")
        
        # Act
        result = verify_jwt(token, jwt_secret)
        
        # Assert - Extra claims preserved
        assert result["custom_claim"] == "custom_value"
        assert result["roles"] == ["admin", "user"]
