"""
Unit Tests for PolarService - Polar.sh Billing Integration

Pre-Testing Reflection:
1. WHAT ARE WE TESTING?
   PolarService methods: customer management, checkout, subscriptions, portal access.
   
2. WHY IS TESTING IMPORTANT HERE?
   Payment integration is critical - errors could lead to revenue loss or customer frustration.
   
3. WHAT COULD GO WRONG?
   - API failures, network errors, invalid responses
   - Missing configuration (tokens, product IDs)
   - Edge cases in customer lookup/creation
   
4. WHAT DO WE NOT NEED TO TEST?
   - The Polar SDK itself (third-party library)
   - Actual network calls (mock everything)

Test Categories:
- PolarService initialization (with/without token, SDK import errors)
- get_or_create_customer() - lookup, creation, error handling
- create_checkout_session() - URL generation, config errors
- get_subscription() - data transformation
- cancel_subscription() - success/failure
- get_customer_portal_url() - URL generation
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_settings():
    """Mock Settings with Polar configuration."""
    settings = MagicMock()
    settings.POLAR_ACCESS_TOKEN = "test_polar_token_12345"
    settings.POLAR_WEBHOOK_SECRET = "whsec_test_secret"
    settings.POLAR_PRODUCT_ID = "prod_pro_subscription_123"
    return settings


@pytest.fixture
def mock_settings_no_token():
    """Mock Settings without Polar token."""
    settings = MagicMock()
    settings.POLAR_ACCESS_TOKEN = ""
    settings.POLAR_WEBHOOK_SECRET = ""
    settings.POLAR_PRODUCT_ID = ""
    return settings


@pytest.fixture
def mock_settings_no_product():
    """Mock Settings with token but no product ID."""
    settings = MagicMock()
    settings.POLAR_ACCESS_TOKEN = "test_polar_token_12345"
    settings.POLAR_WEBHOOK_SECRET = "whsec_test_secret"
    settings.POLAR_PRODUCT_ID = ""
    return settings


@pytest.fixture
def mock_polar_client():
    """Mock Polar SDK client."""
    return MagicMock()


@pytest.fixture
def mock_customer():
    """Mock Polar customer object."""
    customer = MagicMock()
    customer.id = "cust_polar_123456"
    customer.email = "test@example.com"
    return customer


@pytest.fixture
def mock_checkout():
    """Mock Polar checkout object."""
    checkout = MagicMock()
    checkout.id = "chk_checkout_789"
    checkout.url = "https://checkout.polar.sh/chk_checkout_789"
    return checkout


@pytest.fixture
def mock_subscription():
    """Mock Polar subscription object."""
    subscription = MagicMock()
    subscription.id = "sub_subscription_456"
    subscription.status = "active"
    subscription.current_period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    subscription.current_period_end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    return subscription


@pytest.fixture
def mock_customer_session():
    """Mock Polar customer session object."""
    session = MagicMock()
    session.customer_portal_url = "https://polar.sh/portal/session_abc123"
    return session


# =============================================================================
# Tests: PolarService Initialization
# =============================================================================

class TestPolarServiceInit:
    """Tests for PolarService initialization."""

    def test_init_with_valid_token_enables_service(self, mock_settings):
        # Arrange
        with patch("app.services.polar.get_settings", return_value=mock_settings):
            with patch("polar_sdk.Polar") as MockPolar:
                MockPolar.return_value = MagicMock()
                
                # Act
                from app.services.polar import PolarService
                service = PolarService(settings=mock_settings)
                
                # Assert
                assert service.enabled is True
                assert service.client is not None

    def test_init_without_token_disables_service(self, mock_settings_no_token):
        # Arrange & Act
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Assert
        assert service.enabled is False
        assert service.client is None

    def test_init_without_token_handles_gracefully(self, mock_settings_no_token):
        # Arrange & Act - Service should handle missing token gracefully
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Assert - Service is disabled, no errors raised
        assert service.enabled is False
        assert service.client is None
        # All methods should return None/False gracefully
        assert service.get_or_create_customer("test@example.com") is None
        assert service.cancel_subscription("sub_123") is False

    def test_init_uses_default_settings_when_none_provided(self):
        # Arrange
        mock_default_settings = MagicMock()
        mock_default_settings.POLAR_ACCESS_TOKEN = ""
        
        with patch("app.services.polar.get_settings", return_value=mock_default_settings):
            # Act
            from app.services.polar import PolarService
            service = PolarService()  # No settings passed
            
            # Assert
            assert service.settings == mock_default_settings


# =============================================================================
# Tests: get_or_create_customer()
# =============================================================================

class TestGetOrCreateCustomer:
    """Tests for customer lookup and creation."""

    @pytest.fixture
    def enabled_service(self, mock_settings, mock_polar_client):
        """Create a PolarService with mocked client."""
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings
        service.client = mock_polar_client
        service.enabled = True
        return service

    def test_get_or_create_customer_finds_existing_customer(
        self, enabled_service, mock_customer
    ):
        # Arrange
        mock_result = MagicMock()
        mock_result.items = [mock_customer]
        enabled_service.client.customers.list.return_value = MagicMock(result=mock_result)
        
        # Act
        result = enabled_service.get_or_create_customer("test@example.com")
        
        # Assert
        assert result == "cust_polar_123456"
        enabled_service.client.customers.list.assert_called_once_with(email="test@example.com")

    def test_get_or_create_customer_creates_new_when_not_found(
        self, enabled_service, mock_customer
    ):
        # Arrange - Empty result list
        mock_result = MagicMock()
        mock_result.items = []
        enabled_service.client.customers.list.return_value = MagicMock(result=mock_result)
        enabled_service.client.customers.create.return_value = mock_customer
        
        # Act
        result = enabled_service.get_or_create_customer("new@example.com")
        
        # Assert
        # The mocked customer ID is "cust_polar_123456" in conftest.py's mock_customer fixture
        assert result == "cust_polar_123456"
        # Verify it was called with customer_create dictionary
        enabled_service.client.customers.create.assert_called_with(
            customer_create={"email": "new@example.com"}
        )

    def test_get_or_create_customer_returns_none_when_disabled(
        self, mock_settings_no_token
    ):
        # Arrange
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Act
        result = service.get_or_create_customer("test@example.com")
        
        # Assert
        assert result is None

    def test_get_or_create_customer_handles_api_error(self, enabled_service):
        # Arrange
        enabled_service.client.customers.list.side_effect = Exception("API Error")
        
        # Act
        result = enabled_service.get_or_create_customer("error@example.com")
        
        # Assert
        assert result is None


# =============================================================================
# Tests: create_checkout_session()
# =============================================================================

class TestCreateCheckoutSession:
    """Tests for checkout session creation."""

    @pytest.fixture
    def enabled_service(self, mock_settings, mock_polar_client):
        """Create a PolarService with mocked client."""
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings
        service.client = mock_polar_client
        service.enabled = True
        return service

    def test_create_checkout_session_returns_url(
        self, enabled_service, mock_checkout
    ):
        # Arrange
        enabled_service.client.checkouts.create.return_value = mock_checkout
        
        # Act
        result = enabled_service.create_checkout_session(
            customer_id="cust_123",
            success_url="https://app.example.com/success",
            cancel_url="https://app.example.com/cancel"
        )
        
        # Assert
        assert result == "https://checkout.polar.sh/chk_checkout_789"
        
        # Verify call arguments (dictionary, not object)
        enabled_service.client.checkouts.create.assert_called_with(
            request={
                "products": ["prod_pro_subscription_123"],
                "customer_id": "cust_123",
                "success_url": "https://app.example.com/success",
                "return_url": "https://app.example.com/cancel",
            }
        )
        
    def test_create_checkout_session_returns_none_when_disabled(
        self, mock_settings_no_token
    ):
        # Arrange
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Act
        result = service.create_checkout_session(
            customer_id="cust_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        # Assert
        assert result is None

    def test_create_checkout_session_returns_none_without_product_id(
        self, mock_settings_no_product, mock_polar_client
    ):
        # Arrange
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings_no_product
        service.client = mock_polar_client
        service.enabled = True
        
        # Act
        result = service.create_checkout_session(
            customer_id="cust_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        # Assert
        assert result is None

    def test_create_checkout_session_handles_api_error(self, enabled_service):
        # Arrange
        enabled_service.client.checkouts.create.side_effect = Exception("Checkout Error")
        
        # Act
        result = enabled_service.create_checkout_session(
            customer_id="cust_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        # Assert
        assert result is None


# =============================================================================
# Tests: get_subscription()
# =============================================================================

class TestGetSubscription:
    """Tests for subscription retrieval."""

    @pytest.fixture
    def enabled_service(self, mock_settings, mock_polar_client):
        """Create a PolarService with mocked client."""
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings
        service.client = mock_polar_client
        service.enabled = True
        return service

    def test_get_subscription_returns_details(
        self, enabled_service, mock_subscription
    ):
        # Arrange
        enabled_service.client.subscriptions.get.return_value = mock_subscription
        
        # Act
        result = enabled_service.get_subscription("sub_subscription_456")
        
        # Assert
        assert result["id"] == "sub_subscription_456"
        assert result["status"] == "active"
        assert result["cancel_at_period_end"] is False
        assert result["current_period_start"] == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert result["current_period_end"] == datetime(2026, 2, 1, tzinfo=timezone.utc)

    def test_get_subscription_returns_none_when_disabled(
        self, mock_settings_no_token
    ):
        # Arrange
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Act
        result = service.get_subscription("sub_123")
        
        # Assert
        assert result is None

    def test_get_subscription_handles_api_error(self, enabled_service):
        # Arrange
        enabled_service.client.subscriptions.get.side_effect = Exception("Not Found")
        
        # Act
        result = enabled_service.get_subscription("sub_invalid")
        
        # Assert
        assert result is None

    def test_get_subscription_handles_missing_canceled_at(self, enabled_service):
        # Arrange - Subscription without canceled_at attribute
        subscription = MagicMock()
        subscription.id = "sub_123"
        subscription.status = "active"
        subscription.current_period_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        subscription.current_period_end = datetime(2026, 2, 1, tzinfo=timezone.utc)
        subscription.cancel_at_period_end = False
        # Simulate missing canceled_at
        del subscription.canceled_at
        enabled_service.client.subscriptions.get.return_value = subscription
        
        # Act
        result = enabled_service.get_subscription("sub_123")
        
        # Assert - Should use getattr default
        assert result["canceled_at"] is None


# =============================================================================
# Tests: cancel_subscription()
# =============================================================================

class TestCancelSubscription:
    """Tests for subscription cancellation."""

    @pytest.fixture
    def enabled_service(self, mock_settings, mock_polar_client):
        """Create a PolarService with mocked client."""
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings
        service.client = mock_polar_client
        service.enabled = True
        return service

    def test_cancel_subscription_returns_true_on_success(self, enabled_service):
        # Arrange
        enabled_service.client.subscriptions.cancel.return_value = None
        
        # Act
        result = enabled_service.cancel_subscription("sub_123")
        
        # Assert
        assert result is True
        enabled_service.client.subscriptions.cancel.assert_called_once_with("sub_123")

    def test_cancel_subscription_returns_false_when_disabled(
        self, mock_settings_no_token
    ):
        # Arrange
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Act
        result = service.cancel_subscription("sub_123")
        
        # Assert
        assert result is False

    def test_cancel_subscription_returns_false_on_error(self, enabled_service):
        # Arrange
        enabled_service.client.subscriptions.cancel.side_effect = Exception("Cancel Error")
        
        # Act
        result = enabled_service.cancel_subscription("sub_123")
        
        # Assert
        assert result is False


# =============================================================================
# Tests: get_customer_portal_url()
# =============================================================================

class TestGetCustomerPortalUrl:
    """Tests for customer portal URL generation."""

    @pytest.fixture
    def enabled_service(self, mock_settings, mock_polar_client):
        """Create a PolarService with mocked client."""
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings
        service.client = mock_polar_client
        service.enabled = True
        return service

    def test_get_customer_portal_url_returns_url(
        self, enabled_service, mock_customer_session
    ):
        # Arrange
        enabled_service.client.customer_sessions.create.return_value = mock_customer_session
        
        # Act
        result = enabled_service.get_customer_portal_url("cust_123")
        
        # Assert
        assert result == "https://polar.sh/portal/session_abc123"
        
        # Verify call arguments (dictionary)
        enabled_service.client.customer_sessions.create.assert_called_with(
            request={"customer_id": "cust_123"}
        )

    def test_get_customer_portal_url_returns_none_when_disabled(
        self, mock_settings_no_token
    ):
        # Arrange
        from app.services.polar import PolarService
        service = PolarService(settings=mock_settings_no_token)
        
        # Act
        result = service.get_customer_portal_url("cust_123")
        
        # Assert
        assert result is None

    def test_get_customer_portal_url_handles_api_error(self, enabled_service):
        # Arrange
        enabled_service.client.customer_sessions.create.side_effect = Exception("Portal Error")
        
        # Act
        result = enabled_service.get_customer_portal_url("cust_123")
        
        # Assert
        assert result is None


# =============================================================================
# Tests: Edge Cases
# =============================================================================

class TestPolarServiceEdgeCases:
    """Edge case tests for PolarService."""

    @pytest.fixture
    def enabled_service(self, mock_settings, mock_polar_client):
        """Create a PolarService with mocked client."""
        from app.services.polar import PolarService
        service = PolarService.__new__(PolarService)
        service.settings = mock_settings
        service.client = mock_polar_client
        service.enabled = True
        return service

    def test_get_or_create_customer_with_unicode_email(
        self, enabled_service, mock_customer
    ):
        # Arrange
        mock_result = MagicMock()
        mock_result.items = []
        enabled_service.client.customers.list.return_value = MagicMock(result=mock_result)
        enabled_service.client.customers.create.return_value = mock_customer
        
        # Act
        result = enabled_service.get_or_create_customer("用户@example.com")
        
        # Assert
        assert result == "cust_polar_123456"
        enabled_service.client.customers.create.assert_called_with(
            customer_create={"email": "用户@example.com"}
        )

    def test_create_checkout_with_special_characters_in_urls(
        self, enabled_service, mock_checkout
    ):
        # Arrange
        enabled_service.client.checkouts.create.return_value = mock_checkout
        success_url = "https://app.example.com/success?session=abc&user=123"
        cancel_url = "https://app.example.com/cancel?reason=user"
        
        # Act
        result = enabled_service.create_checkout_session(
            customer_id="cust_123",
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        # Assert
        assert result is not None
        enabled_service.client.checkouts.create.assert_called_with(
            request={
                "products": ["prod_pro_subscription_123"],
                "customer_id": "cust_123",
                "success_url": success_url,
                "return_url": cancel_url,
            }
        )

    def test_service_handles_none_result_from_customer_list(self, enabled_service):
        # Arrange - API returns None result
        enabled_service.client.customers.list.return_value = MagicMock(result=None)
        
        # Act
        result = enabled_service.get_or_create_customer("test@example.com")
        
        # Assert - Should handle gracefully (either create new or return None)
        # Based on implementation: if not result, it should try to create
        assert result is None or enabled_service.client.customers.create.called
