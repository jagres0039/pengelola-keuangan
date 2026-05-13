"""Auth endpoints: register, login, /me, link Telegram."""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import (
    LinkCodeResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)
from pengelola_keuangan.api.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from pengelola_keuangan.config import get_settings
from pengelola_keuangan.db.models import User
from pengelola_keuangan.services.users import seed_default_categories

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        username=user.username,
        timezone=user.timezone,
        currency=user.currency,
        telegram_linked=user.telegram_user_id is not None,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: DBSession) -> TokenResponse:
    """Register a new account with email + password."""
    email = payload.email.lower().strip()
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email udah dipake",
        )
    settings = get_settings()
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        timezone=settings.default_timezone,
        currency=settings.default_currency,
    )
    session.add(user)
    session.flush()
    seed_default_categories(session, user)
    session.flush()
    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: DBSession) -> TokenResponse:
    """Login with email + password."""
    email = payload.email.lower().strip()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="email atau password salah",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="email atau password salah",
        )
    token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user."""
    return _user_to_response(user)


@router.patch("/me", response_model=UserResponse)
def update_me(payload: UpdateUserRequest, user: CurrentUser, session: DBSession) -> UserResponse:
    """Update profile fields (first_name / timezone / currency)."""
    if payload.first_name is not None:
        user.first_name = payload.first_name.strip() or None
    if payload.timezone is not None:
        user.timezone = payload.timezone.strip()
    if payload.currency is not None:
        user.currency = payload.currency.upper().strip()
    session.flush()
    return _user_to_response(user)


@router.post("/link-code", response_model=LinkCodeResponse)
def issue_link_code(user: CurrentUser, session: DBSession) -> LinkCodeResponse:
    """Issue a short code for linking a Telegram chat to this account.

    User logs into PWA -> request /auth/link-code -> sends the code to bot
    via /link <code>. Bot validates within 15 minutes and binds telegram_user_id.
    """
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(6))
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    user.link_code = code
    user.link_code_expires_at = expires_at
    session.flush()
    return LinkCodeResponse(code=code, expires_at=expires_at)
