# Force SQLite for tests - must be set before any app imports
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

"""
Golden-Thread Integration Tests

Tests that the Universal Inbox Brain correctly updates thread state
as emails arrive in a conversation.

Test Philosophy:
- Replays real email conversation sequences
- Uses deterministic mocked AI responses (no randomness)
- Asserts thread state after every message
- Validates: tasks, decisions, needs_reply, summary updates

Coverage:
1. Thread Understanding
2. Needs-Reply Logic
3. Task Extraction & Deduplication
4. Follow-Up Detection
5. Decision Handling
6. Thread State Transitions
7. Quoted History Immunity
8. Scheduling Signals
9. Performance Guarantees (1 AI call per message)
10. Determinism & Trust
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from copy import deepcopy

from app.models import Message, Task, ThreadState, Base
from app.thread_state_service import ThreadStateService


# =============================================================================
# TEST HARNESS: Deterministic AI Processor
# =============================================================================

class DeterministicAIProcessor:
    """
    AI Processor with scripted responses for each message.
    
    WHY: Tests must be deterministic. Real LLMs are random.
    HOW: Each message index in a thread has a predefined response.
    """
    
    def __init__(self, responses: List[Dict[str, Any]]):
        """
        Args:
            responses: List of AI responses, one per message in order
        """
        self.responses = responses
        self.call_count = 0
        self.call_log = []
    
    def init_thread_state(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return scripted response for first message."""
        response = self._get_next_response("init_thread_state", message_data)
        return response
    
    def update_thread_state(
        self, 
        current_state: Dict[str, Any], 
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return scripted response for subsequent messages."""
        response = self._get_next_response("update_thread_state", message_data)
        return response
    
    def _get_next_response(self, method: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get next response from script and log the call."""
        if self.call_count >= len(self.responses):
            raise AssertionError(
                f"More messages processed than responses scripted. "
                f"Expected {len(self.responses)}, got call #{self.call_count + 1}"
            )
        
        response = self.responses[self.call_count]
        self.call_log.append({
            "call_index": self.call_count,
            "method": method,
            "message_subject": message_data.get("subject"),
        })
        self.call_count += 1
        return response


# =============================================================================
# TEST HARNESS: Email Thread Runner
# =============================================================================

class EmailThreadRunner:
    """
    Helper to replay email conversations and assert state.
    
    Usage:
        runner = EmailThreadRunner(db_session, ai_responses)
        runner.send_message("Send me the report", sender="bob@example.com")
        runner.assert_state(needs_reply=True, task_count=1)
    """
    
    def __init__(self, db_session, ai_responses: List[Dict[str, Any]]):
        self.db = db_session
        self.ai_processor = DeterministicAIProcessor(ai_responses)
        self.thread_state_service = ThreadStateService(
            db=self.db, 
            ai_processor=self.ai_processor
        )
        self.thread_id = f"test_thread_{datetime.now().timestamp()}"
        self.message_count = 0
        self.states_after_each_message = []
    
    def send_message(
        self,
        body: str,
        sender: str = "external@example.com",
        subject: str = None
    ) -> Dict[str, Any]:
        """
        Simulate receiving an email in the thread.
        
        Args:
            body: Email body text
            sender: Sender email
            subject: Subject (defaults to "Test Thread")
        
        Returns:
            Processing result from ThreadStateService
        """
        self.message_count += 1
        subject = subject or "Test Thread"
        
        # Create message in DB
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
        
        # Process message
        message_data = {
            "sender": sender,
            "subject": subject,
            "body": body,
        }
        result = self.thread_state_service.process_message(message, message_data)
        
        # Store state snapshot
        thread_state = self.get_thread_state()
        self.states_after_each_message.append(deepcopy(thread_state))
        
        return result
    
    def get_thread_state(self):
        """Get current thread state from DB."""
        return self.db.query(ThreadState).filter(
            ThreadState.thread_id == self.thread_id
        ).first()
    
    def get_tasks(self) -> List:
        """Get all tasks for this thread."""
        return self.db.query(Task).filter(
            Task.thread_id == self.thread_id
        ).all()
    
    def assert_state(
        self,
        needs_reply: bool = None,
        task_count: int = None,
        open_task_count: int = None,
        decision_count: int = None,
        summary_contains: str = None,
        summary_max_length: int = None,
    ):
        """
        Assert current thread state matches expectations.
        
        All parameters are optional - only provided ones are checked.
        """
        state = self.get_thread_state()
        assert state is not None, "Thread state should exist"
        
        if needs_reply is not None:
            assert state.needs_reply == needs_reply, (
                f"needs_reply: expected {needs_reply}, got {state.needs_reply}"
            )
        
        if task_count is not None:
            tasks = self.get_tasks()
            assert len(tasks) == task_count, (
                f"task_count: expected {task_count}, got {len(tasks)}"
            )
        
        if open_task_count is not None:
            open_tasks = [t for t in (state.open_tasks or []) if t.get("status") == "open"]
            assert len(open_tasks) == open_task_count, (
                f"open_task_count: expected {open_task_count}, got {len(open_tasks)}"
            )
        
        if decision_count is not None:
            decisions = state.decisions or []
            assert len(decisions) == decision_count, (
                f"decision_count: expected {decision_count}, got {len(decisions)}"
            )
        
        if summary_contains is not None:
            assert summary_contains.lower() in (state.summary or "").lower(), (
                f"summary should contain '{summary_contains}', got: '{state.summary}'"
            )
        
        if summary_max_length is not None:
            assert len(state.summary or "") <= summary_max_length, (
                f"summary too long: {len(state.summary)} > {summary_max_length}"
            )
    
    def assert_no_duplicate_tasks(self):
        """Assert no duplicate task titles exist."""
        tasks = self.get_tasks()
        titles = [t.title.lower() for t in tasks]
        assert len(titles) == len(set(titles)), (
            f"Duplicate tasks found: {titles}"
        )
    
    def assert_ai_call_count(self, expected: int):
        """Assert exactly N AI calls were made (1 per message)."""
        assert self.ai_processor.call_count == expected, (
            f"AI call count: expected {expected}, got {self.ai_processor.call_count}"
        )


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
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


# =============================================================================
# SCENARIO 1: Request → Follow-Up → Completion
# =============================================================================

class TestScenario1_RequestFollowUpCompletion:
    """
    Tests: Thread Understanding, Needs-Reply, Task Extraction, Follow-Up Detection
    
    Scenario:
    1. Bob requests "Send me the Q3 report"
    2. Bob follows up "Any update on this?"
    3. User replies "Here's the report attached"
    
    Expected:
    - Task created on msg 1
    - No duplicate on msg 2
    - Task completed on msg 3
    """
    
    @pytest.fixture
    def ai_responses(self):
        """Scripted AI responses for this scenario."""
        return [
            # Message 1: Initial request
            {
                "summary": "Bob requested Q3 report",
                "needs_reply": True,
                "last_action": "Requested Q3 report",
                "last_action_by": "bob@example.com",
                "tasks": [
                    {
                        "title": "Send Q3 report to Bob",
                        "task_type": "explicit",
                        "priority": "normal",
                    }
                ],
                "decisions": [],
            },
            # Message 2: Follow-up ("any update?")
            {
                "summary_update": "Bob following up on Q3 report request",
                "needs_reply": True,
                "last_action": "Sent follow-up",
                "last_action_by": "bob@example.com",
                "new_tasks": [],  # NO new task - follow-up, not new request
                "task_updates": [],
                "new_decisions": [],
            },
            # Message 3: Completion
            {
                "summary_update": "Q3 report sent to Bob",
                "needs_reply": False,
                "last_action": "Sent report",
                "last_action_by": "me@example.com",
                "new_tasks": [],
                "task_updates": [
                    {
                        "existing_task_title": "Send Q3 report to Bob",
                        "new_status": "completed",
                    }
                ],
                "new_decisions": [],
            },
        ]
    
    @pytest.mark.integration
    def test_task_created_on_first_message(self, db_session, ai_responses):
        """Task is created from initial request."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message(
            "Hi, can you send me the Q3 report?",
            sender="bob@example.com"
        )
        
        runner.assert_state(
            needs_reply=True,
            task_count=1,
            open_task_count=1,
        )
    
    @pytest.mark.integration
    def test_no_duplicate_on_followup(self, db_session, ai_responses):
        """Follow-up message does not create duplicate task."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        # Message 1: Initial request
        runner.send_message(
            "Hi, can you send me the Q3 report?",
            sender="bob@example.com"
        )
        
        # Message 2: Follow-up
        runner.send_message(
            "Any update on this?",
            sender="bob@example.com"
        )
        
        runner.assert_state(
            needs_reply=True,
            task_count=1,  # Still only 1 task
        )
        runner.assert_no_duplicate_tasks()
    
    @pytest.mark.integration
    def test_task_completed_on_resolution(self, db_session, ai_responses):
        """Task is marked completed when resolved."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        # Message 1: Request
        runner.send_message("Send me the Q3 report?", sender="bob@example.com")
        
        # Message 2: Follow-up
        runner.send_message("Any update?", sender="bob@example.com")
        
        # Message 3: Resolution
        runner.send_message(
            "Here's the Q3 report attached.",
            sender="me@example.com"
        )
        
        runner.assert_state(
            needs_reply=False,
            task_count=1,
            open_task_count=0,  # Task completed
        )
    
    @pytest.mark.integration
    def test_one_ai_call_per_message(self, db_session, ai_responses):
        """Performance: exactly 1 AI call per message."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message("Send me the Q3 report?", sender="bob@example.com")
        runner.send_message("Any update?", sender="bob@example.com")
        runner.send_message("Here's the report.", sender="me@example.com")
        
        runner.assert_ai_call_count(3)
    
    @pytest.mark.integration
    def test_determinism(self, db_session, ai_responses):
        """Same input produces same output."""
        # Run 1
        runner1 = EmailThreadRunner(db_session, ai_responses)
        runner1.send_message("Send me the Q3 report?", sender="bob@example.com")
        runner1.send_message("Any update?", sender="bob@example.com")
        runner1.send_message("Here's the report.", sender="me@example.com")
        state1 = runner1.get_thread_state()
        
        # Run 2 with fresh responses (same data)
        runner2 = EmailThreadRunner(db_session, deepcopy(ai_responses))
        runner2.send_message("Send me the Q3 report?", sender="bob@example.com")
        runner2.send_message("Any update?", sender="bob@example.com")
        runner2.send_message("Here's the report.", sender="me@example.com")
        state2 = runner2.get_thread_state()
        
        # Compare
        assert state1.needs_reply == state2.needs_reply
        assert len(state1.open_tasks or []) == len(state2.open_tasks or [])


# =============================================================================
# SCENARIO 2: Quoted History + Decision
# =============================================================================

class TestScenario2_QuotedHistoryDecision:
    """
    Tests: Quoted History Immunity, Decision Handling
    
    Scenario:
    1. "Please review the budget"
    2. Reply with quoted text: "> Please review the budget\nApproved."
    
    Expected:
    - Task created on msg 1
    - Decision stored on msg 2
    - NO duplicate task from quoted text
    """
    
    @pytest.fixture
    def ai_responses(self):
        """Scripted AI responses."""
        return [
            # Message 1: Budget review request
            {
                "summary": "Budget review requested",
                "needs_reply": True,
                "last_action": "Requested budget review",
                "last_action_by": "cfo@example.com",
                "tasks": [
                    {
                        "title": "Review budget",
                        "task_type": "explicit",
                        "priority": "high",
                    }
                ],
                "decisions": [],
            },
            # Message 2: Approval (with quoted history)
            {
                "summary_update": "Budget approved",
                "needs_reply": False,
                "last_action": "Approved budget",
                "last_action_by": "me@example.com",
                "new_tasks": [],  # NO new tasks from quoted text
                "task_updates": [
                    {
                        "existing_task_title": "Review budget",
                        "new_status": "completed",
                    }
                ],
                "new_decisions": [
                    {
                        "decision": "Budget approved",
                        "made_by": "me@example.com",
                    }
                ],
            },
        ]
    
    @pytest.mark.integration
    def test_quoted_text_does_not_create_duplicate_task(self, db_session, ai_responses):
        """Quoted old requests do not recreate tasks."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        # Message 1
        runner.send_message(
            "Please review the attached budget for Q4.",
            sender="cfo@example.com"
        )
        runner.assert_state(task_count=1)
        
        # Message 2 with quoted text
        runner.send_message(
            "> Please review the attached budget for Q4.\n\nApproved. Looks good.",
            sender="me@example.com"
        )
        
        # Still only 1 task, not 2
        runner.assert_state(task_count=1)
        runner.assert_no_duplicate_tasks()
    
    @pytest.mark.integration
    def test_decision_stored_and_closes_task(self, db_session, ai_responses):
        """Explicit approval is stored as decision and closes task."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message("Please review the budget.", sender="cfo@example.com")
        runner.send_message("> Please review\n\nApproved.", sender="me@example.com")
        
        runner.assert_state(
            needs_reply=False,
            decision_count=1,
            open_task_count=0,
        )
    
    @pytest.mark.integration
    def test_summary_reflects_current_state(self, db_session, ai_responses):
        """Summary reflects current state, not full history."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message("Please review the budget.", sender="cfo@example.com")
        runner.send_message("Approved.", sender="me@example.com")
        
        state = runner.get_thread_state()
        # Summary should reflect approval, not just original request
        assert "approved" in state.summary.lower()


# =============================================================================
# SCENARIO 3: Scheduling + Decision + Topic Shift
# =============================================================================

class TestScenario3_SchedulingDecisionTopicShift:
    """
    Tests: Scheduling Signals, Thread Understanding (topic shift)
    
    Scenario:
    1. "Can we meet next week?"
    2. "Tuesday 2pm works for me"
    3. "Also, the project deadline is Friday"
    
    Expected:
    - Scheduling detected on msg 1
    - Decision on msg 2
    - New task on msg 3 (topic shift)
    """
    
    @pytest.fixture
    def ai_responses(self):
        """Scripted AI responses."""
        return [
            # Message 1: Scheduling request
            {
                "summary": "Meeting requested for next week",
                "needs_reply": True,
                "last_action": "Requested meeting",
                "last_action_by": "colleague@example.com",
                "tasks": [],
                "decisions": [],
                # Note: scheduling_intent would be handled separately
            },
            # Message 2: Agreement
            {
                "summary_update": "Meeting scheduled for Tuesday 2pm",
                "needs_reply": False,
                "last_action": "Confirmed Tuesday 2pm",
                "last_action_by": "me@example.com",
                "new_tasks": [],
                "task_updates": [],
                "new_decisions": [
                    {
                        "decision": "Meeting scheduled for Tuesday 2pm",
                        "made_by": "me@example.com",
                    }
                ],
            },
            # Message 3: Topic shift
            {
                "summary_update": "Meeting Tuesday 2pm; project deadline Friday",
                "needs_reply": True,
                "last_action": "Mentioned project deadline",
                "last_action_by": "colleague@example.com",
                "new_tasks": [
                    {
                        "title": "Project deadline Friday",
                        "task_type": "explicit",
                        "priority": "high",
                    }
                ],
                "task_updates": [],
                "new_decisions": [],
            },
        ]
    
    @pytest.mark.integration
    def test_scheduling_creates_decision(self, db_session, ai_responses):
        """Scheduling agreement creates a decision."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message("Can we meet next week?", sender="colleague@example.com")
        runner.send_message("Tuesday 2pm works.", sender="me@example.com")
        
        runner.assert_state(decision_count=1)
    
    @pytest.mark.integration
    def test_topic_shift_creates_new_task(self, db_session, ai_responses):
        """Topic shift creates new task without losing prior context."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message("Can we meet next week?", sender="colleague@example.com")
        runner.assert_state(task_count=0)
        
        runner.send_message("Tuesday 2pm works.", sender="me@example.com")
        runner.assert_state(task_count=0, decision_count=1)
        
        runner.send_message(
            "Also, the project deadline is Friday.",
            sender="colleague@example.com"
        )
        runner.assert_state(task_count=1, decision_count=1)
    
    @pytest.mark.integration
    def test_summary_updates_incrementally(self, db_session, ai_responses):
        """Summary updates but doesn't grow unbounded."""
        runner = EmailThreadRunner(db_session, ai_responses)
        
        runner.send_message("Can we meet?", sender="colleague@example.com")
        runner.send_message("Tuesday 2pm.", sender="me@example.com")
        runner.send_message("Also, deadline Friday.", sender="colleague@example.com")
        
        state = runner.get_thread_state()
        # Summary should be concise, not a transcript
        runner.assert_state(summary_max_length=200)


# =============================================================================
# CROSS-SCENARIO: Determinism & Trust
# =============================================================================

class TestDeterminismAndTrust:
    """
    Tests: Same message sequence → same thread state
    """
    
    @pytest.mark.integration
    def test_identical_runs_produce_identical_state(self, db_session):
        """Running the same scenario twice produces identical results."""
        ai_responses = [
            {
                "summary": "Test request",
                "needs_reply": True,
                "last_action": "Requested",
                "last_action_by": "test@example.com",
                "tasks": [{"title": "Test task", "task_type": "explicit"}],
                "decisions": [],
            },
            {
                "summary_update": "Task completed",
                "needs_reply": False,
                "last_action": "Completed",
                "last_action_by": "me@example.com",
                "new_tasks": [],
                "task_updates": [
                    {"existing_task_title": "Test task", "new_status": "completed"}
                ],
                "new_decisions": [],
            },
        ]
        
        # Run 1
        runner1 = EmailThreadRunner(db_session, deepcopy(ai_responses))
        runner1.send_message("Do the thing", sender="test@example.com")
        runner1.send_message("Done", sender="me@example.com")
        
        # Run 2
        runner2 = EmailThreadRunner(db_session, deepcopy(ai_responses))
        runner2.send_message("Do the thing", sender="test@example.com")
        runner2.send_message("Done", sender="me@example.com")
        
        # Compare states
        state1 = runner1.states_after_each_message
        state2 = runner2.states_after_each_message
        
        assert len(state1) == len(state2)
        for i, (s1, s2) in enumerate(zip(state1, state2)):
            assert s1.needs_reply == s2.needs_reply, f"Mismatch at message {i}"
            assert len(s1.open_tasks or []) == len(s2.open_tasks or [])
