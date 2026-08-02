from unittest.mock import MagicMock

from app.services.context_capture_shortener import (
    deterministic_shorten_context_capture_text,
    shorten_context_capture_text,
)


def test_shorten_context_capture_text_returns_input_when_within_limit(monkeypatch):
    llm = MagicMock()
    monkeypatch.setattr("app.services.context_capture_shortener.LLMOrchestrator", lambda config=None: llm)

    result = shorten_context_capture_text(
        transcript="Sarah approved vendor X.",
        max_chars=2000,
        scope_type="contact",
        scope_label="Sarah",
    )

    assert result.shortened is False
    assert result.text == "Sarah approved vendor X."
    llm.generate_text.assert_not_called()


def test_shorten_context_capture_text_uses_llm_when_over_limit(monkeypatch):
    monkeypatch.setattr(
        "app.services.context_capture_shortener._load_prompt_template",
        lambda: "max={max_chars} scope={scope_type} label={scope_label} transcript={transcript_text}",
    )

    class FakeOrchestrator:
        def __init__(self, config=None):
            pass

        def generate_text(self, prompt, max_output_tokens=None, temperature=None):
            assert "scope=contact" in prompt
            return "Sarah approved vendor X for Q3 expansion."

    monkeypatch.setattr("app.services.context_capture_shortener.LLMOrchestrator", FakeOrchestrator)

    result = shorten_context_capture_text(
        transcript="x" * 2500,
        max_chars=2000,
        scope_type="contact",
        scope_label="Sarah",
    )

    assert result.shortened is True
    assert result.text == "Sarah approved vendor X for Q3 expansion."


def test_shorten_context_capture_text_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setattr(
        "app.services.context_capture_shortener._load_prompt_template",
        lambda: "transcript={transcript_text}",
    )

    class FakeOrchestrator:
        def __init__(self, config=None):
            pass

        def generate_text(self, prompt, max_output_tokens=None, temperature=None):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.context_capture_shortener.LLMOrchestrator", FakeOrchestrator)

    result = shorten_context_capture_text(
        transcript="x" * 2500,
        max_chars=2000,
        scope_type="contact",
        scope_label="Sarah",
    )

    assert result.shortened is True
    assert len(result.text) <= 2000
    assert result.text.endswith("…")


def test_deterministic_shorten_context_capture_text_clips_to_limit():
    text = deterministic_shorten_context_capture_text(
        transcript="x" * 2100,
        max_chars=2000,
    )

    assert len(text) <= 2000
    assert text.endswith("…")
