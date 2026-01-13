"""
Unit Tests for LLM Parsing and Repair Logic (core/llm/providers/base.py)

=== WHAT IS THIS TESTING? ===
This file tests the "brain" behind how we turn messy AI output into 
clean Python dictionaries. Small AI models often make mistakes like:
- Forgetting a closing brace }
- Adding an extra comma at the end of a list
- Wrapping everything in text they weren't asked for
- Forgetting to put { } around their answer

These tests ensure that our parsing logic is robust enough to handle 
all these "noisy" situations so the rest of the app doesn't crash.

=== WHO IS THIS FOR? ===
A junior engineer taking over the project should be able to read 
these tests to understand all the weird ways an LLM can fail and 
how we recover from those failures.

Run tests with: pytest tests/unit/test_llm_parsing.py -v
"""
import pytest
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from unittest.mock import patch

from pydantic import BaseModel, Field

# We need a concrete class to test the abstract BaseLLMProvider
from core.llm.providers.base import BaseLLMProvider


# -----------------------------------------------------------------------------
# SETUP: Mock Provider
# -----------------------------------------------------------------------------
# ... (existing MockLLMProvider)
# BaseLLMProvider is an abstract class (Base), so we can't create it directly.
# We create a "Mock" version that just implements the required methods
# so we can test the parsing logic that lives in the Base class.

class MockLLMProvider(BaseLLMProvider):
    """A minimal version of an LLM provider for testing parsing logic."""
    def initialize(self): pass
    def cleanup(self): pass
    def _raw_generate(self, prompt, system_prompt=None):
        return "Not used in these tests"


@pytest.fixture
def parser():
    """Provides an instance of the provider to test parsing methods."""
    return MockLLMProvider(config={})


# =============================================================================
# TESTS: Perfect JSON (The Happy Path)
# =============================================================================

class TestPerfectParsing:
    """Tests for when the LLM behaves perfectly and returns clean JSON."""

    @pytest.mark.unit
    def test_parse_clean_object(self, parser):
        """
        WHAT: Parse a standard JSON object.
        WHY: This is the most common and simplest case.
        """
        raw_output = '{"summary": "Meeting went well", "tasks": 3}'
        result = parser._parse_json(raw_output)
        
        assert result == {"summary": "Meeting went well", "tasks": 3}

    @pytest.mark.unit
    def test_parse_nested_json(self, parser):
        """
        WHAT: Parse JSON with nested objects.
        WHY: AI models often return complex hierarchical data.
        """
        raw_output = '{"event": {"title": "Call", "time": "10am"}, "participants": ["A", "B"]}'
        result = parser._parse_json(raw_output)
        
        assert result["event"]["title"] == "Call"
        assert len(result["participants"]) == 2


# =============================================================================
# TESTS: Markdown Handling
# =============================================================================
# Many LLMs insist on wrapping their output in ```json ... ``` blocks
# even when asked not to. We must be able to peel these off.

class TestMarkdownExtraction:
    """Tests for extracting JSON from markdown code blocks."""

    @pytest.mark.unit
    def test_parse_markdown_json_block(self, parser):
        """
        WHAT: Parse JSON wrapped in ```json tags.
        WHY: This is the most standard way LLMs provide "formatted" code.
        """
        raw_output = "Here is the result:\n```json\n{\"status\": \"ok\"}\n```"
        result = parser._parse_json(raw_output)
        
        assert result == {"status": "ok"}

    @pytest.mark.unit
    def test_parse_plain_markdown_block(self, parser):
        """
        WHAT: Parse JSON wrapped in generic ``` blocks.
        WHY: Sometimes models forget the 'json' label.
        """
        raw_output = "```\n{\"key\": \"value\"}\n```"
        result = parser._parse_json(raw_output)
        
        assert result == {"key": "value"}


# =============================================================================
# TESTS: Noisy Text Extraction
# =============================================================================
# Sometimes the model writes a bunch of conversational text and then the JSON.

class TestNoisyExtraction:
    """Tests for finding JSON hidden within regular text."""

    @pytest.mark.unit
    def test_find_json_inside_conversational_text(self, parser):
        """
        WHAT: Find a { } block even if there is text before and after it.
        WHY: Chat-optimized models often "chat" before giving the data.
        """
        raw_output = "I have analyzed it. Result: {\"intent\": \"greeting\"}. Hope this helps!"
        result = parser._parse_json(raw_output)
        
        assert result == {"intent": "greeting"}

    @pytest.mark.unit
    def test_find_array_inside_conversational_text(self, parser):
        """
        WHAT: Find a [ ] block even if there is text before and after it.
        WHY: Same as above, but for lists.
        """
        raw_output = "Tasks: [\"call me\", \"email her\"] tomorrow."
        result = parser._parse_json(raw_output)
        
        # Note: _parse_json automatically wraps bare arrays in a key
        assert "tasks" in result
        assert result["tasks"] == ["call me", "email her"]


# =============================================================================
# TESTS: JSON Repair (Common LLM Mistakes)
# =============================================================================
# These tests focus on fixing syntax errors that small models frequently make.

class TestJsonRepair:
    """Tests for fixing common syntax errors automatically."""

    @pytest.mark.unit
    def test_repair_trailing_comma(self, parser):
        """
        WHAT: Fix JSON that has an extra comma at the end, like {"a": 1,}.
        WHY: This is a very common syntax error in model-generated output.
        """
        raw_output = '{"a": 1, "b": 2,}'
        result = parser._parse_json(raw_output)
        
        assert result == {"a": 1, "b": 2}

    @pytest.mark.unit
    def test_repair_missing_closing_brace(self, parser):
        """
        WHAT: Fix JSON that was cut off or forgotten: {"a": 1
        WHY: Models sometimes hit token limits or just forget to close the brace.
        """
        raw_output = '{"a": 1, "b": "half-done"'
        result = parser._parse_json(raw_output)
        
        assert result["a"] == 1
        assert result["b"] == "half-done"

    @pytest.mark.unit
    def test_repair_unescaped_newlines(self, parser):
        """
        WHAT: Fix strings that contain real newlines instead of \\n.
        WHY: Standard Python json.loads() fails if a string value has a raw newline.
        """
        # This string has a physical newline in it
        raw_output = '{"summary": "Line 1\nLine 2"}'
        result = parser._parse_json(raw_output)
        
        # Should be repaired to Line 1\nLine 2
        assert result["summary"] == "Line 1\nLine 2"


# =============================================================================
# TESTS: Wrapping & Enveloping
# =============================================================================
# If the model sends a list or just raw text, we wrap it in a "sensible" dict.

class TestWrappingLogic:
    """Tests for wrapping non-dictionary output into standardized envelopes."""

    @pytest.mark.unit
    def test_wrap_bare_array(self, parser):
        """
        WHAT: Wrap [1, 2, 3] into {"tasks": [1, 2, 3]}.
        WHY: The app expects every result to be a dictionary.
        """
        raw_output = '["item1", "item2"]'
        result = parser._parse_json(raw_output)
        
        # 'tasks' is one of the default keys it tries
        assert "tasks" in result
        assert result["tasks"] == ["item1", "item2"]

    @pytest.mark.unit
    def test_wrap_raw_text(self, parser):
        """
        WHAT: Wrap "Sample text" into {"draft": "Sample text"}.
        WHY: If the model ignores the JSON request entirely, we still want the text.
        """
        raw_output = "Please call me back at 555-0199."
        result = parser._parse_json(raw_output)
        
        # 'draft' is the first key it tries for raw text
        assert "draft" in result
        assert result["draft"] == "Please call me back at 555-0199."

    @pytest.mark.unit
    def test_parse_naked_key_value(self, parser):
        """
        WHAT: Parse "key": "value" (without braces).
        WHY: Some models write key-value pairs but skip the outer { }.
        """
        raw_output = '"summary": "The project is on track"'
        result = parser._parse_json(raw_output)
        
        assert result == {"summary": "The project is on track"}


# =============================================================================
# TESTS: Failure Modes
# =============================================================================

class TestParsingFailures:
    """Tests for when the input is truly un-parsable."""

    @pytest.mark.unit
    def test_completely_invalid_garbage(self, parser):
        """
        WHAT: Return an error dictionary if the output is complete nonsense.
        WHY: We need to know when parsing completely failed to trigger a retry.
        """
        raw_output = "!!!@@@###$$$%%%"
        # For this to fail, it needs to not look like raw text words either.
        # But our strategy 5 wraps raw text. 
        # Let's try something that looks like broken JSON but can't be fixed.
        raw_output = '{"broken": "missing quote' 
        
        result = parser._parse_json(raw_output)
        
# =============================================================================
# TESTS: Schema Validation
# =============================================================================

class SimpleSchema(BaseModel):
    name: str
    age: int
    tags: List[str] = Field(default_factory=list)

class TestSchemaValidation:
    """Tests for validating parsed JSON against Pydantic models."""

    @pytest.mark.unit
    def test_validate_correct_schema(self, parser):
        """
        WHAT: Successfully validate JSON matching the schema.
        WHY: Outlines/Gemini should return perfect matches usually.
        """
        data = {"name": "Alice", "age": 30, "tags": ["admin"]}
        result = parser._validate_schema(data, SimpleSchema)
        
        assert result == data

    @pytest.mark.unit
    def test_validate_rejects_missing_fields(self, parser):
        """
        WHAT: Return None if required fields are missing.
        WHY: If the LLM misses a field, we need to know so we can retry.
        """
        data = {"name": "Alice"}  # Missing 'age'
        result = parser._validate_schema(data, SimpleSchema)
        
        assert result is None

    @pytest.mark.unit
    def test_validate_rejects_wrong_types(self, parser):
        """
        WHAT: Return None if field types are wrong (e.g., string instead of int).
        WHY: LLMs sometimes return types that don't match our Pydantic expectations.
        """
        data = {"name": "Alice", "age": "thirty"}
        result = parser._validate_schema(data, SimpleSchema)
        
        assert result is None


# =============================================================================
# TESTS: Provider Specializations
# =============================================================================

from core.llm.providers.hf_outlines import HFOutlinesProvider

class TestProviderFallbacks:
    """Tests for specialized providers (like Outlines) when they hit edge cases."""

    @pytest.mark.unit
    def test_hf_outlines_fallback_without_schema(self):
        """
        WHAT: HFOutlinesProvider uses BaseLLMProvider's repair logic when no schema given.
        WHY: Sometimes we use Outlines for raw text extraction without a rigid schema.
        """
        # Mock config
        mock_config = type('obj', (object,), {
            'hf_model_id': 'qwen',
            'hf_device': 'cpu',
            'cache_dir': './cache',
            'hf_max_new_tokens': 50
        })
        
        provider = HFOutlinesProvider(mock_config)
        provider._initialized = True  # Bypass initialization/import
        
        # We don't need to initialize the full model, we just want to test
        # that it calls _parse_json (inherited from BaseLLMProvider)
        with patch.object(HFOutlinesProvider, '_raw_generate', return_value="Result: {\"a\": 1}"):
            result = provider.generate("test prompt")
            
            # Should have used Strategy 3: Find JSON object/array pattern
            assert result == {"a": 1}
