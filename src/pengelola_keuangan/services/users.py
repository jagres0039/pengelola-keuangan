"""User lifecycle helpers (lookup, registration, default category seeding)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pengelola_keuangan.config import get_settings
from pengelola_keuangan.db.defaults import (
    DEFAULT_EXPENSE_CATEGORIES,
    DEFAULT_INCOME_CATEGORIES,
)
from pengelola_keuangan.db.models import Category, TransactionType, User


def get_user_by_telegram_id(session: Session, telegram_user_id: int) -> User | None:
    """Lookup user by telegram_user_id."""
    stmt = select(User).where(User.telegram_user_id == telegram_user_id)
    return session.scalar(stmt)


def ensure_user(
    session: Session,
    telegram_user_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
) -> tuple[User, bool]:
    """Get-or-create a user. Returns (user, created)."""
    user = get_user_by_telegram_id(session, telegram_user_id)
    if user is not None:
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            session.flush()
        return user, False

    settings = get_settings()
    user = User(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        timezone=settings.default_timezone,
        currency=settings.default_currency,
    )
    session.add(user)
    session.flush()
    seed_default_categories(session, user)
    session.flush()
    return user, True


def seed_default_categories(session: Session, user: User) -> None:
    """Seed the user's default categories."""
    for name, emoji in DEFAULT_INCOME_CATEGORIES:
        session.add(
            Category(
                user_id=user.id,
                name=name,
                type=TransactionType.INCOME,
                emoji=emoji,
                is_default=True,
            )
        )
    for name, emoji in DEFAULT_EXPENSE_CATEGORIES:
        session.add(
            Category(
                user_id=user.id,
                name=name,
                type=TransactionType.EXPENSE,
                emoji=emoji,
                is_default=True,
            )
        )


def is_user_allowed(telegram_user_id: int) -> bool:
    """Check if the user is in the access allow-list (or list is empty = everyone)."""
    allowed = get_settings().allowed_user_id_set
    if not allowed:
        return True
    return telegram_user_id in allowed
