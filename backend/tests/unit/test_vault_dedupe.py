from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.data.models import Base, VaultProposal
from app.services.vault import VaultService


def _build_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session_local(), engine


def test_propose_returns_existing_for_same_dedupe_payload():
    db, engine = _build_session()
    try:
        service = VaultService(db, "user-123")
        proposal_a = service.propose(
            proposal_type="create_note",
            proposed_data={
                "note_type": "decision",
                "title": "Roadmap approved",
                "body": "Team agreed on milestones for Q2.",
            },
            diff_summary="Add decision",
            source_type="email_processing",
            source_id="thread-abc",
            confidence=0.8,
        )
        proposal_b = service.propose(
            proposal_type="create_note",
            proposed_data={
                "note_type": "decision",
                "title": "Roadmap approved",
                "body": "Team agreed on milestones for Q2.",
            },
            diff_summary="Add decision (duplicate attempt)",
            source_type="email_processing",
            source_id="thread-abc",
            confidence=0.8,
        )

        assert proposal_a.id == proposal_b.id
        assert proposal_a.dedupe_key == proposal_b.dedupe_key

        count = db.query(VaultProposal).filter(VaultProposal.user_id == "user-123").count()
        assert count == 1
    finally:
        db.close()
        engine.dispose()
