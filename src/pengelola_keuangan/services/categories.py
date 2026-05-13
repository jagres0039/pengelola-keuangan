"""Category lookup, creation and renaming."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import Category, TransactionType


def list_categories(
    session: Session,
    user_id: int,
    transaction_type: TransactionType | None = None,
) -> list[Category]:
    """Return all categories for a user, optionally filtered by type."""
    stmt = select(Category).where(Category.user_id == user_id)
    if transaction_type is not None:
        stmt = stmt.where(Category.type == transaction_type)
    stmt = stmt.order_by(Category.is_default.desc(), Category.name)
    return list(session.scalars(stmt))


def find_category_by_name(
    session: Session,
    user_id: int,
    name: str,
    transaction_type: TransactionType,
) -> Category | None:
    """Case-insensitive lookup of category by name."""
    stmt = (
        select(Category)
        .where(Category.user_id == user_id)
        .where(Category.type == transaction_type)
        .where(Category.name.ilike(name))
    )
    return session.scalar(stmt)


def get_or_create_category(
    session: Session,
    user_id: int,
    name: str,
    transaction_type: TransactionType,
    emoji: str | None = None,
) -> Category:
    """Get-or-create a category by name."""
    existing = find_category_by_name(session, user_id, name, transaction_type)
    if existing is not None:
        return existing
    category = Category(
        user_id=user_id,
        name=name,
        type=transaction_type,
        emoji=emoji,
        is_default=False,
    )
    session.add(category)
    session.flush()
    return category


def get_category_by_id(session: Session, user_id: int, category_id: int) -> Category | None:
    """Lookup a single category by id, scoped to user."""
    stmt = select(Category).where(Category.id == category_id).where(Category.user_id == user_id)
    return session.scalar(stmt)


def rename_category(
    session: Session,
    user_id: int,
    category_id: int,
    new_name: str,
) -> Category | None:
    """Rename a category, returning the updated row (or None if not found)."""
    category = get_category_by_id(session, user_id, category_id)
    if category is None:
        return None
    category.name = new_name
    session.flush()
    return category


def delete_category(session: Session, user_id: int, category_id: int) -> bool:
    """Delete a category; returns True on success."""
    category = get_category_by_id(session, user_id, category_id)
    if category is None:
        return False
    session.delete(category)
    session.flush()
    return True


def fallback_category(
    session: Session,
    user_id: int,
    transaction_type: TransactionType,
) -> Category:
    """Return the ``Lainnya`` fallback category, creating it if missing."""
    return get_or_create_category(
        session,
        user_id,
        "Lainnya",
        transaction_type,
        emoji="✨",
    )
