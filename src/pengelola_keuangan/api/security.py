"""Password hashing and JWT token helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from pengelola_keuangan.config import get_settings


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    if not password:
        raise ValueError("password kosong")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *,
    user_id: int,
    expires_in_minutes: int | None = None,
) -> str:
    """Create a JWT access token for the given user."""
    settings = get_settings()
    minutes = expires_in_minutes or settings.jwt_expires_minutes
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token


def decode_access_token(token: str) -> int:
    """Return the user_id encoded in a JWT, or raise."""
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    sub = payload.get("sub")
    if sub is None:
        raise jwt.InvalidTokenError("missing sub")
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise jwt.InvalidTokenError("invalid sub") from exc
