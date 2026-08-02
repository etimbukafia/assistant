from app.services.context_memory_policy import is_retrieval_confident


def test_retrieval_confident_allows_missing_confidence():
    assert is_retrieval_confident(classification_confidence=None, user_corrected=False) is True


def test_retrieval_confident_blocks_low_confidence_when_not_corrected():
    assert is_retrieval_confident(classification_confidence=0.4, user_corrected=False) is False


def test_retrieval_confident_allows_low_confidence_when_user_corrected():
    assert is_retrieval_confident(classification_confidence=0.2, user_corrected=True) is True
