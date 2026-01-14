import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.data.models import Message, Task, PrincipalMemory, GmailAccount, UserSettings
from app.security.encryption import encrypt_token, encrypt_body

def create_ghost_instance(db: Session) -> str:
    """
    Creates a session-isolated 'Ghost' user with full demo data.
    Returns the generated user_id.
    """
    user_id = f"ghost_{uuid.uuid4().hex[:8]}"
    email = f"{user_id}@donna.demo"

    # 1. Create User Settings
    settings = UserSettings(
        user_id=user_id,
        user_email=email,
        subscription_tier="trial",
        subscription_status="trialing",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(settings)

    # 2. Create Mock Gmail Account
    account = GmailAccount(
        email=email,
        user_id=user_id,
        access_token=encrypt_token("demo_access_token"),
        refresh_token=encrypt_token("demo_refresh_token"),
        last_sync=datetime.now(timezone.utc)
    )
    db.add(account)
    db.flush()

    # 3. Seed Principal Memory
    memories = [
        {"key": "tone", "value": "Professional, executive, but concise.", "context_type": "drafting"},
        {"key": "sign_off", "value": "Best, [User]", "context_type": "drafting"},
        {"key": "vip_contacts", "value": "sarah.v@venture-cap.com, jack@internal-ops.io", "context_type": "filtering"}
    ]
    for mem in memories:
        db.add(PrincipalMemory(user_id=user_id, **mem))

    # 4. Seed Messages (Matching the prototype flows)
    msg1 = Message(
        message_id=f"msg_{uuid.uuid4().hex[:6]}",
        thread_id=f"thread_{uuid.uuid4().hex[:6]}",
        user_id=user_id,
        subject="Board Meeting Conflict: Q1 Strategy",
        sender="Sarah Voss <sarah.v@venture-cap.com>",
        recipient=email,
        body=encrypt_body("Hi, the board meeting is currently conflicting with the offsite. Can we reschedule?"),
        body_encrypted=True,
        received_at=datetime.now(timezone.utc) - timedelta(hours=2),
        processed=True,
        summary="Sarah is reporting a conflict between the board meeting and the offsite.",
        needs_reply=True,
        scheduling_intent=True,
        scheduling_intent_type="reschedule_request",
        scheduling_intent_confidence=0.95,
        status="inbox"
    )
    db.add(msg1)
    db.flush()

    # 5. Seed Tasks
    tasks = [
        {
            "title": "Prep Q4 Budget Review",
            "description": "Synthesize the department spends into a 3-slide deck.",
            "priority": "high",
            "status": "pending_approval",
            "message_id": msg1.id
        },
        {
            "title": "Approve Expense Reports",
            "description": "Five reports awaiting signature from the ops team.",
            "priority": "normal",
            "status": "approved",
            "message_id": msg1.id
        }
    ]
    for t in tasks:
        db.add(Task(user_id=user_id, **t))

    db.commit()
    return user_id
