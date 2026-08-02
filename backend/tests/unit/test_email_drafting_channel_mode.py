import os
import sys
import types
from unittest.mock import MagicMock
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

if "google.genai" not in sys.modules:
    google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
    genai_mod = types.ModuleType("google.genai")
    genai_mod.types = types.SimpleNamespace()
    sys.modules["google.genai"] = genai_mod
    setattr(google_mod, "genai", genai_mod)

from app.superpowers.email_drafting import EmailDraftingService


def test_infer_draft_format_email_when_thread_present():
    service = EmailDraftingService(db=MagicMock(), user_id="u1")

    mode = service._infer_draft_format(
        thread_ref="thr_123",
        message_ref=None,
        source_message=None,
        subject="Follow up",
        intent="send update",
        user_request="follow up with Sarah",
    )

    assert mode == "email"


def test_infer_draft_format_message_when_no_email_signal():
    service = EmailDraftingService(db=MagicMock(), user_id="u1")

    mode = service._infer_draft_format(
        thread_ref=None,
        message_ref=None,
        source_message=None,
        subject="Follow up",
        intent="check in briefly",
        user_request="write a quick follow up to Sarah about timeline",
    )

    assert mode == "message"


def test_infer_draft_format_email_when_request_looks_like_email():
    service = EmailDraftingService(db=MagicMock(), user_id="u1")

    mode = service._infer_draft_format(
        thread_ref=None,
        message_ref=None,
        source_message=None,
        subject="Update",
        intent="share update",
        user_request="Subject: Weekly update\nHi team,\nQuick update below.\nBest,",
    )

    assert mode == "email"


def test_sanitize_message_mode_strips_email_scaffolding():
    service = EmailDraftingService(db=MagicMock(), user_id="u1")

    text = (
        "Subject: Re: Budget update\n"
        "To: sarah@company.com\n\n"
        "Hi Sarah, quick note: we are on track.\n\n"
        "Best,\n"
        "Etimbuk"
    )
    cleaned = service._sanitize_draft_text(text=text, sender_name="Etimbuk", draft_format="message")

    assert "Subject:" not in cleaned
    assert "To:" not in cleaned
    assert "Best," not in cleaned
    assert "quick note" in cleaned


def test_generate_draft_body_uses_shared_llm_layer():
    service = EmailDraftingService(db=MagicMock(), user_id="u1")
    fake_llm = MagicMock()
    fake_llm.generate_text.return_value = "Hi Sarah,\n\nWe are on track.\n\nBest,\nEtimbuk"

    with patch("app.superpowers.email_drafting._get_drafting_llm", return_value=fake_llm):
        body = service._generate_draft_body(
            subject="Budget update",
            intent="share a quick update",
            recipient="sarah@example.com",
            sender_name="Etimbuk",
            context_lines=[],
            source_message=None,
            user_request=None,
            draft_format="email",
        )

    assert "We are on track." in body
    fake_llm.generate_text.assert_called_once()
