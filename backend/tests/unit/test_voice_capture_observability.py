import logging

from app.services.voice_capture_observability import log_voice_capture_metric


def test_log_voice_capture_metric_emits_structured_log(caplog):
    with caplog.at_level(logging.INFO, logger="app.services.voice_capture_observability"):
        log_voice_capture_metric(
            user_id="user-voice-1",
            stage="transcription",
            outcome="completed",
            scope_type="contact",
            latency_ms=123,
            duration_seconds=12.4,
            transcript_chars=420,
            final_chars=180,
            shortened=True,
            reason="llm_shortener",
        )

    assert "voice_capture_metric" in caplog.text
    assert "stage=transcription" in caplog.text
    assert "outcome=completed" in caplog.text
    assert "scope_type=contact" in caplog.text
    assert "shortened=True" in caplog.text
