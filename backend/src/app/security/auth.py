"""
Supabase Authentication Module

Architecture:
- Supabase Auth is the source of truth for identity
- auth.users (Supabase) holds identity
- UserSettings table links via user_id = auth.users.id
- JWT verified on every request, user context set for RLS
- Pure functions + FastAPI Depends (no globals, no singletons)

Security:
- Never trust client-side identity
- All user identity comes from verified JWT claims
- RLS policies enforce data isolation at database level
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy import text
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from app.infra.config import get_settings, Settings
from app.infra.database import get_db
from app.data.models import UserSettings


# =============================================================================
# Data Classes (immutable, no state)
# =============================================================================

@dataclass(frozen=True)
class AuthenticatedUser:
    """
    Immutable representation of an authenticated user from Supabase JWT.

    This is the single source of truth for user identity on the server.
    """
    user_id: str          # auth.uid() - the primary identifier
    email: str
    email_verified: bool
    provider: str
    app_metadata: dict
    user_metadata: dict

    @property
    def display_name(self) -> str:
        """Get user's display name from metadata or email"""
        return (
            self.user_metadata.get("full_name") or
            self.user_metadata.get("name") or
            self.email.split("@")[0]
        )

    @property
    def avatar_url(self) -> Optional[str]:
        """Get user's avatar URL from Google metadata"""
        return self.user_metadata.get("avatar_url") or self.user_metadata.get("picture")

    @classmethod
    def from_jwt_payload(cls, payload: dict) -> "AuthenticatedUser":
        """
        Create AuthenticatedUser from verified JWT claims.

        Supabase JWT structure:
        {
            "sub": "user-uuid",           # auth.uid()
            "email": "user@example.com",
            "email_verified": true,
            "app_metadata": {"provider": "google", ...},
            "user_metadata": {"full_name": "...", ...},
            "aud": "authenticated",
            "exp": 1234567890
        }
        """
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            raise ValueError("Invalid JWT: missing sub or email claim")

        app_metadata = payload.get("app_metadata", {})
        user_metadata = payload.get("user_metadata", {})

        return cls(
            user_id=user_id,
            email=email,
            email_verified=payload.get("email_verified", False),
            provider=app_metadata.get("provider", "google"),
            app_metadata=app_metadata,
            user_metadata=user_metadata,
        )


# =============================================================================
# Pure Functions (no state, no side effects)
# =============================================================================

def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    """
    Extract Bearer token from Authorization header.

    Pure function: str -> Optional[str]
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]

    return None


def verify_jwt(token: str, jwt_secret: str) -> dict:
    """
    Verify a Supabase JWT and return decoded claims.

    Pure function: (token, secret) -> claims dict

    Raises:
        HTTPException: If token is invalid or expired
    """
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: JWT secret not configured"
        )

    try:
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={
                "verify_exp": True,
                "verify_aud": True,
                "require": ["sub", "email", "exp", "aud"]
            }
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


def create_user_settings(user_id: str, email: str, trial_days: int = 7) -> UserSettings:
    """
    Create a new UserSettings instance.

    Pure function: returns new object, doesn't persist
    """
    return UserSettings(
        user_id=user_id,
        user_email=email,
        trial_ends_at=None  # Deferred trial: starts only when explicitly activated
    )


# =============================================================================
# FastAPI Dependencies (request-scoped, no shared state)
# =============================================================================

async def get_current_user(
    authorization: str = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    Get the authenticated user from JWT.

    Usage:
        @app.get("/protected")
        def route(user: AuthenticatedUser = Depends(get_current_user)):
            return {"user_id": user.user_id}
    """
    token = extract_token_from_header(authorization)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = verify_jwt(token, settings.SUPABASE_JWT_SECRET)

    try:
        return AuthenticatedUser.from_jwt_payload(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_optional(
    authorization: str = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> Optional[AuthenticatedUser]:
    """
    Optional authentication - returns None if not authenticated.

    Useful for routes that work differently for auth vs anon users.
    """
    token = extract_token_from_header(authorization)

    if not token:
        return None

    try:
        payload = verify_jwt(token, settings.SUPABASE_JWT_SECRET)
        return AuthenticatedUser.from_jwt_payload(payload)
    except (HTTPException, ValueError):
        return None


def get_db_for_user(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Session:
    """
    Get database session with RLS context set.

    Sets the user_id in PostgreSQL session so RLS policies
    can use it for automatic row filtering.

    Usage:
        @app.get("/messages")
        def get_messages(db: Session = Depends(get_db_for_user)):
            # RLS automatically filters to current user
            return db.query(Message).all()

    RLS policy example:
        CREATE POLICY "users_own_data" ON messages
        FOR ALL USING (user_id = current_setting('app.user_id', true));
    """
    db.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": user.user_id}
    )
    return db


def get_user_settings(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettings:
    """
    Get or create UserSettings for the authenticated user.

    Auto-creates profile on first authenticated request.
    """
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user.user_id
    ).first()

    if not settings:
        settings = create_user_settings(user.user_id, user.email)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


def get_user_with_settings(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
) -> tuple[AuthenticatedUser, UserSettings]:
    """
    Get both user and settings in one dependency.

    Usage:
        @app.get("/me")
        def get_me(data: tuple = Depends(get_user_with_settings)):
            user, settings = data
            return {"email": user.email, "tier": settings.subscription_tier}
    """
    return (user, settings)


def require_active_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
) -> AuthenticatedUser:
    """
    Require active subscription or valid trial.

    Use for premium features.
    """
    if not settings.is_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "subscription_required",
                "message": "This feature requires an active subscription.",
                "tier": settings.subscription_tier,
                "status": settings.subscription_status,
            }
        )
    return user


def require_pro_tier(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
) -> AuthenticatedUser:
    """
    Require Pro subscription (not trial).

    Use for features exclusive to paying customers.
    """
    if settings.subscription_tier != "pro":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "pro_required",
                "message": "This feature requires a Pro subscription.",
                "current_tier": settings.subscription_tier,
            }
        )
    return user


def require_credits_available(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: UserSettings = Depends(get_user_settings),
) -> AuthenticatedUser:
    """
    Require user has credits remaining for AI operations.

    Use on endpoints that consume Gemini tokens.
    Returns HTTP 402 when credits are exhausted.
    """
    from app.services.credits import check_credits_available

    can_proceed, error_details = check_credits_available(settings)

    if not can_proceed:
        # Determine action based on tier
        if settings.subscription_tier == "trial":
            action = "upgrade"
            message = "You've used all your trial AI credits. Upgrade to Pro for more."
        else:
            action = "wait_for_renewal"
            message = "You've used all your AI credits for this billing period."

        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "credits_exhausted",
                "message": message,
                "action": action,
                "credits_used": error_details["credits_used"],
                "credits_limit": error_details["credits_limit"],
                "tier": settings.subscription_tier,
            }
        )
    return user


# =============================================================================
# RLS Setup
# =============================================================================
# RLS policies are defined in: migrations/017_enable_rls_policies.sql
# Run that migration to enable Row Level Security on all user-owned tables.
