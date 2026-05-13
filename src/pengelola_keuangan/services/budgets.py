"""Budget management."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import Budget, Category, TransactionType
from pengelola_keuangan.services.transactions import total_for_category_this_month


@dataclass(frozen=True)
class BudgetStatus:
    """Snapshot of how much of a budget has been spent this month."""

    category_id: int
    category_name: str
    limit: Decimal
    spent: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.limit - self.spent

    @property
    def percent(self) -> int:
        if self.limit == 0:
            return 0
        return int((self.spent / self.limit) * 100)

    @property
    def over_budget(self) -> bool:
        return self.spent > self.limit


def set_budget(
    session: Session,
    user_id: int,
    category_id: int,
    monthly_limit: Decimal,
) -> Budget:
    """Create or update a budget for a category."""
    stmt = select(Budget).where(Budget.user_id == user_id).where(Budget.category_id == category_id)
    budget = session.scalar(stmt)
    if budget is None:
        budget = Budget(
            user_id=user_id,
            category_id=category_id,
            monthly_limit=monthly_limit,
        )
        session.add(budget)
    else:
        budget.monthly_limit = monthly_limit
    session.flush()
    return budget


def get_budget(session: Session, user_id: int, category_id: int) -> Budget | None:
    """Return the budget row for a specific category (or None)."""
    stmt = select(Budget).where(Budget.user_id == user_id).where(Budget.category_id == category_id)
    return session.scalar(stmt)


def delete_budget(session: Session, user_id: int, category_id: int) -> bool:
    """Delete a budget; returns True on success."""
    budget = get_budget(session, user_id, category_id)
    if budget is None:
        return False
    session.delete(budget)
    session.flush()
    return True


def list_budget_status(
    session: Session,
    user_id: int,
    tz_name: str,
) -> list[BudgetStatus]:
    """Return budget vs actual spending status for the current month."""
    stmt = (
        select(Budget, Category.name)
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == user_id)
        .where(Category.type == TransactionType.EXPENSE)
        .order_by(Category.name)
    )
    result: list[BudgetStatus] = []
    for budget, name in session.execute(stmt):
        spent = total_for_category_this_month(session, user_id, budget.category_id, tz_name)
        result.append(
            BudgetStatus(
                category_id=budget.category_id,
                category_name=name,
                limit=Decimal(budget.monthly_limit),
                spent=spent,
            )
        )
    return result
