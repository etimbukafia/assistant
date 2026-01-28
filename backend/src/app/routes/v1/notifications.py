"""
Notification API endpoints

- GET /notifications/ - List notifications (paginated)
- GET /notifications/unread-count - Unread badge count
- POST /notifications/mark-read - Mark specific notifications as read
- POST /notifications/mark-all-read - Mark all as read
- POST /notifications/device-token - Register Expo push token
- DELETE /notifications/device-token - Unregister push token
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, get_db_for_user, AuthenticatedUser
from app.data.schemas import (
    NotificationListResponse, UnreadCountResponse,
    MarkReadRequest, DeviceTokenRegisterRequest, DeviceTokenResponse,
)
from app.data.models import DeviceToken
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Get paginated notification feed."""
    service = NotificationService(db, user.user_id)
    notifications, total, unread_count = service.get_notifications(limit=limit, offset=offset)
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Get unread notification count (for badge)."""
    service = NotificationService(db, user.user_id)
    return UnreadCountResponse(unread_count=service.get_unread_count())


@router.post("/mark-read")
def mark_notifications_read(
    request: MarkReadRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Mark specific notifications as read."""
    service = NotificationService(db, user.user_id)
    service.mark_read(request.notification_ids)
    return {"status": "ok"}


@router.post("/mark-all-read")
def mark_all_read(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Mark all notifications as read."""
    service = NotificationService(db, user.user_id)
    service.mark_all_read()
    return {"status": "ok"}


@router.post("/device-token", response_model=DeviceTokenResponse)
def register_device_token(
    request: DeviceTokenRegisterRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Register or update an Expo push token."""
    existing = db.query(DeviceToken).filter(
        DeviceToken.expo_push_token == request.expo_push_token
    ).first()

    if existing:
        existing.user_id = user.user_id
        existing.device_name = request.device_name
        existing.platform = request.platform
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    token = DeviceToken(
        user_id=user.user_id,
        expo_push_token=request.expo_push_token,
        device_name=request.device_name,
        platform=request.platform,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.delete("/device-token")
def unregister_device_token(
    request: DeviceTokenRegisterRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db_for_user),
):
    """Deactivate a push token (on logout or disable)."""
    token = db.query(DeviceToken).filter(
        DeviceToken.expo_push_token == request.expo_push_token,
        DeviceToken.user_id == user.user_id,
    ).first()

    if token:
        token.is_active = False
        db.commit()

    return {"status": "ok"}
