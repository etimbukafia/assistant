"""
Email classifier using sentence embeddings for Layer 2 filtering.

Uses the SentenceTransformerProvider for zero-shot classification
of emails as important (process) or ignorable (metadata-only).
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailClassificationResult:
    """Result of email classification"""
    should_process: bool
    confidence: float
    reason: str


# Anchor descriptions for zero-shot classification
# Emails are compared semantically to these descriptions

IMPORTANT_ANCHORS = [
    "important business email requiring response or action",
    "personal message from colleague or client needing attention",
    "urgent request with deadline or time-sensitive matter",
    "meeting request or calendar invitation requiring response",
    "project update or status report needing review",
    "question or inquiry requiring my input or decision",
    "invoice, contract, or document requiring review",
    "job application or professional opportunity",
]

IGNORABLE_ANCHORS = [
    "promotional marketing email with sales and discounts",
    "automated newsletter or digest subscription",
    "bulk notification from service or platform",
    "social media notification or alert",
    "automated system notification no action needed",
    "spam or unsolicited commercial email",
    "mailing list broadcast message",
    "promotional offer or advertisement",
]

LABEL_ANCHORS = {
    "important": IMPORTANT_ANCHORS,
    "ignorable": IGNORABLE_ANCHORS,
}


def classify_email(
    subject: str,
    sender: str,
    body_preview: Optional[str] = None,
    threshold: float = 0.1,
    min_confidence: float = 0.15,
) -> EmailClassificationResult:
    """
    Classify an email as important (should process) or ignorable (metadata only).

    Args:
        subject: Email subject line
        sender: Sender email/name
        body_preview: Optional first ~200 chars of body for better accuracy
        threshold: Minimum score difference for classification decision.
        min_confidence: Minimum confidence to filter as ignorable.
                        If confidence < min_confidence, defaults to process (conservative).
                        This prevents filtering emails when the model is uncertain.

    Returns:
        EmailClassificationResult with should_process, confidence, and reason
    """
    try:
        from core.llm.providers import get_sentence_transformer
    except ImportError:
        logger.warning("sentence-transformers not available, skipping Layer 2")
        return EmailClassificationResult(
            should_process=True,
            confidence=0.0,
            reason="AI classifier unavailable, defaulting to process"
        )

    provider = get_sentence_transformer()

    if not provider.is_available():
        return EmailClassificationResult(
            should_process=True,
            confidence=0.0,
            reason="sentence-transformers not installed, defaulting to process"
        )

    # Construct text representation of email
    email_text = f"Subject: {subject}\nFrom: {sender}"
    if body_preview:
        preview = body_preview[:200].strip()
        if preview:
            email_text += f"\n{preview}"

    try:
        result = provider.classify(
            text=email_text,
            label_anchors=LABEL_ANCHORS,
            threshold=threshold,
            default_label="important",  # Conservative: process if ambiguous
        )

        important_score = result.scores.get("important", 0)
        ignorable_score = result.scores.get("ignorable", 0)

        # Conservative filtering: only mark as ignorable if confidence is high enough
        if result.label == "ignorable" and result.confidence >= min_confidence:
            return EmailClassificationResult(
                should_process=False,
                confidence=result.confidence,
                reason=f"Classified as ignorable ({ignorable_score:.2f} vs {important_score:.2f})",
            )

        # Default to process: either classified as important, or low confidence
        if result.label == "ignorable" and result.confidence < min_confidence:
            # Log borderline case for tuning (invisible to users, valuable for learning)
            logger.info(
                "Borderline classification",
                extra={
                    "borderline": True,
                    "label": "ignorable",
                    "confidence": round(result.confidence, 3),
                    "min_confidence": min_confidence,
                    "final_action": "process",
                    "important_score": round(important_score, 3),
                    "ignorable_score": round(ignorable_score, 3),
                    "subject_preview": subject[:50] if subject else None,
                }
            )
            reason = f"Low confidence ({result.confidence:.2f} < {min_confidence}), defaulting to process"
        elif result.confidence < threshold:
            reason = f"Ambiguous ({important_score:.2f} vs {ignorable_score:.2f}), defaulting to process"
        else:
            reason = f"Classified as important ({important_score:.2f} vs {ignorable_score:.2f})"

        return EmailClassificationResult(
            should_process=True,
            confidence=result.confidence,
            reason=reason,
        )

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return EmailClassificationResult(
            should_process=True,
            confidence=0.0,
            reason=f"Classification error: {str(e)}, defaulting to process"
        )


def is_classifier_available() -> bool:
    """Check if the email classifier is available"""
    try:
        from core.llm.providers import get_sentence_transformer
        provider = get_sentence_transformer()
        return provider.is_available()
    except ImportError:
        return False


def preload_classifier() -> bool:
    """
    Preload the classifier model at startup.
    Call during application initialization to avoid first-request latency.

    Returns:
        True if model loaded successfully, False otherwise
    """
    try:
        from core.llm.providers import get_sentence_transformer
        provider = get_sentence_transformer()
        provider.ensure_initialized()
        return True
    except Exception as e:
        logger.warning(f"Failed to preload classifier: {e}")
        return False
