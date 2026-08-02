from app.data.models import ContextEntry
from app.services.context_capture_classifier import classify_context_capture


def test_context_capture_classifier_parses_high_confidence_result(monkeypatch):
    entry = ContextEntry(
        id=1,
        user_id="user-1",
        raw_text="Sarah approved vendor X for Q3 expansion.",
        content="Sarah approved vendor X for Q3 expansion.",
        entity_type="contact",
        linked_to="Sarah",
    )

    class _FakeLLM:
        def generate(self, prompt):
            assert "Sarah approved vendor X" in prompt
            return {
                "category": "decision",
                "confidence": 0.91,
                "rationale": "Clear approval language.",
            }

    monkeypatch.setattr(
        "app.services.context_capture_classifier.LLMOrchestrator",
        lambda config=None: _FakeLLM(),
    )

    result = classify_context_capture(entry)

    assert result.category == "decision"
    assert result.confidence == 0.91
    assert result.uncertain is False


def test_context_capture_classifier_falls_back_to_insight_on_invalid_response(monkeypatch):
    entry = ContextEntry(
        id=2,
        user_id="user-1",
        raw_text="Keep an eye on procurement timing.",
        content="Keep an eye on procurement timing.",
        entity_type="global",
    )

    class _FakeLLM:
        def generate(self, prompt):
            return {"_error": True, "_raw": "bad"}

    monkeypatch.setattr(
        "app.services.context_capture_classifier.LLMOrchestrator",
        lambda config=None: _FakeLLM(),
    )

    result = classify_context_capture(entry)

    assert result.category == "insight"
    assert result.confidence == 0.0
    assert result.uncertain is True
