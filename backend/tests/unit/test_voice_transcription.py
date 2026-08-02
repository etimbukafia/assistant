from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.infra.config import get_settings
from app.services.voice_transcription import (
    VoiceAudioValidationError,
    VoiceTranscriptionError,
    inspect_audio_bytes,
    transcribe_audio_bytes,
)


class _FakeParser:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeMetadata:
    def __init__(self, duration):
        self._duration = duration

    def has(self, key: str) -> bool:
        return key == "duration"

    def get(self, key: str):
        if key != "duration":
            raise KeyError(key)
        return self._duration


def test_inspect_audio_bytes_returns_duration_seconds():
    fake_modules = {
        "hachoir.metadata": SimpleNamespace(extractMetadata=lambda parser: _FakeMetadata(timedelta(seconds=12))),
        "hachoir.parser": SimpleNamespace(createParser=lambda path: _FakeParser()),
    }

    with patch.dict("sys.modules", fake_modules):
        duration = inspect_audio_bytes(
            audio_bytes=b"audio-bytes",
            filename="capture.webm",
        )

    assert duration == 12.0


def test_inspect_audio_bytes_rejects_missing_duration():
    fake_modules = {
        "hachoir.metadata": SimpleNamespace(extractMetadata=lambda parser: None),
        "hachoir.parser": SimpleNamespace(createParser=lambda path: _FakeParser()),
    }

    with patch.dict("sys.modules", fake_modules):
        with pytest.raises(VoiceAudioValidationError):
            inspect_audio_bytes(
                audio_bytes=b"audio-bytes",
                filename="capture.webm",
            )


def test_transcribe_audio_bytes_normalizes_transcript(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class FakeClient:
        def __init__(self, api_key: str):
            assert api_key == "test-openai-key"
            self.audio = SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(text="  Hello\n\nworld   ")
                )
            )

    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=FakeClient)}):
        transcript = transcribe_audio_bytes(
            audio_bytes=b"audio-bytes",
            filename="capture.webm",
        )

    assert transcript == "Hello world"


def test_transcribe_audio_bytes_raises_when_response_has_no_text(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class FakeClient:
        def __init__(self, api_key: str):
            self.audio = SimpleNamespace(
                transcriptions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(text="   ")
                )
            )

    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=FakeClient)}):
        with pytest.raises(VoiceTranscriptionError):
            transcribe_audio_bytes(
                audio_bytes=b"audio-bytes",
                filename="capture.webm",
            )
