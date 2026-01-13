"""
Data migration utilities for the data lifecycle system.

This module provides one-time migration scripts for:
- Encrypting existing message bodies
- Future data transformations

Usage:
    python -m app.data_migration encrypt_bodies
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def migrate_encrypt_all_bodies(batch_size: int = 100) -> dict:
    """
    One-time migration to encrypt all existing unencrypted message bodies.

    Processes messages in batches to avoid memory issues with large datasets.

    Args:
        batch_size: Number of messages to process per batch

    Returns:
        dict with migration statistics
    """
    from .database import SessionLocal
    from .models import Message
    from .encryption import encrypt_body

    db = SessionLocal()
    stats = {
        "total_processed": 0,
        "already_encrypted": 0,
        "newly_encrypted": 0,
        "empty_bodies": 0,
        "errors": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None
    }

    try:
        # Count total unencrypted messages
        total_unencrypted = db.query(Message).filter(
            Message.body_encrypted == False,
            Message.body.isnot(None),
            Message.body != ""
        ).count()

        logger.info(f"Starting encryption migration for {total_unencrypted} messages")

        offset = 0
        while True:
            # Fetch batch of unencrypted messages
            messages = db.query(Message).filter(
                Message.body_encrypted == False
            ).offset(offset).limit(batch_size).all()

            if not messages:
                break

            batch_encrypted = 0
            for msg in messages:
                stats["total_processed"] += 1

                # Skip if already encrypted
                if msg.body_encrypted:
                    stats["already_encrypted"] += 1
                    continue

                # Skip empty bodies
                if not msg.body or msg.body.strip() == "":
                    stats["empty_bodies"] += 1
                    continue

                try:
                    # Encrypt the body
                    msg.body = encrypt_body(msg.body)
                    msg.body_encrypted = True
                    batch_encrypted += 1
                    stats["newly_encrypted"] += 1
                except Exception as e:
                    logger.error(f"Failed to encrypt message {msg.id}: {e}")
                    stats["errors"] += 1

            # Commit batch
            db.commit()
            logger.info(f"Encrypted {batch_encrypted} messages in batch (offset: {offset})")

            offset += batch_size

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Encryption migration complete: {stats}")
        return stats

    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed: {e}")
        stats["error"] = str(e)
        raise

    finally:
        db.close()


def check_encryption_status() -> dict:
    """
    Check current encryption status of message bodies.

    Returns:
        dict with counts of encrypted vs unencrypted messages
    """
    from .database import SessionLocal
    from .models import Message

    db = SessionLocal()
    try:
        total = db.query(Message).count()
        encrypted = db.query(Message).filter(Message.body_encrypted == True).count()
        unencrypted = db.query(Message).filter(Message.body_encrypted == False).count()
        expired = db.query(Message).filter(Message.content_expired == True).count()

        return {
            "total_messages": total,
            "encrypted": encrypted,
            "unencrypted": unencrypted,
            "content_expired": expired,
            "encryption_percentage": round((encrypted / total * 100), 2) if total > 0 else 0
        }

    finally:
        db.close()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m app.data_migration <command>")
        print("")
        print("Commands:")
        print("  encrypt_bodies  - Encrypt all existing message bodies")
        print("  status          - Check encryption status")
        sys.exit(1)

    command = sys.argv[1]

    if command == "encrypt_bodies":
        print("Starting encryption migration...")
        stats = migrate_encrypt_all_bodies()
        print(f"\nMigration complete:")
        print(f"  Total processed: {stats['total_processed']}")
        print(f"  Newly encrypted: {stats['newly_encrypted']}")
        print(f"  Already encrypted: {stats['already_encrypted']}")
        print(f"  Empty bodies: {stats['empty_bodies']}")
        print(f"  Errors: {stats['errors']}")

    elif command == "status":
        status = check_encryption_status()
        print("\nEncryption Status:")
        print(f"  Total messages: {status['total_messages']}")
        print(f"  Encrypted: {status['encrypted']}")
        print(f"  Unencrypted: {status['unencrypted']}")
        print(f"  Content expired: {status['content_expired']}")
        print(f"  Encryption %: {status['encryption_percentage']}%")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
