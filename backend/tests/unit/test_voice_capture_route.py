from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from datetime import datetime, timedelta, timezone

from app.data.models import Contact, ContextEntry, TaskQueue
from app.services.context_capture_shortener import ContextCaptureShortenResult
from app.routes.v1.vault import create_voice_context_capture
from app.security.auth import AuthenticatedUser
from app.services.voice_transcription import VoiceAudioValidationError


def _user():
    return AuthenticatedUser(
        user_id="user-voice-1",
        email="ea@example.com",
        email_verified=True,
        provider="google",
        app_metadata={},
        user_metadata={},
    )


def _upload(filename: str, content_type: str, payload: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_create_voice_context_capture_transcribes_and_saves(db_session, monkeypatch):
    contact = Contact(user_id="user-voice-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.commit()

    queued = {}
    monkeypatch.setattr(
        "app.jobs.queue.enqueue_task",
        lambda task_type, payload, **kwargs: queued.update({"task_type": task_type, "payload": payload}),
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.transcribe_audio_bytes",
        lambda **kwargs: "Sarah approved vendor X for Q3 expansion",
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.inspect_audio_bytes",
        lambda **kwargs: 12.0,
    )

    response = await create_voice_context_capture(
        audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
        scope_type="contact",
        scope_id="sarah@example.com",
        linked_to="Sarah",
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert stored.raw_text == "Sarah approved vendor X for Q3 expansion"
    assert stored.input_source == "voice"
    assert stored.entity_type == "contact"
    assert stored.entity_id == str(contact.id)
    assert stored.classification_status == "pending"
    assert queued["task_type"] == "classify_context_capture"
    assert queued["payload"]["entry_id"] == response.id


@pytest.mark.asyncio
async def test_create_voice_context_capture_shortens_transcript_over_limit(db_session, monkeypatch):
    contact = Contact(user_id="user-voice-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.commit()

    monkeypatch.setattr(
        "app.jobs.queue.enqueue_task",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.inspect_audio_bytes",
        lambda **kwargs: 12.0,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.transcribe_audio_bytes",
        lambda **kwargs: "x" * 2500,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.shorten_context_capture_text",
        lambda **kwargs: ContextCaptureShortenResult(
            text="Sarah approved vendor X for Q3 expansion.",
            shortened=True,
        ),
    )

    response = await create_voice_context_capture(
        audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
        scope_type="contact",
        scope_id="sarah@example.com",
        linked_to="Sarah",
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert stored.raw_text == "Sarah approved vendor X for Q3 expansion."
    assert len(stored.raw_text) <= 2000
    assert stored.classification_status == "pending"


@pytest.mark.asyncio
async def test_create_voice_context_capture_clips_very_long_transcript_without_shortener(db_session, monkeypatch):
    contact = Contact(user_id="user-voice-1", name="Sarah", email="sarah@example.com")
    db_session.add(contact)
    db_session.commit()

    monkeypatch.setattr(
        "app.jobs.queue.enqueue_task",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.inspect_audio_bytes",
        lambda **kwargs: 12.0,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.transcribe_audio_bytes",
        lambda **kwargs: "x" * 5000,
    )
    monkeypatch.setattr(
        "app.routes.v1.vault.shorten_context_capture_text",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("LLM shortener should not be called")),
    )

    response = await create_voice_context_capture(
        audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
        scope_type="contact",
        scope_id="sarah@example.com",
        linked_to="Sarah",
        user=_user(),
        db=db_session,
    )

    stored = db_session.query(ContextEntry).filter(ContextEntry.id == response.id).first()
    assert stored is not None
    assert len(stored.raw_text) <= 2000
    assert stored.classification_status == "pending"


@pytest.mark.asyncio
async def test_create_voice_context_capture_rejects_unsupported_audio_format(db_session):
    with pytest.raises(HTTPException) as exc:
        await create_voice_context_capture(
            audio=_upload("capture.txt", "text/plain", b"not-audio"),
            scope_type="global",
            scope_id=None,
            linked_to=None,
            user=_user(),
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert "Unsupported audio format" in exc.value.detail


@pytest.mark.asyncio
async def test_create_voice_context_capture_rejects_empty_audio(db_session):
    with pytest.raises(HTTPException) as exc:
        await create_voice_context_capture(
            audio=_upload("capture.webm", "audio/webm", b""),
            scope_type="global",
            scope_id=None,
            linked_to=None,
            user=_user(),
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Audio file is empty."


@pytest.mark.asyncio
async def test_create_voice_context_capture_rejects_audio_over_45_seconds(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.routes.v1.vault.inspect_audio_bytes",
        lambda **kwargs: 46.0,
    )

    with pytest.raises(HTTPException) as exc:
        await create_voice_context_capture(
            audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
            scope_type="global",
            scope_id=None,
            linked_to=None,
            user=_user(),
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Record up to 45 seconds."


@pytest.mark.asyncio
async def test_create_voice_context_capture_rejects_unreadable_audio(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.routes.v1.vault.inspect_audio_bytes",
        lambda **kwargs: (_ for _ in ()).throw(VoiceAudioValidationError("bad parse")),
    )

    with pytest.raises(HTTPException) as exc:
        await create_voice_context_capture(
            audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
            scope_type="global",
            scope_id=None,
            linked_to=None,
            user=_user(),
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Use a short supported audio recording."


@pytest.mark.asyncio
async def test_create_voice_context_capture_throttles_recent_voice_captures(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            ContextEntry(
                user_id="user-voice-1",
                type="insight",
                content=f"Voice capture {idx}",
                raw_text=f"Voice capture {idx}",
                input_source="voice",
                entity_type="global",
                entity_id=None,
                linked_to=None,
                created_by="You",
                status="active",
                classification_status="classified",
                created_at=now - timedelta(minutes=1),
                updated_at=now - timedelta(minutes=1),
            )
            for idx in range(6)
        ]
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await create_voice_context_capture(
            audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
            scope_type="global",
            scope_id=None,
            linked_to=None,
            user=_user(),
            db=db_session,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail == "Voice capture is temporarily busy. Try again in a moment."


@pytest.mark.asyncio
async def test_create_voice_context_capture_blocks_when_another_transcription_is_in_flight(db_session):
    db_session.add(
        TaskQueue(
            task_type="voice_capture_transcription",
            user_id="user-voice-1",
            payload={"kind": "voice_capture_lock"},
            status="in_progress",
            attempts=1,
            max_attempts=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await create_voice_context_capture(
            audio=_upload("capture.webm", "audio/webm", b"voice-bytes"),
            scope_type="global",
            scope_id=None,
            linked_to=None,
            user=_user(),
            db=db_session,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail == "Voice capture is temporarily busy. Try again in a moment."
