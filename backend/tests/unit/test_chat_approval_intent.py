from app.chat.approval_intent import (
    ApprovalIntentKind,
    PendingActionRef,
    parse_approval_intent,
)


def _pending():
    return [
        PendingActionRef(id="a1", index=1, action_type="create_task"),
        PendingActionRef(id="a2", index=2, action_type="draft_reply"),
        PendingActionRef(id="a3", index=3, action_type="add_to_calendar"),
    ]


def test_approve_all_intent():
    intent = parse_approval_intent("proceed", _pending())
    assert intent.kind == ApprovalIntentKind.APPROVE_ALL
    assert intent.approve_ids == {"a1", "a2", "a3"}


def test_approve_all_with_note_containing_cancel_word():
    intent = parse_approval_intent("approve all. if blocked, cancel only conflicting one", _pending())
    assert intent.kind == ApprovalIntentKind.APPROVE_ALL
    assert intent.approve_ids == {"a1", "a2", "a3"}


def test_approve_subset_by_numbers():
    intent = parse_approval_intent("run 1 and 3", _pending())
    assert intent.kind == ApprovalIntentKind.APPROVE_SUBSET
    assert intent.approve_ids == {"a1", "a3"}
    assert not intent.reject_ids


def test_reject_subset():
    intent = parse_approval_intent("skip 2", _pending())
    assert intent.kind == ApprovalIntentKind.REJECT_SUBSET
    assert intent.reject_ids == {"a2"}


def test_cancel_all():
    intent = parse_approval_intent("cancel", _pending())
    assert intent.kind == ApprovalIntentKind.CANCEL_ALL
    assert intent.reject_ids == {"a1", "a2", "a3"}


def test_ambiguous_intent():
    intent = parse_approval_intent("approve now", _pending())
    assert intent.kind == ApprovalIntentKind.AMBIGUOUS
