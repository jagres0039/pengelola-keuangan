"""Recurring transactions: storage and execution."""

from __future__ import annotations

import calendar
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import Recurring, RecurringFrequency, Transaction, User
from pengelola_keuangan.services.time_helpers import get_zoneinfo, now_in


def list_recurring(session: Session, user_id: int) -> list[Recurring]:
    """List all recurring templates for a user."""
    stmt = select(Recurring).where(Recurring.user_id == user_id).order_by(Recurring.id)
    return list(session.scalars(stmt))


def get_recurring(session: Session, user_id: int, recurring_id: int) -> Recurring | None:
    """Get a single recurring template scoped to a user."""
    stmt = select(Recurring).where(Recurring.id == recurring_id).where(Recurring.user_id == user_id)
    return session.scalar(stmt)


def delete_recurring(session: Session, user_id: int, recurring_id: int) -> bool:
    """Delete a recurring template; returns True on success."""
    recurring = get_recurring(session, user_id, recurring_id)
    if recurring is None:
        return False
    session.delete(recurring)
    session.flush()
    return True


def _should_run(now: datetime, recurring: Recurring) -> bool:
    """Decide whether a recurring template should fire at ``now`` in the user's timezone."""
    last = recurring.last_run_at
    if recurring.frequency is RecurringFrequency.DAILY:
        if last is None:
            return True
        return last.date() < now.date()

    if recurring.frequency is RecurringFrequency.WEEKLY:
        if now.weekday() != recurring.day_of_period:
            return False
        if last is None:
            return True
        return last.date() < now.date()

    if recurring.frequency is RecurringFrequency.MONTHLY:
        last_day = calendar.monthrange(now.year, now.month)[1]
        target_day = min(recurring.day_of_period, last_day)
        if now.day != target_day:
            return False
        if last is None:
            return True
        return last.year != now.year or last.month != now.month

    return False


def run_due_recurring(session: Session) -> int:
    """Run all recurring templates that are due. Returns the number of transactions created."""
    stmt = (
        select(Recurring, User)
        .join(User, User.id == Recurring.user_id)
        .where(Recurring.active.is_(True))
    )
    count = 0
    for recurring, user in session.execute(stmt):
        tz_name = user.timezone or "Asia/Jakarta"
        now_local = now_in(tz_name)
        if not _should_run(now_local, recurring):
            continue
        transaction = Transaction(
            user_id=recurring.user_id,
            type=recurring.type,
            amount=recurring.amount,
            category_id=recurring.category_id,
            note=recurring.note or "Recurring",
            occurred_at=now_local,
        )
        session.add(transaction)
        recurring.last_run_at = now_local.astimezone(get_zoneinfo("UTC"))
        count += 1
    if count:
        session.flush()
    return count
