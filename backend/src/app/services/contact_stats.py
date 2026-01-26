"""
Contact statistics service.

Updates ContactContext metadata when user interactions occur.
Used for relationship-based email filtering (Layer 3).
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


def update_reply_rate(
    db: Session,
    user_id: str,
    contact_email: str,
) -> Optional[float]:
    """
    Update reply_rate for a contact based on thread history.

    Called when:
    - User sends a reply to a thread
    - Periodic stats recalculation

    Returns:
        Updated reply_rate (0.0 - 1.0), or None if no data
    """
    from app.data.models import ContactContext, ThreadState

    contact_email = contact_email.lower()

    # Calculate reply rate from threads involving this contact
    # Optimized: single query with aggregation
    stats = db.query(
        func.count(ThreadState.id).label("total"),
        func.count(ThreadState.last_outbound_at).label("replied"),
    ).filter(
        ThreadState.user_id == user_id,
        func.lower(func.cast(ThreadState.participants, db.bind.dialect.name == 'postgresql' and 'TEXT' or 'VARCHAR')).contains(contact_email),
    ).first()

    if not stats or stats.total == 0:
        return None

    reply_rate = stats.replied / stats.total

    # Update or create ContactContext
    contact = db.query(ContactContext).filter(
        ContactContext.user_id == user_id,
        ContactContext.contact_email == contact_email,
    ).first()

    if contact:
        metadata = contact.contact_metadata or {}
        metadata["reply_rate"] = round(reply_rate, 3)
        metadata["reply_rate_updated_at"] = datetime.now(timezone.utc).isoformat()
        contact.contact_metadata = metadata
        contact.updated_at = datetime.now(timezone.utc)
    else:
        # Create new contact context
        contact = ContactContext(
            user_id=user_id,
            contact_email=contact_email,
            contact_metadata={
                "message_count": stats.total,
                "reply_rate": round(reply_rate, 3),
                "reply_rate_updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        db.add(contact)

    db.commit()

    logger.debug(
        f"Updated reply_rate for {contact_email}: {reply_rate:.2%}",
        extra={"user_id": user_id, "contact_email": contact_email, "reply_rate": reply_rate}
    )

    return reply_rate


def update_contact_on_reply(
    db: Session,
    user_id: str,
    thread_id: str,
) -> None:
    """
    Update contact stats when user replies to a thread.

    Called from sync_sent_messages when a reply is detected.
    Updates reply_rate for all participants in the thread.
    """
    from app.data.models import ThreadState

    thread = db.query(ThreadState).filter(
        ThreadState.thread_id == thread_id,
        ThreadState.user_id == user_id,
    ).first()

    if not thread:
        return

    participants = thread.participants or []

    for participant in participants:
        email = participant.get("email", "").lower()
        if email:
            try:
                update_reply_rate(db, user_id, email)
            except Exception as e:
                logger.warning(f"Failed to update reply_rate for {email}: {e}")


def increment_message_count(
    db: Session,
    user_id: str,
    contact_email: str,
) -> None:
    """
    Increment message count for a contact.

    Called when a new message is received from this contact.
    """
    from app.data.models import ContactContext

    contact_email = contact_email.lower()

    contact = db.query(ContactContext).filter(
        ContactContext.user_id == user_id,
        ContactContext.contact_email == contact_email,
    ).first()

    if contact:
        metadata = contact.contact_metadata or {}
        metadata["message_count"] = metadata.get("message_count", 0) + 1
        metadata["last_interaction_at"] = datetime.now(timezone.utc).isoformat()
        contact.contact_metadata = metadata
        contact.updated_at = datetime.now(timezone.utc)
    else:
        contact = ContactContext(
            user_id=user_id,
            contact_email=contact_email,
            contact_metadata={
                "message_count": 1,
                "last_interaction_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        db.add(contact)

    db.commit()
