"""
Unit tests for BaseModule (backend/src/app/agents/modules/base.py)

Tests focus on:
- execute() routing and error handling logic
- _load_prompt() caching and file handling
- log_execution() output format
"""
import pytest
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime, timezone
from freezegun import freeze_time

from app.agents.modules.base import BaseModule


# -----------------------------------------------------------------------------
# Test Fixtures & Concrete Implementation
# -----------------------------------------------------------------------------

class ConcreteModule(BaseModule):
    """Concrete implementation for testing the abstract BaseModule."""
    
    def get_capabilities(self):
        return {
            "do_something": "Performs a test action",
            "raise_error": "Raises an exception for testing"
        }
    
    def do_something(self, value: str = "default"):
        return {"processed": value}
    
    def raise_error(self):
        raise ValueError("Intentional test error")


@pytest.fixture
def module(mocker):
    """Create a ConcreteModule with mocked LLMOrchestrator."""
    mocker.patch("core.llm.LLMOrchestrator")
    return ConcreteModule(prompts_dir="test_prompts")


# -----------------------------------------------------------------------------
# Tests: execute() - Routing & Error Handling
# -----------------------------------------------------------------------------

class TestExecuteMethod:
    """Tests for the execute() capability routing method."""

    def test_execute_with_valid_capability_returns_success(self, module):
        # Arrange
        capability = "do_something"
        kwargs = {"value": "test_input"}
        
        # Act
        result = module.execute(capability, **kwargs)
        
        # Assert
        assert result["success"] is True
        assert result["data"] == {"processed": "test_input"}
        assert result["error"] is None

    def test_execute_with_nonexistent_capability_returns_error(self, module):
        # Arrange
        capability = "nonexistent_method"
        
        # Act
        result = module.execute(capability)
        
        # Assert
        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["data"] is None

    def test_execute_with_capability_exception_returns_error(self, module):
        # Arrange
        capability = "raise_error"
        
        # Act
        result = module.execute(capability)
        
        # Assert
        assert result["success"] is False
        assert "Intentional test error" in result["error"]
        assert result["data"] is None

    def test_execute_with_invalid_input_returns_error(self, module):
        # Arrange
        module.validate_input = MagicMock(return_value=False)
        
        # Act
        result = module.execute("do_something", value="bad")
        
        # Assert
        assert result["success"] is False
        assert "Invalid input" in result["error"]
        assert result["data"] is None


# -----------------------------------------------------------------------------
# Tests: _load_prompt() - File Loading & Caching
# -----------------------------------------------------------------------------

class TestLoadPrompt:
    """Tests for the _load_prompt() file loading method."""

    def test_load_prompt_reads_file_content(self, module):
        # Arrange
        prompt_content = "You are a helpful assistant."
        
        # Act
        with patch("builtins.open", mock_open(read_data=prompt_content)):
            result = module._load_prompt("system")
        
        # Assert
        assert result == prompt_content

    def test_load_prompt_caches_result_on_second_call(self, module):
        # Arrange
        prompt_content = "Cached prompt content"
        m = mock_open(read_data=prompt_content)
        
        # Act
        with patch("builtins.open", m):
            first_call = module._load_prompt("cached_prompt")
            second_call = module._load_prompt("cached_prompt")
        
        # Assert
        assert first_call == second_call
        m.assert_called_once()  # File should only be read once

    def test_load_prompt_raises_on_missing_file(self, module):
        # Arrange
        with patch("builtins.open", side_effect=FileNotFoundError()):
            # Act & Assert
            with pytest.raises(FileNotFoundError) as exc_info:
                module._load_prompt("nonexistent")
            
            assert "Prompt file not found" in str(exc_info.value)


# -----------------------------------------------------------------------------
# Tests: log_execution() - Logging Output Format
# -----------------------------------------------------------------------------

class TestLogExecution:
    """Tests for the log_execution() logging method."""

    @freeze_time("2026-01-14 12:00:00", tz_offset=0)
    def test_log_execution_returns_correct_format(self, module):
        # Arrange
        capability = "do_something"
        input_data = {"value": "test"}
        result_data = {"processed": "test"}
        
        # Act
        log_entry = module.log_execution(
            capability=capability,
            input_data=input_data,
            result=result_data,
            success=True
        )
        
        # Assert
        assert log_entry["module"] == "ConcreteModule"
        assert log_entry["capability"] == capability
        assert log_entry["timestamp"] == "2026-01-14T12:00:00+00:00"
        assert log_entry["input"] == input_data
        assert log_entry["result"] == result_data
        assert log_entry["success"] is True
        assert log_entry["error"] is None

    def test_log_execution_captures_error_message(self, module):
        # Arrange
        error_msg = "Something went wrong"
        
        # Act
        log_entry = module.log_execution(
            capability="failed_op",
            input_data={},
            result=None,
            success=False,
            error=error_msg
        )
        
        # Assert
        assert log_entry["success"] is False
        assert log_entry["error"] == error_msg


# -----------------------------------------------------------------------------
# Tests: validate_input() - Default Behavior
# -----------------------------------------------------------------------------

class TestValidateInput:
    """Tests for the validate_input() method."""

    def test_validate_input_returns_true_by_default(self, module):
        # Act
        result = module.validate_input(any_param="any_value")
        
        # Assert
        assert result is True
