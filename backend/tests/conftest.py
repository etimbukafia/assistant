"""
Shared pytest fixtures for the test suite.

This module provides:
- Database fixtures (in-memory SQLite for isolation)
- Mock fixtures for external services (Gmail, Calendar, LLM)
- Sample data factories
- FastAPI test client

Note: Uses lazy imports inside fixtures to avoid import errors
when running in environments with version conflicts.
"""
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import MagicMock, patch
from typing import Generator, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from fastapi.testclient import TestClient


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database for testing."""
    from sqlalchemy import create_engine
    from app.data.models import Base
    
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a database session for a test."""
    from sqlalchemy.orm import sessionmaker
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def postgres_session():
    """
    Create a session using the real Postgres database for integration tests.
    
    Uses DATABASE_URL from environment (Supabase or local Postgres).
    Each test runs in a SAVEPOINT that is rolled back after the test.
    This ensures complete isolation between tests.
    
    Usage:
        @pytest.mark.integration
        def test_something(postgres_session):
            ...
    """
    from app.infra.database import SessionLocal
    
    session = SessionLocal()
    # Start a transaction
    session.begin_nested()  # SAVEPOINT
    try:
        yield session
    finally:
        session.rollback()  # Rollback to SAVEPOINT
        session.close()


@pytest.fixture(scope="function")
def postgres_test_client(postgres_session):
    """FastAPI test client using real Postgres database."""
    from fastapi.testclient import TestClient
    from main import app
    from app.infra.database import get_db
    
    def override_get_db():
        try:
            yield postgres_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_client(db_session):
    """Create a FastAPI test client with database session override."""
    from fastapi.testclient import TestClient
    from main import app
    from app.infra.database import get_db
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


# =============================================================================
# LLM Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Default mock LLM response structure."""
    return {
        "summary": "Test summary",
        "needs_reply": True,
        "tasks": [],
        "dates": [],
        "people": [],
        "decisions": [],
        "draft": "Test draft reply"
    }


@pytest.fixture
def mock_llm_orchestrator(mock_llm_response):
    """Mock LLMOrchestrator for isolated testing."""
    with patch("app.ai_processor.LLMOrchestrator") as mock_class:
        mock_instance = MagicMock()
        mock_instance.generate.return_value = mock_llm_response
        mock_instance.generate_batch.return_value = [mock_llm_response]
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_llm_config():
    """Mock LLMConfig for testing."""
    with patch("core.llm.LLMConfig") as mock:
        mock.from_env.return_value = MagicMock(
            provider="huggingface",
            hf_model_id="test-model",
            gemini_model="gemini-test"
        )
        yield mock


# =============================================================================
# Gmail Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_gmail_client():
    """Mock GmailClient for testing without API calls."""
    with patch("app.gmail_integration.GmailClient") as mock_class:
        mock_instance = MagicMock()
        mock_instance.is_authenticated.return_value = True
        mock_instance.get_messages.return_value = []
        mock_instance.get_message_detail.return_value = None
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_gmail_message() -> Dict[str, Any]:
    """Sample Gmail message structure for testing."""
    return {
        "id": "test_msg_123",
        "threadId": "test_thread_456",
        "sender": "test@example.com",
        "sender_name": "Test Sender",
        "subject": "Test Subject",
        "body": "This is a test email body.",
        "received_at": "2026-01-02T10:00:00Z",
        "snippet": "This is a test...",
        "labels": ["INBOX"]
    }


# =============================================================================
# Calendar Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_calendar_service():
    """Mock CalendarService for testing without API calls."""
    with patch("app.calendar_service.CalendarService") as mock_class:
        mock_instance = MagicMock()
        mock_instance.get_calendars.return_value = []
        mock_instance.get_availability.return_value = []
        mock_instance.suggest_time_slots.return_value = []
        mock_class.return_value = mock_instance
        yield mock_instance


# =============================================================================
# Sample Data Factories
# =============================================================================

@pytest.fixture
def email_factory():
    """Factory for creating test email data."""
    def _create_email(
        id: str = "test_email",
        sender: str = "sender@example.com",
        subject: str = "Test Subject",
        body: str = "Test body content",
        **kwargs
    ) -> Dict[str, Any]:
        email = {
            "id": id,
            "sender": sender,
            "subject": subject,
            "body": body,
        }
        email.update(kwargs)
        return email
    
    return _create_email


@pytest.fixture
def message_factory(db_session):
    """Factory for creating Message model instances in the database."""
    from app.data.models import Message
    
    def _create_message(
        gmail_id: str = "gmail_123",
        thread_id: str = "thread_456",
        sender: str = "test@example.com",
        subject: str = "Test Subject",
        body: str = "Test body",
        **kwargs
    ) -> Message:
        message = Message(
            gmail_id=gmail_id,
            thread_id=thread_id,
            sender=sender,
            subject=subject,
            body_encrypted=body.encode(),  # Simplified for testing
            **kwargs
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)
        return message
    
    return _create_message


# =============================================================================
# AIProcessor Fixtures
# =============================================================================

@pytest.fixture
def ai_processor(mock_llm_orchestrator):
    """Create an AIProcessor with mocked LLM."""
    from app.ai_processor import AIProcessor
    return AIProcessor()


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def assert_json_structure():
    """Helper to assert JSON response has expected keys."""
    def _assert(response: Dict[str, Any], expected_keys: list):
        for key in expected_keys:
            assert key in response, f"Missing key: {key}"
    return _assert
