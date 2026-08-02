from app.services.context_memory_policy import ages_as_stale_in_diary, is_expiry_retrievable


def test_decision_history_does_not_age_to_stale_in_diary():
    assert ages_as_stale_in_diary(entry_type="decision") is False
    assert ages_as_stale_in_diary(entry_type="decisions") is False


def test_non_decision_memory_can_still_age_to_stale_in_diary():
    assert ages_as_stale_in_diary(entry_type="preference") is True
    assert ages_as_stale_in_diary(entry_type="commitment") is True


def test_expired_decision_history_remains_retrievable_but_expired_commitment_does_not():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(days=10)

    assert is_expiry_retrievable(entry_type="decision", expires_at=expired_at, now=now) is True
    assert is_expiry_retrievable(entry_type="commitment", expires_at=expired_at, now=now) is False
