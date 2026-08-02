import re
from datetime import timedelta
from io import BytesIO
import os
from pathlib import Path
from tempfile import mkstemp
from time import perf_counter
import time
from typing import Optional

from app.infra.config import get_settings
from app.services.voice_capture_observability import log_voice_capture_metric


class VoiceTranscriptionError(Exception):
    """Raised when speech-to-text transcription fails."""


class VoiceAudioValidationError(Exception):
    """Raised when the uploaded audio does not match the product contract."""


def _normalize_transcript_text(text: Optional[str]) -> str:
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    return normalized


def _voice_temp_dir() -> Path:
    temp_dir = Path(__file__).resolve().parents[3] / "tmp" / "voice_inspection"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _cleanup_stale_voice_temp_files(*, max_age_seconds: int = 900) -> None:
    temp_dir = _voice_temp_dir()
    cutoff = time.time() - max_age_seconds
    for path in temp_dir.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except Exception:
            continue


def inspect_audio_bytes(
    *,
    audio_bytes: bytes,
    filename: str,
) -> float:
    if not audio_bytes:
        raise VoiceAudioValidationError("Audio payload is empty.")

    try:
        from hachoir.metadata import extractMetadata
        from hachoir.parser import createParser
    except Exception as exc:
        raise VoiceAudioValidationError("Audio inspection dependency is unavailable.") from exc

    suffix = Path(filename or "capture.webm").suffix or ".webm"
    temp_path = None
    try:
        _cleanup_stale_voice_temp_files()
        fd, temp_path = mkstemp(suffix=suffix, dir=str(_voice_temp_dir()))
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(audio_bytes)

        parser = createParser(temp_path)
        if parser is None:
            raise VoiceAudioValidationError("Audio file could not be read.")
        with parser:
            metadata = extractMetadata(parser)
        if metadata is None or not metadata.has("duration"):
            raise VoiceAudioValidationError("Audio duration is unavailable.")
        duration = metadata.get("duration")
        if isinstance(duration, timedelta):
            seconds = duration.total_seconds()
        else:
            seconds = float(duration)
        if seconds <= 0:
            raise VoiceAudioValidationError("Audio duration is invalid.")
        return seconds
    except VoiceAudioValidationError:
        raise
    except Exception as exc:
        raise VoiceAudioValidationError("Audio file could not be validated.") from exc
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


def transcribe_audio_bytes(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
) -> str:
    started_at = perf_counter()
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise VoiceTranscriptionError("Voice transcription is not configured.")
    if not audio_bytes:
        raise VoiceTranscriptionError("Audio payload is empty.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise VoiceTranscriptionError("Voice transcription dependency is unavailable.") from exc

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    audio_file = BytesIO(audio_bytes)
    audio_file.name = filename or "capture.webm"

    try:
        response = client.audio.transcriptions.create(
            model=settings.OPENAI_TRANSCRIPTION_MODEL,
            file=audio_file,
            response_format="json",
        )
    except Exception as exc:
        raise VoiceTranscriptionError("Voice transcription failed.") from exc

    transcript = getattr(response, "text", None)
    if transcript is None and isinstance(response, dict):
        transcript = response.get("text")

    normalized = _normalize_transcript_text(transcript)
    if not normalized:
        raise VoiceTranscriptionError("Voice transcription returned no text.")
    log_voice_capture_metric(
        user_id="unknown",
        stage="provider_transcription",
        outcome="completed",
        latency_ms=int((perf_counter() - started_at) * 1000),
        transcript_chars=len(normalized),
    )
    return normalized
