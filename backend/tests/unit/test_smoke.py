"""
Smoke test to verify test infrastructure works.
This file can be deleted once real tests are added.
"""
import pytest


class TestInfrastructure:
    """Verify test infrastructure is set up correctly."""
    
    @pytest.mark.unit
    def test_fixtures_load(self, email_factory):
        """Test that fixtures can be loaded."""
        email = email_factory(
            id="smoke_test",
            subject="Infrastructure Smoke Test"
        )
        assert email["id"] == "smoke_test"
        assert email["subject"] == "Infrastructure Smoke Test"
    
    @pytest.mark.unit
    def test_mock_llm_response(self, mock_llm_response):
        """Test that mock LLM response fixture works."""
        assert "summary" in mock_llm_response
        assert "needs_reply" in mock_llm_response
        assert "tasks" in mock_llm_response
    
    @pytest.mark.unit
    def test_sample_gmail_message(self, sample_gmail_message):
        """Test that sample Gmail message fixture works."""
        assert sample_gmail_message["id"] == "test_msg_123"
        assert "sender" in sample_gmail_message
        assert "subject" in sample_gmail_message
        assert "body" in sample_gmail_message
