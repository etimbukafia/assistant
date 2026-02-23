from app.chat.service import ChatService
from app.data.models import ContactContext, Message, VaultNote


def test_resolve_mentions_prefers_message_id_prefix(db_session):
    user_id = "user-mentions-1"
    message = Message(
        message_id="gmail-1",
        thread_id="thread-1",
        user_id=user_id,
        subject="Q1 strategic review",
        sender="alex@example.com",
        recipient="me@example.com",
        body="body",
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    service = ChatService(db_session, user_id=user_id)
    resolved = service._resolve_mentions(
        [
            {
                "type": "email",
                "ref_id": f"msg:{message.id}",
                "label": "@email/Q1 strategic review (alex@example.com)",
            }
        ]
    )
    assert len(resolved["emails"]) == 1
    assert resolved["emails"][0]["message_id"] == message.id
    assert resolved["emails"][0]["subject"] == "Q1 strategic review"


def test_resolve_mentions_sanitizes_text_fields(db_session):
    user_id = "user-mentions-2"
    db_session.add(
        ContactContext(
            user_id=user_id,
            contact_email="kim@example.com",
            contact_name="Kim",
            promoted=True,
        )
    )
    db_session.add(
        Message(
            message_id="gmail-2",
            thread_id="thread-2",
            user_id=user_id,
            subject="Roadmap\nDraft",
            sender="alex@example.com\nbad",
            recipient="me@example.com",
            body="body",
        )
    )
    db_session.add(
        VaultNote(
            user_id=user_id,
            slug="q1-plan",
            note_type="project",
            title="Q1\nPlan",
            body="",
            status="active",
        )
    )
    db_session.commit()

    service = ChatService(db_session, user_id=user_id)
    resolved = service._resolve_mentions(
        [
            {"type": "contact", "ref_id": "kim@example.com", "label": "Kim\nEA"},
            {"type": "email", "ref_id": "Roadmap Draft", "label": "@email/Roadmap Draft"},
            {"type": "knowledge", "ref_id": "q1-plan", "label": "@knowledge/q1-plan"},
        ]
    )

    assert resolved["contacts"][0]["label"] == "Kim EA"
    assert "\n" not in resolved["emails"][0]["subject"]
    assert "\n" not in resolved["emails"][0]["sender"]
    assert "\n" not in resolved["knowledge"][0]["title"]
