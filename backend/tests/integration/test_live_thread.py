# Force SQLite for tests - must be set before any app imports
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

"""
Live Thread Processing Demo

Runs the REAL ThreadStateService with REAL Gemini API calls.
Use this to see actual AI outputs without sending emails or running the UI.

Usage:
    pytest tests/integration/test_live_thread.py -v -s

The -s flag shows print output so you can see the AI responses.

NOTE: This test will cost API credits and may have variable results.
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from pprint import pprint

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Message, ThreadState, Task, Base
from app.thread_state_service import ThreadStateService
from app.ai_processor import AIProcessor
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
def real_ai_processor():
    """Create a real AIProcessor that calls Gemini."""
    return AIProcessor()


@pytest.fixture
def thread_state_service(db_session, real_ai_processor):
    """ThreadStateService with real AI."""
    return ThreadStateService(db=db_session, ai_processor=real_ai_processor)


# =============================================================================
# HELPER
# =============================================================================

class LiveThreadRunner:
    """
    Run email threads with real AI and print outputs.
    """
    
    def __init__(self, db_session, thread_state_service):
        self.db = db_session
        self.tss = thread_state_service
        self.thread_id = f"live_test_{datetime.now().timestamp()}"
        self.message_count = 0
    
    def send_message(self, body: str, sender: str = "external@example.com", subject: str = "Test Thread"):
        """Send a message and print the AI's response."""
        self.message_count += 1
        
        # Create message
        message = Message(
            message_id=f"msg_{self.thread_id}_{self.message_count}",
            thread_id=self.thread_id,
            sender=sender,
            subject=subject,
            body=body,
            received_at=datetime.now(timezone.utc),
            status="inbox"
        )
        self.db.add(message)
        self.db.flush()
        
        # Process with real AI
        message_data = {"sender": sender, "subject": subject, "body": body}
        
        print(f"\n{'='*60}")
        print(f"📧 MESSAGE {self.message_count}")
        print(f"{'='*60}")
        print(f"From: {sender}")
        print(f"Body: {body}")
        print()
        
        result = self.tss.process_message(message, message_data)
        
        print(f"🤖 AI RESPONSE:")
        print(f"  Summary: {result.get('summary')}")
        print(f"  Needs Reply: {result.get('needs_reply')}")
        print(f"  Tasks: {result.get('extracted_tasks')}")
        print(f"  Decisions: {result.get('extracted_decisions')}")
        
        # Show thread state
        state = self.db.query(ThreadState).filter(
            ThreadState.thread_id == self.thread_id
        ).first()
        
        print(f"\n📊 THREAD STATE:")
        print(f"  Message Count: {state.message_count}")
        print(f"  Open Tasks: {state.open_tasks}")
        print(f"  Decisions: {state.decisions}")
        print(f"  Last Action: {state.last_action}")
        
        return result


# =============================================================================
# LIVE TESTS - Run with: pytest tests/integration/test_live_thread.py -v -s
# =============================================================================

@pytest.mark.live
class TestLiveScenario1_RequestFollowUpCompletion:
    """
    Scenario: Bob asks for a report, follows up, gets it.
    
    Watch the real AI:
    1. Extract the task from the request
    2. Recognize the follow-up (not create duplicate)
    3. Mark task complete when resolved
    """
    
    def test_full_conversation(self, db_session, thread_state_service):
        """Run the full conversation and see real AI output."""
        runner = LiveThreadRunner(db_session, thread_state_service)
        
        print("\n" + "="*60)
        print("🎬 SCENARIO 1: Request → Follow-Up → Completion")
        print("="*60)
        
        # Message 1: Initial request
        runner.send_message(
            "Hi, can you send me the Q3 sales report when you get a chance? Thanks!",
            sender="bob@example.com",
            subject="Q3 Report"
        )
        
        # Message 2: Follow-up
        runner.send_message(
            "Hey, just checking in on this. Any update?",
            sender="bob@example.com",
            subject="Re: Q3 Report"
        )
        
        # Message 3: Resolution
        runner.send_message(
            "Hi Bob, here's the Q3 report attached. Let me know if you have any questions.",
            sender="me@company.com",
            subject="Re: Q3 Report"
        )
        
        print("\n✅ Scenario complete! Review the outputs above.")


@pytest.mark.live
class TestLiveScenario2_QuotedHistoryDecision:
    """
    Scenario: CFO asks for budget review, you approve with quoted text.
    
    Watch the real AI:
    1. NOT create duplicate task from quoted text
    2. Store the decision (approval)
    """
    
    def test_full_conversation(self, db_session, thread_state_service):
        """Run the conversation with quoted history."""
        runner = LiveThreadRunner(db_session, thread_state_service)
        
        print("\n" + "="*60)
        print("🎬 SCENARIO 2: Quoted History + Decision")
        print("="*60)
        
        # Message 1: Budget review request
        runner.send_message(
            "Please review the attached Q4 budget proposal and let me know if you approve.",
            sender="cfo@company.com",
            subject="Q4 Budget Approval Needed"
        )
        
        # Message 2: Approval with quoted text
        runner.send_message(
            """> Please review the attached Q4 budget proposal and let me know if you approve.

Reviewed and approved. The numbers look solid. Go ahead with the implementation.""",
            sender="me@company.com",
            subject="Re: Q4 Budget Approval Needed"
        )
        
        print("\n✅ Scenario complete! Check if AI avoided duplicate task from quoted text.")


@pytest.mark.live
class TestLiveScenario3_SchedulingAndTopicShift:
    """
    Scenario: Colleague asks to meet, you agree, then they mention a deadline.
    
    Watch the real AI:
    1. Handle the scheduling discussion
    2. Create new task when topic shifts to deadline
    """
    
    def test_full_conversation(self, db_session, thread_state_service):
        """Run conversation with topic shift."""
        runner = LiveThreadRunner(db_session, thread_state_service)
        
        print("\n" + "="*60)
        print("🎬 SCENARIO 3: Scheduling + Topic Shift")
        print("="*60)
        
        # Message 1: Meeting request
        runner.send_message(
            "Hey, can we grab some time next week to discuss the project roadmap?",
            sender="colleague@company.com",
            subject="Catch up?"
        )
        
        # Message 2: Agreement
        runner.send_message(
            "Sure! How about Tuesday at 2pm?",
            sender="me@company.com",
            subject="Re: Catch up?"
        )
        
        # Message 3: Topic shift
        runner.send_message(
            "Tuesday 2pm works! Also, quick reminder - the project deadline is this Friday. Can you make sure the deliverables are ready?",
            sender="colleague@company.com",
            subject="Re: Catch up?"
        )
        
        print("\n✅ Scenario complete! Check if AI handled the topic shift.")


# =============================================================================
# Quick single-message test
# =============================================================================

@pytest.mark.live
def test_single_message(db_session, thread_state_service):
    """
    Quick test: process one message and see what the AI extracts.
    
    Modify the message below to test different scenarios.
    """
    runner = LiveThreadRunner(db_session, thread_state_service)
    
    print("\n" + "="*60)
    print("🎬 SINGLE MESSAGE TEST")
    print("="*60)
    
    runner.send_message(
        """Hi Team,

Just a reminder that the quarterly review is next Monday at 10am.

Please have your department reports ready by EOD Friday.

Also, Sarah - can you send me the updated org chart?

Thanks,
Manager""",
        sender="manager@company.com",
        subject="Quarterly Review Prep"
    )
    
    print("\n✅ Check the extracted tasks above!")
