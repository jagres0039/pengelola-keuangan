"""Transaction CRUD and summary queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from pengelola_keuangan.db.models import Category, Transaction, TransactionItem, TransactionType
from pengelola_keuangan.services.time_helpers import (
    current_month,
    get_zoneinfo,
    month_bounds,
    now_in,
    shift_months,
)


@dataclass(frozen=True)
class ItemInput:
    """Input for a single line item when creating a transaction."""

    name: str
    qty: Decimal
    unit_price: Decimal | None
    subtotal: Decimal


@dataclass(frozen=True)
class CategoryTotal:
    """A row in the by-category summary table."""

    category_id: int | None
    category_name: str
    total: Decimal


@dataclass(frozen=True)
class MonthlySummary:
    """Aggregate summary for a calendar month."""

    year: int
    month: int
    total_income: Decimal
    total_expense: Decimal
    expense_by_category: list[CategoryTotal]
    income_by_category: list[CategoryTotal]

    @property
    def balance(self) -> Decimal:
        return self.total_income - self.total_expense


def create_transaction(
    session: Session,
    *,
    user_id: int,
    transaction_type: TransactionType,
    amount: Decimal,
    category_id: int | None,
    note: str | None,
    occurred_at: datetime | None = None,
    user_tz: str = "Asia/Jakarta",
    items: list[ItemInput] | None = None,
) -> Transaction:
    """Insert a new transaction with optional line items."""
    transaction = Transaction(
        user_id=user_id,
        type=transaction_type,
        amount=amount,
        category_id=category_id,
        note=note,
        occurred_at=occurred_at or now_in(user_tz),
    )
    if items:
        transaction.items = [
            TransactionItem(
                name=item.name,
                qty=item.qty,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in items
        ]
    session.add(transaction)
    session.flush()
    return transaction


def replace_items(
    session: Session,
    user_id: int,
    transaction_id: int,
    items: list[ItemInput],
) -> Transaction | None:
    """Replace all items on a transaction. Returns the transaction (None if not found)."""
    transaction = get_transaction(session, user_id, transaction_id)
    if transaction is None:
        return None
    transaction.items = [
        TransactionItem(
            name=item.name,
            qty=item.qty,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
        )
        for item in items
    ]
    session.flush()
    return transaction


def get_transaction(session: Session, user_id: int, transaction_id: int) -> Transaction | None:
    """Get a single transaction scoped to a user (with items eagerly loaded)."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.items))
        .where(Transaction.id == transaction_id)
        .where(Transaction.user_id == user_id)
    )
    return session.scalar(stmt)


def delete_transaction(session: Session, user_id: int, transaction_id: int) -> Transaction | None:
    """Delete a transaction; returns the deleted row (None if not found)."""
    transaction = get_transaction(session, user_id, transaction_id)
    if transaction is None:
        return None
    session.delete(transaction)
    session.flush()
    return transaction


def list_recent(session: Session, user_id: int, limit: int = 10) -> list[Transaction]:
    """Return the user's most recent transactions (items eagerly loaded)."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.items))
        .where(Transaction.user_id == user_id)
        .order_by(desc(Transaction.occurred_at), desc(Transaction.id))
        .limit(limit)
    )
    return list(session.scalars(stmt))


def list_for_month(
    session: Session,
    user_id: int,
    year: int,
    month: int,
    tz_name: str,
) -> list[Transaction]:
    """Return all transactions in a calendar month for a user."""
    start, end = month_bounds(year, month, tz_name)
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at < end)
        .order_by(Transaction.occurred_at, Transaction.id)
    )
    return list(session.scalars(stmt))


def total_for_category_this_month(
    session: Session,
    user_id: int,
    category_id: int,
    tz_name: str,
) -> Decimal:
    """Sum expenses for a single category in the current calendar month."""
    year, month = current_month(tz_name)
    start, end = month_bounds(year, month, tz_name)
    stmt = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.user_id == user_id)
        .where(Transaction.category_id == category_id)
        .where(Transaction.type == TransactionType.EXPENSE)
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at < end)
    )
    return Decimal(session.scalar(stmt) or 0)


def summarize_month(
    session: Session,
    user_id: int,
    year: int,
    month: int,
    tz_name: str,
) -> MonthlySummary:
    """Compute monthly totals and category breakdowns."""
    start, end = month_bounds(year, month, tz_name)
    base = (
        select(
            Transaction.type,
            Transaction.category_id,
            func.coalesce(Category.name, "Tanpa kategori").label("category_name"),
            func.sum(Transaction.amount).label("total"),
        )
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .where(Transaction.user_id == user_id)
        .where(Transaction.occurred_at >= start)
        .where(Transaction.occurred_at < end)
        .group_by(Transaction.type, Transaction.category_id, Category.name)
    )
    rows = list(session.execute(base))

    income_rows: list[CategoryTotal] = []
    expense_rows: list[CategoryTotal] = []
    total_income = Decimal("0")
    total_expense = Decimal("0")
    for row in rows:
        amount = Decimal(row.total or 0)
        ct = CategoryTotal(
            category_id=row.category_id,
            category_name=row.category_name,
            total=amount,
        )
        if row.type == TransactionType.EXPENSE.value:
            expense_rows.append(ct)
            total_expense += amount
        else:
            income_rows.append(ct)
            total_income += amount

    expense_rows.sort(key=lambda r: r.total, reverse=True)
    income_rows.sort(key=lambda r: r.total, reverse=True)

    return MonthlySummary(
        year=year,
        month=month,
        total_income=total_income,
        total_expense=total_expense,
        expense_by_category=expense_rows,
        income_by_category=income_rows,
    )


def expense_trend(
    session: Session,
    user_id: int,
    months: int,
    tz_name: str,
) -> list[tuple[int, int, Decimal, Decimal]]:
    """Return list of ``(year, month, income, expense)`` for the last N months."""
    year, month = current_month(tz_name)
    results: list[tuple[int, int, Decimal, Decimal]] = []
    for delta in range(months - 1, -1, -1):
        y, m = shift_months(year, month, -delta)
        summary = summarize_month(session, user_id, y, m, tz_name)
        results.append((y, m, summary.total_income, summary.total_expense))
    return results


def update_transaction_fields(
    session: Session,
    user_id: int,
    transaction_id: int,
    *,
    amount: Decimal | None = None,
    category_id: int | None = None,
    note: str | None = None,
    occurred_at: datetime | None = None,
) -> Transaction | None:
    """Update one or more fields on a transaction."""
    transaction = get_transaction(session, user_id, transaction_id)
    if transaction is None:
        return None
    if amount is not None:
        transaction.amount = amount
    if category_id is not None:
        transaction.category_id = category_id
    if note is not None:
        transaction.note = note
    if occurred_at is not None:
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=get_zoneinfo("UTC"))
        transaction.occurred_at = occurred_at
    session.flush()
    return transaction
