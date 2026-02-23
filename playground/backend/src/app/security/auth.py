"""Playground auth/dependency shims for v1 route parity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, Query
from sqlalchemy.orm import Session

from app.db import get_db


@dataclass
class AuthenticatedUser:
    user_id: str
    display_name: Optional[str] = None
    is_admin: bool = True


def _resolve_user_id(
    x_user_id: Optional[str],
    user_id_query: Optional[str],
) -> str:
    return (x_user_id or user_id_query or "ea_demo").strip() or "ea_demo"


def get_current_user(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    user_id: Optional[str] = Query(default=None),
) -> AuthenticatedUser:
    resolved = _resolve_user_id(x_user_id=x_user_id, user_id_query=user_id)
    return AuthenticatedUser(user_id=resolved, display_name=resolved, is_admin=True)


def require_active_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    # Playground does not enforce billing tiers.
    return user


def require_credits_available(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    # Playground does not enforce credits.
    return user


def require_admin_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    # Playground grants admin access for local development.
    return user


def get_db_for_user(
    db: Session = Depends(get_db),
) -> Session:
    return db

