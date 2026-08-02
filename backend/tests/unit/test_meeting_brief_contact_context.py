from datetime import datetime, timedelta, timezone

from app.data.models import CalendarEvent, Contact, ContextEntry
from app.superpowers.meeting_brief import MeetingBriefService


def test_meeting_brief_includes_participant_contact_briefs(db_session):
    user_id = "user-meeting-contact-1"
    contact = Contact(
        user_id=user_id,
        name="Priya Shah",
        email="priya@example.com",
        role="Board Member",
        organization="Acme",
    )
    db_session.add(contact)
    db_session.flush()
    event = CalendarEvent(
        user_id=user_id,
        id=101,
        title="Board prep sync",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        participants=[{"email": "priya@example.com", "name": "Priya Shah"}],
        status="upcoming",
        external_event_id="evt-board-1",
    )
    db_session.add(event)
    db_session.add_all(
        [
            ContextEntry(
                user_id=user_id,
                type="decision",
                entity_type="event",
                entity_id="evt-board-1",
                content="Cover the investor update first.",
                importance_level="high",
                status="active",
            ),
            ContextEntry(
                user_id=user_id,
                type="relationships",
                entity_type="contact",
                entity_id="priya@example.com",
                content="Priya expects board-ready summaries and explicit asks.",
                importance_level="high",
                status="active",
            ),
            ContextEntry(
                user_id=user_id,
                type="commitment",
                entity_type="contact",
                entity_id="priya@example.com",
                content="Send Priya the pre-read by Thursday.",
                importance_level="normal",
                status="active",
            ),
        ]
    )
    db_session.commit()

    service = MeetingBriefService(db_session, user_id=user_id)
    brief = service.build_brief(event_id="101")

    assert brief["meeting_subject"] == "Board prep sync"
    assert brief["participant_briefs"]
    participant_brief = brief["participant_briefs"][0]
    assert participant_brief["contact"]["name"] == "Priya Shah"
    assert participant_brief["relationship_summary"]
    assert participant_brief["preferred_tone"] is None
    assert "open_commitments" not in participant_brief
    assert "manual_notes" not in participant_brief


def test_meeting_brief_does_not_expand_participants_from_request(db_session):
    user_id = "user-meeting-contact-2"
    invited = Contact(
        user_id=user_id,
        name="Priya Shah",
        email="priya@example.com",
        role="Board Member",
        organization="Acme",
    )
    unrelated = Contact(
        user_id=user_id,
        name="Unrelated Contact",
        email="outside@example.com",
        role="Investor",
        organization="OtherCo",
    )
    db_session.add_all([invited, unrelated])
    db_session.flush()
    event = CalendarEvent(
        user_id=user_id,
        id=102,
        title="Board prep sync",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        participants=[{"email": "priya@example.com", "name": "Priya Shah"}],
        status="upcoming",
        external_event_id="evt-board-2",
    )
    db_session.add(event)
    db_session.commit()

    service = MeetingBriefService(db_session, user_id=user_id)
    brief = service.build_brief(event_id="102", participant_ids=["outside@example.com"])

    assert brief["participants"] == []
    assert brief["participant_briefs"] == []
