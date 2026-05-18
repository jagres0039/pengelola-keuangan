"""Shared FastAPI dependencies (DB session, auth)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from pengelola_keuangan.api.security import decode_access_token
from pengelola_keuangan.db.models import User
from pengelola_keuangan.db.session import get_session_factory
from pengelola_keuangan.services.subscriptions import get_status

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yield a transactional DB session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DBSession,
) -> User:
    """FastAPI dependency: return the authenticated user, or 401."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_active_subscription(user: CurrentUser, session: DBSession) -> User:
    """FastAPI dependency: same as CurrentUser but 402s if user can't write (trial expired)."""
    sub = get_status(user, session)
    if not sub.can_write:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="subscription kadaluarsa. Mohon bayar untuk lanjut catat transaksi.",
        )
    return user


CurrentUserCanWrite = Annotated[User, Depends(require_active_subscription)]


def require_admin(user: CurrentUser) -> User:
    """FastAPI dependency: 403 if user is not an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin only",
        )
    return user


CurrentAdmin = Annotated[User, Depends(require_admin)]
