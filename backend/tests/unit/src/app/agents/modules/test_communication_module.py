"""
Unit tests for CommunicationModule.

Tests email sending, reply generation, and notification methods.
Only tests methods with actual business logic per testing guidelines.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.agents.modules.communication import CommunicationModule
from app.data.models import Message, UserSettings


class TestCommunicationModuleCapabilities:
    """Tests for get_capabilities method."""

    def test_get_capabilities_returns_all_expected_capabilities(self):
        """Should return all communication capabilities."""
        # Arrange
        module = CommunicationModule()

        # Act
        capabilities = module.get_capabilities()

        # Assert
        expected_keys = [
            "send_email",
            "send_whatsapp",
            "send_slack",
            "send_sms",
            "generate_reply",
            "notify_user_email",
            "notify_user_in_app",
            "queue_digest",
        ]
        for key in expected_keys:
            assert key in capabilities
            assert isinstance(capabilities[key], str)


class TestSendEmail:
    """Tests for send_email method - has validation and message lookup logic."""

    def test_send_email_with_valid_recipient_and_draft_returns_success(self):
        """Email with 'to' and 'draft' should succeed."""
        # Arrange
        module = CommunicationModule()

        # Act
        result = module.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            draft="Hello, this is a test email."
        )

        # Assert
        assert result["sent"] is True
        assert result["to"] == "recipient@example.com"
        assert result["subject"] == "Test Subject"

    def test_send_email_missing_recipient_returns_error(self):
        """Email without 'to' should fail."""
        # Arrange
        module = CommunicationModule()

        # Act
        result = module.send_email(
            to=None,
            subject="Test",
            draft="Hello"
        )

        # Assert
        assert result["sent"] is False
        assert "Missing required" in result["error"]

    def test_send_email_missing_draft_returns_error(self):
        """Email without 'draft' should fail."""
        # Arrange
        module = CommunicationModule()

        # Act
        result = module.send_email(
            to="recipient@example.com",
            subject="Test",
            draft=None
        )

        # Assert
        assert result["sent"] is False
        assert "Missing required" in result["error"]

    def test_send_email_reply_to_message_extracts_sender(self):
        """Reply to message should use message sender as recipient."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_message = MagicMock(spec=Message)
        mock_message.sender = "original_sender@example.com"
        mock_message.subject = "Original Subject"
        mock_message.message_id = "msg_123"
        mock_message.thread_id = "thread_456"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_message

        # Act
        result = module.send_email(
            message_id=1,
            draft="Thank you for your email.",
            db=mock_db
        )

        # Assert
        assert result["sent"] is True
        assert result["to"] == "original_sender@example.com"
        assert result["subject"] == "Re: Original Subject"

    def test_send_email_reply_to_message_preserves_existing_re_prefix(self):
        """Reply subject should not duplicate 'Re:' prefix."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_message = MagicMock(spec=Message)
        mock_message.sender = "sender@example.com"
        mock_message.subject = "Re: Already a Reply"
        mock_message.message_id = "msg_123"
        mock_message.thread_id = "thread_456"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_message

        # Act
        result = module.send_email(message_id=1, draft="Got it!", db=mock_db)

        # Assert
        assert result["subject"] == "Re: Already a Reply"
        assert not result["subject"].startswith("Re: Re:")

    def test_send_email_message_not_found_returns_error(self):
        """Reply to non-existent message should fail."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = module.send_email(message_id=999, draft="Hello", db=mock_db)

        # Assert
        assert result["sent"] is False
        assert "not found" in result["error"].lower()

    def test_send_email_handles_exception_gracefully(self):
        """Send email should handle exceptions gracefully."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database connection failed")

        # Act
        result = module.send_email(
            message_id=1,
            draft="Test",
            db=mock_db
        )

        # Assert
        assert result["sent"] is False
        assert "Database connection failed" in result["error"]


class TestGenerateReply:
    """Tests for generate_reply method - has AI integration and message lookup logic."""

    @patch('app.agents.modules.communication.CommunicationModule._load_prompt')
    def test_generate_reply_with_body_returns_draft(self, mock_load):
        """Generate reply with message body should return AI draft."""
        # Arrange
        mock_load.return_value = "Generate reply for:\n{sender}\n{subject}\n{body}\n{context_section}"
        
        module = CommunicationModule()
        # Mock the orchestrator after instantiation
        module._orchestrator = MagicMock()
        module._orchestrator.generate.return_value = {
            "draft": "Thank you for reaching out. I will review this.",
            "subject_line": "Re: Test Subject",
            "tone": "professional",
            "confidence": 0.85
        }

        # Act
        result = module.generate_reply(
            message_body="Hi, can you help me with this?",
            message_subject="Test Subject",
            sender_email="sender@example.com",
            tone="professional"
        )

        # Assert
        assert result["success"] is True
        assert "Thank you" in result["draft"]
        assert result["requires_user_approval"] is True

    def test_generate_reply_missing_body_returns_error(self):
        """Generate reply without message body should fail."""
        # Arrange
        module = CommunicationModule()

        # Act
        result = module.generate_reply(
            message_body=None,
            message_subject="Subject"
        )

        # Assert
        assert result["success"] is False
        assert "No message content" in result["error"]

    @patch('app.agents.modules.communication.CommunicationModule._load_prompt')
    def test_generate_reply_from_message_id_fetches_message(self, mock_load):
        """Generate reply with message_id should fetch message from DB."""
        # Arrange
        mock_load.return_value = "Prompt: {sender} {subject} {body} {context_section}"
        
        module = CommunicationModule()
        module._orchestrator = MagicMock()
        module._orchestrator.generate.return_value = {
            "draft": "Thanks for the update.",
            "tone": "professional"
        }

        mock_db = MagicMock()
        mock_message = MagicMock(spec=Message)
        mock_message.decrypted_body = "Original email content"
        mock_message.body = "Fallback body"
        mock_message.subject = "Original Subject"
        mock_message.sender = "sender@example.com"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_message

        # Act
        result = module.generate_reply(message_id=1, db=mock_db)

        # Assert
        assert result["success"] is True
        assert result["draft"] == "Thanks for the update."

    def test_generate_reply_message_not_found_returns_error(self):
        """Generate reply with non-existent message_id should fail."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = module.generate_reply(message_id=999, db=mock_db)

        # Assert
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch('app.agents.modules.communication.CommunicationModule._load_prompt')
    def test_generate_reply_includes_intent_and_tone(self, mock_load):
        """Generate reply should pass intent and tone to prompt."""
        # Arrange
        mock_load.return_value = "Prompt: {sender} {subject} {body} {context_section}"
        
        module = CommunicationModule()
        module._orchestrator = MagicMock()
        module._orchestrator.generate.return_value = {"draft": "I decline.", "tone": "formal"}

        # Act
        result = module.generate_reply(
            message_body="Join our meeting?",
            message_subject="Meeting Invite",
            sender_email="inviter@example.com",
            tone="formal",
            intent="decline politely"
        )

        # Assert
        assert result["success"] is True
        assert result["tone_used"] == "formal"

    @patch('app.agents.modules.communication.CommunicationModule._load_prompt')
    def test_generate_reply_handles_ai_exception(self, mock_load):
        """Generate reply should handle AI exceptions gracefully."""
        # Arrange
        mock_load.return_value = "Prompt template"

        module = CommunicationModule()
        module._orchestrator = MagicMock()
        module._orchestrator.generate.side_effect = Exception("AI service unavailable")

        # Act
        result = module.generate_reply(
            message_body="Test content",
            message_subject="Test"
        )

        # Assert
        assert result["success"] is False
        assert result["draft"] is None
        assert "AI service unavailable" in result["error"]


class TestNotifyUserEmail:
    """Tests for notify_user_email method - has settings lookup fallback logic."""

    def test_notify_user_email_with_provided_email_returns_success(self):
        """Notification with user_email should succeed."""
        # Arrange
        module = CommunicationModule()

        # Act
        result = module.notify_user_email(
            subject="Urgent Task Reminder",
            body="You have a deadline in 2 hours.",
            priority="urgent",
            user_email="user@example.com"
        )

        # Assert
        assert result["sent"] is True
        assert result["to"] == "user@example.com"
        assert result["priority"] == "urgent"

    def test_notify_user_email_fetches_email_from_settings(self):
        """Notification without user_email should fetch from UserSettings."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_settings = MagicMock(spec=UserSettings)
        mock_settings.user_email = "settings@example.com"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings

        # Act
        result = module.notify_user_email(
            subject="Meeting Prep",
            body="Your meeting starts in 30 minutes.",
            db=mock_db,
            user_id="user_123"
        )

        # Assert
        assert result["sent"] is True
        assert result["to"] == "settings@example.com"

    def test_notify_user_email_no_email_configured_returns_error(self):
        """Notification without any email should fail."""
        # Arrange
        module = CommunicationModule()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = module.notify_user_email(
            subject="Test",
            body="Test body",
            db=mock_db,
            user_id="user_123"
        )

        # Assert
        assert result["sent"] is False
        assert "No user email" in result["error"]
