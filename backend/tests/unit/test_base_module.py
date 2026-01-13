"""
Unit Tests for BaseModule (app/agents/modules/base.py)

=== WHAT IS BaseModule? ===
BaseModule is an abstract base class that all assistant modules inherit from.
It provides common functionality like:
- Automatic module naming
- Input validation 
- Execution logging
- A standard way to run capabilities

=== HOW TO READ THESE TESTS ===
Each test class focuses on one method. Each test function tests one specific behavior.
Test names follow the pattern: test_<what_we_are_testing>_<expected_behavior>

Run tests with: pytest tests/unit/test_base_module.py -v
"""
import pytest
import sys
import importlib.util
from datetime import datetime
from pathlib import Path


# -----------------------------------------------------------------------------
# SETUP: Load BaseModule directly from file
# -----------------------------------------------------------------------------
# We use importlib to load BaseModule directly because the normal import path
# (from app.agents.modules.base import BaseModule) would trigger imports of
# google.genai and other heavy dependencies we don't need for these tests.

def load_base_module():
    """Load BaseModule directly from file to avoid import chain."""
    module_path = Path(__file__).parent.parent.parent / "app" / "agents" / "modules" / "base.py"
    spec = importlib.util.spec_from_file_location("base", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BaseModule


BaseModule = load_base_module()


# -----------------------------------------------------------------------------
# SAMPLE MODULE: A realistic email-handling module for testing
# -----------------------------------------------------------------------------
# Since BaseModule is abstract (can't be instantiated directly), 
# we create a concrete class that mimics what real assistant modules do.

class EmailProcessingModule(BaseModule):
    """
    A sample module that handles email-related tasks.
    Used to test the BaseModule functionality with realistic examples.
    """
    
    def get_capabilities(self):
        """List what this module can do."""
        return {
            "summarize_email": "Generate a brief summary of an email",
            "draft_reply": "Create a professional reply draft",
            "extract_action_items": "Extract tasks and action items from an email"
        }
    
    def summarize_email(self, subject: str, body: str) -> str:
        """Generate a summary for an email."""
        return f"Summary: Email about '{subject}' - {len(body)} chars"
    
    def draft_reply(self, original_email: str, tone: str = "professional") -> str:
        """Generate a reply draft based on the original email."""
        return f"Thank you for your email. [Draft reply in {tone} tone]"
    
    def extract_action_items(self, email_body: str) -> list:
        """Extract action items from email (simplified for testing)."""
        # In reality this would use AI - here we just return a mock
        return ["Follow up with client", "Schedule meeting"]


class BrokenModule(BaseModule):
    """A module with a method that always fails (for testing error handling)."""
    
    def get_capabilities(self):
        return {"process_attachment": "Process an email attachment"}
    
    def process_attachment(self, file_path: str):
        """This always fails - simulates a processing error."""
        raise ValueError(f"Failed to process attachment: {file_path}")


@pytest.fixture
def email_module():
    """Create a fresh EmailProcessingModule for each test."""
    return EmailProcessingModule()


@pytest.fixture
def broken_module():
    """Create a module with broken capabilities for error testing."""
    return BrokenModule()


# =============================================================================
# TEST: __init__ method
# =============================================================================
# When you create a module, it should automatically know its own name.

class TestModuleInitialization:
    """Test that modules are initialized correctly."""
    
    @pytest.mark.unit
    def test_module_knows_its_own_class_name(self, email_module):
        """
        WHAT: When a module is created, it should store its class name.
        WHY: This is used for logging and debugging to identify which module acted.
        """
        assert email_module.module_name == "EmailProcessingModule"
    
    @pytest.mark.unit
    def test_each_module_type_has_unique_name(self):
        """
        WHAT: Different module classes should have different names.
        WHY: In logs, we need to distinguish between actions from different modules.
        """
        class SchedulingModule(BaseModule):
            """Handles calendar and scheduling tasks."""
            def get_capabilities(self):
                return {"suggest_meeting_times": "Find available meeting slots"}
        
        class CommunicationModule(BaseModule):
            """Handles email drafting and follow-ups."""
            def get_capabilities(self):
                return {"send_follow_up": "Send a follow-up email"}
        
        scheduling = SchedulingModule()
        communication = CommunicationModule()
        
        # Each knows its own name
        assert scheduling.module_name == "SchedulingModule"
        assert communication.module_name == "CommunicationModule"
        assert scheduling.module_name != communication.module_name


# =============================================================================
# TEST: get_capabilities method
# =============================================================================
# Each module should be able to describe what it can do.

class TestGetCapabilities:
    """Test that modules can describe their capabilities."""
    
    @pytest.mark.unit
    def test_capabilities_are_returned_as_dictionary(self, email_module):
        """
        WHAT: get_capabilities() should return a dict mapping names to descriptions.
        WHY: The orchestrator uses this to know what each module can do.
        """
        capabilities = email_module.get_capabilities()
        
        # Should be a dictionary
        assert isinstance(capabilities, dict)
        
        # Should have expected email-related capabilities
        assert "summarize_email" in capabilities
        assert "draft_reply" in capabilities
        assert "extract_action_items" in capabilities
    
    @pytest.mark.unit
    def test_each_capability_has_description(self, email_module):
        """
        WHAT: Each capability should have a human-readable description.
        WHY: Descriptions help developers understand what each capability does.
        """
        capabilities = email_module.get_capabilities()
        
        for capability_name, description in capabilities.items():
            assert isinstance(capability_name, str), f"Capability name should be a string"
            assert isinstance(description, str), f"Description should be a string"
            assert len(description) > 0, f"Description for '{capability_name}' should not be empty"


# =============================================================================
# TEST: validate_input method
# =============================================================================
# Modules can optionally validate their inputs before execution.

class TestInputValidation:
    """Test input validation behavior."""
    
    @pytest.mark.unit
    def test_default_validation_always_passes(self, email_module):
        """
        WHAT: By default, any input is considered valid.
        WHY: Most modules don't need special validation - they just process what they get.
        """
        assert email_module.validate_input() is True
        assert email_module.validate_input(subject="Q1 Review") is True
        assert email_module.validate_input(sender="john@example.com", body="Hi...") is True
    
    @pytest.mark.unit
    def test_modules_can_add_custom_validation(self):
        """
        WHAT: Modules can override validate_input to enforce requirements.
        WHY: Some capabilities need specific parameters (e.g., email_id for reply).
        """
        class ReplyModule(BaseModule):
            """A module that requires an email to reply to."""
            
            def get_capabilities(self):
                return {"send_reply": "Send a reply to the specified email"}
            
            def validate_input(self, **kwargs):
                # Cannot reply without knowing which email to reply to
                return "email_id" in kwargs
            
            def send_reply(self, email_id: str, reply_text: str):
                return f"Reply sent to email {email_id}"
        
        reply_module = ReplyModule()
        
        # Missing email_id = invalid
        assert reply_module.validate_input(reply_text="Thanks!") is False
        
        # Has email_id = valid
        assert reply_module.validate_input(email_id="msg_123", reply_text="Thanks!") is True


# =============================================================================
# TEST: log_execution method  
# =============================================================================
# Modules create log entries for tracking what they did.

class TestExecutionLogging:
    """Test that modules can log their executions."""
    
    @pytest.mark.unit
    def test_log_entry_contains_all_required_fields(self, email_module):
        """
        WHAT: Log entries should have standard fields for debugging.
        WHY: Consistent logging helps troubleshoot issues across all modules.
        """
        log_entry = email_module.log_execution(
            capability="summarize_email",
            input_data={"subject": "Q1 Review", "body": "Please review..."},
            result="Summary: Email about Q1 Review",
            success=True
        )
        
        required_fields = ["module", "capability", "timestamp", "input", "result", "success", "error"]
        for field in required_fields:
            assert field in log_entry, f"Log entry missing required field: {field}"
    
    @pytest.mark.unit
    def test_log_entry_includes_module_name(self, email_module):
        """
        WHAT: The log should include which module performed the action.
        WHY: When debugging, we need to know which module ran.
        """
        log_entry = email_module.log_execution(
            capability="draft_reply",
            input_data={"original_email": "Hi, can we meet?"},
            result="Thank you for your email..."
        )
        
        assert log_entry["module"] == "EmailProcessingModule"
    
    @pytest.mark.unit
    def test_log_entry_includes_capability_name(self, email_module):
        """
        WHAT: The log should include which capability was executed.
        WHY: We need to know what action was performed.
        """
        log_entry = email_module.log_execution(
            capability="extract_action_items",
            input_data={"email_body": "Please send the report by Friday"},
            result=["Send report by Friday"]
        )
        
        assert log_entry["capability"] == "extract_action_items"
    
    @pytest.mark.unit
    def test_log_entry_has_valid_timestamp(self, email_module):
        """
        WHAT: The timestamp should be in ISO format.
        WHY: ISO format is standard and easy to parse for analysis.
        """
        log_entry = email_module.log_execution(
            capability="summarize_email",
            input_data={"subject": "Test", "body": "Test body"},
            result="Summary: Test email"
        )
        
        # Should parse without error if valid ISO format
        parsed_time = datetime.fromisoformat(log_entry["timestamp"])
        assert parsed_time is not None
    
    @pytest.mark.unit
    def test_log_distinguishes_success_from_failure(self, email_module):
        """
        WHAT: Logs should clearly show if the execution succeeded or failed.
        WHY: Failure tracking is essential for monitoring assistant health.
        """
        # Log a successful email summary
        success_log = email_module.log_execution(
            capability="summarize_email",
            input_data={"subject": "Meeting", "body": "Let's meet tomorrow"},
            result="Summary: Meeting request for tomorrow",
            success=True,
            error=None
        )
        assert success_log["success"] is True
        assert success_log["error"] is None
        
        # Log a failed attachment processing
        failure_log = email_module.log_execution(
            capability="process_attachment",
            input_data={"file_path": "/invalid/path.pdf"},
            result=None,
            success=False,
            error="Failed to process attachment: file not found"
        )
        assert failure_log["success"] is False
        assert "Failed to process" in failure_log["error"]


# =============================================================================
# TEST: execute method
# =============================================================================
# The main way to run module capabilities.

class TestCapabilityExecution:
    """Test running module capabilities through execute()."""
    
    @pytest.mark.unit
    def test_execute_runs_capability_and_returns_result(self, email_module):
        """
        WHAT: execute() should run the capability and return its result.
        WHY: This is the standard interface for using any module.
        """
        result = email_module.execute(
            "summarize_email",
            subject="Q1 Strategy Review",
            body="Please review the attached Q1 strategy document..."
        )
        
        assert result["success"] is True
        assert result["error"] is None
        assert "Q1 Strategy Review" in result["data"]
    
    @pytest.mark.unit
    def test_execute_passes_all_arguments_to_capability(self, email_module):
        """
        WHAT: All keyword arguments should be forwarded to the capability.
        WHY: Capabilities need their input parameters to work correctly.
        """
        result = email_module.execute(
            "draft_reply",
            original_email="Can we schedule a call?",
            tone="friendly"
        )
        
        assert result["success"] is True
        assert "friendly" in result["data"]  # Tone should be reflected in draft
    
    @pytest.mark.unit
    def test_execute_returns_error_for_unknown_capability(self, email_module):
        """
        WHAT: Requesting a non-existent capability should fail gracefully.
        WHY: Typos or missing features shouldn't crash the assistant.
        """
        result = email_module.execute("translate_email")  # Not a real capability
        
        assert result["success"] is False
        assert result["data"] is None
        assert "not found" in result["error"]
        assert "translate_email" in result["error"]
    
    @pytest.mark.unit
    def test_execute_catches_exceptions_from_capability(self, broken_module):
        """
        WHAT: If a capability throws an error, execute() should catch it.
        WHY: We want graceful error handling, not assistant crashes.
        """
        result = broken_module.execute(
            "process_attachment",
            file_path="/path/to/corrupted.pdf"
        )
        
        assert result["success"] is False
        assert result["data"] is None
        assert "Failed to process attachment" in result["error"]
    
    @pytest.mark.unit
    def test_execute_validates_input_before_running(self):
        """
        WHAT: execute() should validate input before running the capability.
        WHY: Catch missing required parameters early with clear error messages.
        """
        class MessageSendModule(BaseModule):
            """A module that sends messages - requires recipient."""
            
            def get_capabilities(self):
                return {"send_message": "Send a message to a contact"}
            
            def validate_input(self, **kwargs):
                # Must have a recipient to send a message
                return "recipient_email" in kwargs
            
            def send_message(self, recipient_email: str, message: str):
                return f"Message sent to {recipient_email}"
        
        module = MessageSendModule()
        
        # Missing recipient: should fail validation
        result_no_recipient = module.execute("send_message", message="Hello!")
        assert result_no_recipient["success"] is False
        assert "Invalid input" in result_no_recipient["error"]
        
        # With recipient: should succeed
        result_with_recipient = module.execute(
            "send_message",
            recipient_email="colleague@company.com",
            message="Hello!"
        )
        assert result_with_recipient["success"] is True
        assert "colleague@company.com" in result_with_recipient["data"]
