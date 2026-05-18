"""Tests for the user + category + transaction service layer."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import TransactionType
from pengelola_keuangan.services import categories as categories_svc
from pengelola_keuangan.services import transactions as transactions_svc
from pengelola_keuangan.services import users as users_svc


def test_ensure_user_seeds_defaults(session: Session) -> None:
    user, created = users_svc.ensure_user(session, 12345, username="testuser")
    assert created is True
    assert user.username == "testuser"
    income = categories_svc.list_categories(session, user.id, TransactionType.INCOME)
    expense = categories_svc.list_categories(session, user.id, TransactionType.EXPENSE)
    assert len(income) > 0
    assert len(expense) > 0
    assert any(c.name == "Gaji" for c in income)
    assert any(c.name == "Makanan" for c in expense)


def test_ensure_user_idempotent(session: Session) -> None:
    user1, created1 = users_svc.ensure_user(session, 9999, username="a")
    user2, created2 = users_svc.ensure_user(session, 9999, username="b")
    assert created1 is True
    assert created2 is False
    assert user1.id == user2.id
    assert user2.username == "b"


def test_create_and_summarize_transactions(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 1)
    makanan = categories_svc.find_category_by_name(
        session, user.id, "Makanan", TransactionType.EXPENSE
    )
    assert makanan is not None
    gaji = categories_svc.find_category_by_name(session, user.id, "Gaji", TransactionType.INCOME)
    assert gaji is not None

    transactions_svc.create_transaction(
        session,
        user_id=user.id,
        transaction_type=TransactionType.INCOME,
        amount=Decimal("5000000"),
        category_id=gaji.id,
        note="gaji bulan ini",
        user_tz=user.timezone,
    )
    transactions_svc.create_transaction(
        session,
        user_id=user.id,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("35000"),
        category_id=makanan.id,
        note="makan siang",
        user_tz=user.timezone,
    )

    from pengelola_keuangan.services.time_helpers import current_month

    year, month = current_month(user.timezone)
    summary = transactions_svc.summarize_month(session, user.id, year, month, user.timezone)
    assert summary.total_income == Decimal("5000000")
    assert summary.total_expense == Decimal("35000")
    assert summary.balance == Decimal("4965000")
    assert any(r.category_name == "Makanan" for r in summary.expense_by_category)


def test_multi_user_isolation(session: Session) -> None:
    user_a, _ = users_svc.ensure_user(session, 100)
    user_b, _ = users_svc.ensure_user(session, 200)
    cat_a = categories_svc.find_category_by_name(
        session, user_a.id, "Makanan", TransactionType.EXPENSE
    )
    assert cat_a is not None
    transactions_svc.create_transaction(
        session,
        user_id=user_a.id,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("100"),
        category_id=cat_a.id,
        note=None,
        user_tz=user_a.timezone,
    )

    history_b = transactions_svc.list_recent(session, user_b.id)
    assert history_b == []
    history_a = transactions_svc.list_recent(session, user_a.id)
    assert len(history_a) == 1
