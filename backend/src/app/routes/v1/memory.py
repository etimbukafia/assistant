from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.data.models import PrincipalMemory, DecisionPattern, ContactContext
from app.data.schemas import (
    PrincipalMemoryResponse, PrincipalMemoryCreate, PrincipalMemoryUpdate, PrincipalMemoryListResponse,
    DecisionPatternListResponse, DecisionPatternActionRequest, DecisionPatternResponse,
    ContactContextResponse, ContactContextUpdateRequest, ContactContextListResponse
)
from app.intelligence.context_builder import ContextBuilder

router = APIRouter(prefix="/memory", tags=["Memory"])

# ========================================
# PRINCIPAL MEMORY ENDPOINTS
# ========================================

@router.get("/preferences", response_model=PrincipalMemoryListResponse)
def get_preferences(
    context_type: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db_for_user)
):
    """Get all user preferences, optionally filtered by context type"""
    # RLS automatically filters by current user
    query = db.query(PrincipalMemory)

    if context_type:
        query = query.filter(PrincipalMemory.context_type == context_type)

    total = query.count()
    preferences = query.order_by(PrincipalMemory.key).offset(offset).limit(limit).all()

    return PrincipalMemoryListResponse(preferences=preferences, total=total)


@router.post("/preferences", response_model=PrincipalMemoryResponse)
def create_preference(
    request: PrincipalMemoryCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Create a new user preference"""
    # Check if preference with this key already exists
    existing = db.query(PrincipalMemory).filter(
        PrincipalMemory.key == request.key,
        PrincipalMemory.context_type == request.context_type
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Preference '{request.key}' for context '{request.context_type}' already exists. Use PUT to update."
        )

    preference = PrincipalMemory(
        user_id=user.user_id,
        key=request.key,
        value=request.value,
        context_type=request.context_type,
        source=request.source
    )

    db.add(preference)
    db.commit()
    db.refresh(preference)

    return preference


@router.put("/preferences/{preference_id}", response_model=PrincipalMemoryResponse)
def update_preference(
    preference_id: int,
    request: PrincipalMemoryUpdate,
    db: Session = Depends(get_db_for_user)
):
    """Update an existing preference"""
    preference = db.query(PrincipalMemory).filter(
        PrincipalMemory.id == preference_id
    ).first()

    if not preference:
        raise HTTPException(status_code=404, detail="Preference not found")

    if request.value is not None:
        preference.value = request.value
    if request.context_type is not None:
        preference.context_type = request.context_type

    db.commit()
    db.refresh(preference)

    return preference


@router.delete("/preferences/{preference_id}")
def delete_preference(preference_id: int, db: Session = Depends(get_db_for_user)):
    """Delete a preference"""
    preference = db.query(PrincipalMemory).filter(
        PrincipalMemory.id == preference_id
    ).first()

    if not preference:
        raise HTTPException(status_code=404, detail="Preference not found")

    db.delete(preference)
    db.commit()

    return {"message": "Preference deleted", "id": preference_id}


# ========================================
# DECISION PATTERNS ENDPOINTS
# ========================================

@router.get("/patterns", response_model=DecisionPatternListResponse)
def get_patterns(
    status: str = None,
    context_type: str = None,
    min_confidence: float = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db_for_user)
):
    """Get decision patterns, optionally filtered"""
    # RLS filters by user
    query = db.query(DecisionPattern)

    if status:
        query = query.filter(DecisionPattern.status == status)
    if context_type:
        query = query.filter(DecisionPattern.context_type == context_type)
    if min_confidence:
        query = query.filter(DecisionPattern.confidence >= min_confidence)

    total = query.count()
    patterns = query.order_by(DecisionPattern.confidence.desc()).offset(offset).limit(limit).all()

    return DecisionPatternListResponse(patterns=patterns, total=total)


@router.get("/patterns/suggestions", response_model=DecisionPatternListResponse)
def get_pattern_suggestions(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db_for_user)
):
    """
    Get patterns ready to be surfaced as suggestions.
    Only returns patterns with:
    - status = 'observed' (not yet suggested/rejected)
    - confidence >= 0.6 (at least 3 occurrences)
    - not stale (has occurrence within 90 days)
    """
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=90)

    query = db.query(DecisionPattern).filter(
        DecisionPattern.status == "observed",
        DecisionPattern.confidence >= 0.6,
        DecisionPattern.last_occurrence_at >= stale_threshold
    ).order_by(DecisionPattern.confidence.desc())

    total = query.count()
    patterns = query.offset(offset).limit(limit).all()

    return DecisionPatternListResponse(patterns=patterns, total=total)


@router.post("/patterns/{pattern_id}/action")
def action_on_pattern(
    pattern_id: int,
    request: DecisionPatternActionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Take action on a pattern suggestion:
    - approve: Convert to PrincipalMemory preference
    - reject: Mark as rejected (never suggest again)
    - not_now: Mark as suggested (may surface again later)
    """
    pattern = db.query(DecisionPattern).filter(
        DecisionPattern.id == pattern_id
    ).first()

    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    if request.action == "approve":
        # Create preference from pattern
        preference = PrincipalMemory(
            user_id=user.user_id,
            key=pattern.pattern_key,
            value=pattern.action,
            context_type=pattern.context_type,
            source="approved_suggestion"
        )
        db.add(preference)

        pattern.status = "approved"
        db.commit()

        return {
            "message": "Pattern approved and saved as preference",
            "preference_id": preference.id
        }

    elif request.action == "reject":
        pattern.status = "rejected"
        db.commit()
        return {"message": "Pattern rejected. It won't be suggested again."}

    elif request.action == "not_now":
        pattern.status = "suggested"
        db.commit()
        return {"message": "Pattern noted. May be suggested again later."}

    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: approve, reject, not_now")


# ========================================
# CONTACT CONTEXT ENDPOINTS
# ========================================

@router.get("/contacts", response_model=ContactContextListResponse)
def get_contacts(
    category: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db_for_user)
):
    """Get all contact contexts, optionally filtered by category"""
    query = db.query(ContactContext)

    if category:
        query = query.filter(ContactContext.category == category)

    total = query.count()
    contacts = query.order_by(ContactContext.contact_email).offset(offset).limit(limit).all()

    return ContactContextListResponse(contacts=contacts, total=total)


@router.get("/contacts/{contact_email}", response_model=ContactContextResponse)
def get_contact(contact_email: str, db: Session = Depends(get_db_for_user)):
    """Get contact context for a specific email"""
    contact = db.query(ContactContext).filter(
        ContactContext.contact_email == contact_email
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact


@router.put("/contacts/{contact_email}", response_model=ContactContextResponse)
def update_contact(
    contact_email: str,
    request: ContactContextUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """Update contact context (manual fields only: notes, category, preferred_tone)"""
    contact = db.query(ContactContext).filter(
        ContactContext.contact_email == contact_email
    ).first()

    if not contact:
        # Create new contact context
        contact = ContactContext(
            user_id=user.user_id,
            contact_email=contact_email
        )
        db.add(contact)

    # Update manual fields only
    if request.contact_name is not None:
        contact.contact_name = request.contact_name
    if request.notes is not None:
        contact.notes = request.notes
    if request.category is not None:
        contact.category = request.category
    if request.preferred_tone is not None:
        contact.preferred_tone = request.preferred_tone

    db.commit()
    db.refresh(contact)

    return contact


@router.delete("/contacts/{contact_email}")
def delete_contact(contact_email: str, db: Session = Depends(get_db_for_user)):
    """Delete contact context"""
    contact = db.query(ContactContext).filter(
        ContactContext.contact_email == contact_email
    ).first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()

    return {"message": "Contact context deleted", "email": contact_email}


@router.get("/context/preview")
def preview_context(
    context_type: str,
    sender_email: str = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user)
):
    """
    Preview what context would be injected for a given context type.
    Useful for debugging and transparency.
    """

    valid_types = ["drafting", "scheduling", "task_review"]
    if context_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid context_type. Must be one of: {valid_types}"
        )

    builder = ContextBuilder(db, user_id=user.user_id)
    summary = builder.get_context_summary(context_type, sender_email)

    return summary
