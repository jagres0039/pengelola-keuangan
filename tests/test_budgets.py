"""Tests for budget set/get/status."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import TransactionType
from pengelola_keuangan.services import budgets as budgets_svc
from pengelola_keuangan.services import categories as categories_svc
from pengelola_keuangan.services import transactions as transactions_svc
from pengelola_keuangan.services import users as users_svc


def test_budget_set_and_status(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 42)
    makanan = categories_svc.find_category_by_name(
        session, user.id, "Makanan", TransactionType.EXPENSE
    )
    assert makanan is not None
    budgets_svc.set_budget(session, user.id, makanan.id, Decimal("1500000"))

    transactions_svc.create_transaction(
        session,
        user_id=user.id,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("500000"),
        category_id=makanan.id,
        note=None,
        user_tz=user.timezone,
    )

    statuses = budgets_svc.list_budget_status(session, user.id, user.timezone)
    assert len(statuses) == 1
    status = statuses[0]
    assert status.category_name == "Makanan"
    assert status.limit == Decimal("1500000")
    assert status.spent == Decimal("500000")
    assert status.remaining == Decimal("1000000")
    assert status.percent == 33
    assert status.over_budget is False


def test_budget_over_limit(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 43)
    belanja = categories_svc.find_category_by_name(
        session, user.id, "Belanja", TransactionType.EXPENSE
    )
    assert belanja is not None
    budgets_svc.set_budget(session, user.id, belanja.id, Decimal("100000"))

    transactions_svc.create_transaction(
        session,
        user_id=user.id,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("250000"),
        category_id=belanja.id,
        note=None,
        user_tz=user.timezone,
    )

    statuses = budgets_svc.list_budget_status(session, user.id, user.timezone)
    assert len(statuses) == 1
    assert statuses[0].over_budget is True
    assert statuses[0].percent == 250


def test_budget_update(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 44)
    makanan = categories_svc.find_category_by_name(
        session, user.id, "Makanan", TransactionType.EXPENSE
    )
    assert makanan is not None
    budgets_svc.set_budget(session, user.id, makanan.id, Decimal("1000000"))
    budget = budgets_svc.set_budget(session, user.id, makanan.id, Decimal("2000000"))
    assert budget.monthly_limit == Decimal("2000000")

    assert budgets_svc.delete_budget(session, user.id, makanan.id) is True
    assert budgets_svc.delete_budget(session, user.id, makanan.id) is False
