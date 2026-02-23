# Force SQLite for tests - must be set before any app imports
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

"""
Integration Tests for CommunicationModule

These tests call the REAL Gemini API to verify:
- Reply generation produces valid, contextual responses
- Response structure matches expected schema
- Error handling works with real API failures

Usage:
    pytest tests/integration/test_communication_integration.py -v -s

The -s flag shows print output so you can see the AI responses.

NOTE: These tests will cost API credits and may have variable results.
Mark with @pytest.mark.live to skip in CI.
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from pprint import pprint

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.data.models import Message, Base
from app.agents.modules.communication import CommunicationModule
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def communication_module():
    """Create a real CommunicationModule that calls Gemini API."""
    return CommunicationModule()


# =============================================================================
# SAMPLE EMAIL CONTENT FOR TESTS
# =============================================================================

SAMPLE_EMAILS = {
    "meeting_request": {
        "sender": "colleague@company.com",
        "subject": "Quick sync next week?",
        "body": """Hi,

I wanted to see if you're free for a 30-minute call next week to discuss 
the upcoming product launch. I'm flexible on timing - let me know what 
works for you.

Looking forward to connecting!

Best,
Sarah"""
    },
    "urgent_deadline": {
        "sender": "manager@company.com",
        "subject": "URGENT: Report needed by Friday",
        "body": """Hi,

I need the Q4 financial report by end of day Friday. The board meeting 
has been moved up and we need this data ASAP.

Please confirm you received this and can deliver on time.

Thanks,
Michael"""
    },
    "follow_up_question": {
        "sender": "client@external.com",
        "subject": "Re: Project Proposal",
        "body": """Thanks for sending over the proposal. I had a couple of questions:

1. Can you clarify the timeline for Phase 2?
2. What's the estimated budget for the additional features we discussed?
3. Is there flexibility on the payment terms?

Looking forward to your response.

Best regards,
Jennifer"""
    },
    "simple_thank_you": {
        "sender": "teammate@company.com",
        "subject": "Re: Design Review",
        "body": "Thanks for the feedback on the designs! Really helpful - I'll make those changes today."
    }
}


# =============================================================================
# INTEGRATION TESTS - Call Real Gemini API
# =============================================================================

@pytest.mark.live
class TestGenerateReplyIntegration:
    """
    Integration tests for generate_reply with real Gemini API.
    
    These verify:
    - AI returns properly structured responses
    - Responses are contextually relevant
    - Different tones produce different outputs
    """
    
    def test_generate_reply_meeting_request_returns_valid_structure(self, communication_module):
        """Generate reply to meeting request should return valid response structure."""
        # Arrange
        email = SAMPLE_EMAILS["meeting_request"]
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Meeting Request Reply")
        print("="*60)
        print(f"From: {email['sender']}")
        print(f"Subject: {email['subject']}")
        print(f"Body:\n{email['body']}")
        
        result = communication_module.generate_reply(
            message_body=email["body"],
            message_subject=email["subject"],
            sender_email=email["sender"],
            tone="professional",
            intent="accept meeting and suggest times"
        )
        
        print("\n🤖 AI RESPONSE:")
        pprint(result)
        
        # Assert - Structure validation
        assert result["success"] is True, f"Failed with error: {result.get('error')}"
        assert "draft" in result
        assert result["draft"] is not None
        assert len(result["draft"]) > 50, "Draft should be substantive"
        assert result["requires_user_approval"] is True
        
        # Assert - Content relevance
        draft_lower = result["draft"].lower()
        assert any(word in draft_lower for word in ["meet", "call", "time", "schedule", "available"]), \
            "Reply should mention scheduling-related content"
    
    def test_generate_reply_urgent_deadline_returns_acknowledgment(self, communication_module):
        """Generate reply to urgent request should acknowledge urgency."""
        # Arrange
        email = SAMPLE_EMAILS["urgent_deadline"]
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Urgent Deadline Reply")
        print("="*60)
        
        result = communication_module.generate_reply(
            message_body=email["body"],
            message_subject=email["subject"],
            sender_email=email["sender"],
            tone="professional",
            intent="confirm receipt and commit to deadline"
        )
        
        print("\n🤖 AI RESPONSE:")
        pprint(result)
        
        # Assert
        assert result["success"] is True
        assert result["draft"] is not None
        
        # Check urgency is acknowledged
        draft_lower = result["draft"].lower()
        assert any(word in draft_lower for word in ["friday", "confirm", "deliver", "report", "understood"]), \
            "Reply should acknowledge the deadline/request"
    
    def test_generate_reply_questions_addresses_points(self, communication_module):
        """Generate reply to multiple questions should address them."""
        # Arrange
        email = SAMPLE_EMAILS["follow_up_question"]
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Multi-Question Reply")
        print("="*60)
        
        result = communication_module.generate_reply(
            message_body=email["body"],
            message_subject=email["subject"],
            sender_email=email["sender"],
            tone="professional",
            intent="answer the questions about timeline, budget, and payment terms"
        )
        
        print("\n🤖 AI RESPONSE:")
        pprint(result)
        
        # Assert
        assert result["success"] is True
        assert result["draft"] is not None
        assert len(result["draft"]) > 100, "Reply to multiple questions should be detailed"
    
    def test_generate_reply_simple_email_is_concise(self, communication_module):
        """Generate reply to simple thank-you should be brief."""
        # Arrange
        email = SAMPLE_EMAILS["simple_thank_you"]
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Simple Thank You Reply")
        print("="*60)
        
        result = communication_module.generate_reply(
            message_body=email["body"],
            message_subject=email["subject"],
            sender_email=email["sender"],
            tone="friendly",
            intent="acknowledge"
        )
        
        print("\n🤖 AI RESPONSE:")
        pprint(result)
        
        # Assert
        assert result["success"] is True
        assert result["draft"] is not None
        # Simple reply shouldn't be overly long
        assert len(result["draft"]) < 500, "Reply to simple email should be concise"
    
    def test_generate_reply_different_tones_produce_different_outputs(self, communication_module):
        """Same email with different tones should produce different replies."""
        # Arrange
        email = SAMPLE_EMAILS["meeting_request"]
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Tone Comparison (Professional vs Casual)")
        print("="*60)
        
        professional_result = communication_module.generate_reply(
            message_body=email["body"],
            message_subject=email["subject"],
            sender_email=email["sender"],
            tone="professional"
        )
        
        casual_result = communication_module.generate_reply(
            message_body=email["body"],
            message_subject=email["subject"],
            sender_email=email["sender"],
            tone="casual"
        )
        
        print("\n🤖 PROFESSIONAL TONE:")
        print(professional_result.get("draft", "ERROR"))
        
        print("\n🤖 CASUAL TONE:")
        print(casual_result.get("draft", "ERROR"))
        
        # Assert
        assert professional_result["success"] is True
        assert casual_result["success"] is True
        
        # They should be different (not exact match)
        assert professional_result["draft"] != casual_result["draft"], \
            "Different tones should produce different replies"


@pytest.mark.live
class TestGenerateReplyWithDatabaseMessage:
    """
    Integration tests that verify reply generation from database messages.
    """
    
    def test_generate_reply_from_db_message(self, communication_module, db_session):
        """Generate reply from message_id should fetch and process correctly."""
        # Arrange - Create a message in the database
        message = Message(
            message_id="test_msg_001",
            thread_id="test_thread_001",
            sender="test@example.com",
            subject="Integration Test Email",
            body="Hi, can you please review the attached document and let me know your thoughts? Thanks!",
            received_at=datetime.now(timezone.utc),
            status="inbox"
        )
        db_session.add(message)
        db_session.commit()
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Reply from Database Message")
        print("="*60)
        print(f"Message ID in DB: {message.id}")
        
        result = communication_module.generate_reply(
            message_id=message.id,
            db=db_session,
            tone="professional",
            intent="acknowledge and promise review"
        )
        
        print("\n🤖 AI RESPONSE:")
        pprint(result)
        
        # Assert
        assert result["success"] is True
        assert "draft" in result
        assert result["draft"] is not None
        
        # Should reference the document review
        draft_lower = result["draft"].lower()
        assert any(word in draft_lower for word in ["review", "document", "look", "check"]), \
            "Reply should address the document review request"


@pytest.mark.live
class TestGenerateReplyEdgeCases:
    """
    Edge case tests for reply generation.
    """
    
    def test_generate_reply_very_long_email_handles_truncation(self, communication_module):
        """Should handle very long emails without error."""
        # Arrange - Create email with 5000+ characters
        long_body = "This is a test paragraph. " * 300  # ~7500 chars
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Very Long Email (truncation)")
        print("="*60)
        print(f"Email body length: {len(long_body)} characters")
        
        result = communication_module.generate_reply(
            message_body=long_body,
            message_subject="Long Email Test",
            sender_email="test@example.com",
            tone="professional"
        )
        
        print("\n🤖 AI RESPONSE:")
        print(f"Success: {result.get('success')}")
        print(f"Draft length: {len(result.get('draft', ''))}")
        
        # Assert - Should not error
        assert result["success"] is True
        assert result["draft"] is not None
    
    def test_generate_reply_email_with_special_characters(self, communication_module):
        """Should handle emails with unicode and special characters."""
        # Arrange
        special_body = """Hi! 👋

Thanks for the update. Here are my thoughts:

• Point 1: The numbers look great – better than expected!
• Point 2: We need to address the "edge cases" mentioned
• Point 3: Let's discuss the €50,000 budget variance

Best regards,
José García-López
Senior Analyst • Finance Dept.
"""
        
        # Act
        print("\n" + "="*60)
        print("📧 TESTING: Special Characters & Unicode")
        print("="*60)
        
        result = communication_module.generate_reply(
            message_body=special_body,
            message_subject="Re: Q3 Analysis",
            sender_email="jose.garcia@example.com",
            tone="professional"
        )
        
        print("\n🤖 AI RESPONSE:")
        pprint(result)
        
        # Assert
        assert result["success"] is True
        assert result["draft"] is not None


# =============================================================================
# Quick single test for manual verification
# =============================================================================

@pytest.mark.live
def test_quick_reply_generation(communication_module):
    """
    Quick test: generate one reply and see output.
    
    Modify the email content below to test different scenarios.
    """
    print("\n" + "="*60)
    print("🎬 QUICK REPLY TEST")
    print("="*60)
    
    result = communication_module.generate_reply(
        message_body="""Hi Team,

Just a reminder that the quarterly review is next Monday at 10am.

Please have your department reports ready by EOD Friday.

Also, can someone send me the updated org chart?

Thanks,
Manager""",
        message_subject="Quarterly Review Prep",
        sender_email="manager@company.com",
        tone="professional",
        intent="acknowledge and confirm attendance"
    )
    
    print("\n🤖 GENERATED REPLY:")
    print("-" * 40)
    if result["success"]:
        print(result["draft"])
    else:
        print(f"ERROR: {result.get('error')}")
    print("-" * 40)
    
    assert result["success"] is True
    print("\n✅ Test passed!")
