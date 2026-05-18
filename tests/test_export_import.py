"""Tests for export → import round-trip."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import TransactionType
from pengelola_keuangan.services import categories as categories_svc
from pengelola_keuangan.services import exporting as exporting_svc
from pengelola_keuangan.services import importing as importing_svc
from pengelola_keuangan.services import transactions as transactions_svc
from pengelola_keuangan.services import users as users_svc
from pengelola_keuangan.services.time_helpers import current_month


def _seed_transactions(session: Session, user_id: int, tz: str) -> None:
    makanan = categories_svc.find_category_by_name(
        session, user_id, "Makanan", TransactionType.EXPENSE
    )
    gaji = categories_svc.find_category_by_name(session, user_id, "Gaji", TransactionType.INCOME)
    assert makanan is not None
    assert gaji is not None
    transactions_svc.create_transaction(
        session,
        user_id=user_id,
        transaction_type=TransactionType.INCOME,
        amount=Decimal("5000000"),
        category_id=gaji.id,
        note="gaji",
        user_tz=tz,
    )
    transactions_svc.create_transaction(
        session,
        user_id=user_id,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("35000"),
        category_id=makanan.id,
        note="makan siang",
        user_tz=tz,
    )


def test_export_xlsx_roundtrip_noop(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 11)
    _seed_transactions(session, user.id, user.timezone)

    year, month = current_month(user.timezone)
    xlsx_bytes = exporting_svc.export_month_to_xlsx(
        session, user.id, year, month, user.timezone, user.currency
    )

    rows, parse_errors = importing_svc.parse_import_rows(xlsx_bytes, user.timezone)
    assert parse_errors == []
    assert len(rows) == 2

    existing = transactions_svc.list_for_month(session, user.id, year, month, user.timezone)
    plan = importing_svc.build_import_plan(session, user.id, rows, existing)
    assert plan.to_create == []
    assert plan.to_update == []
    assert plan.to_delete == []


def test_export_csv_includes_all_rows(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 12)
    _seed_transactions(session, user.id, user.timezone)
    year, month = current_month(user.timezone)
    csv_bytes = exporting_svc.export_month_to_csv(session, user.id, year, month, user.timezone)
    text = csv_bytes.decode("utf-8-sig")
    assert "id,tanggal,tipe,jumlah,kategori,catatan" in text
    assert "Makanan" in text
    assert "Gaji" in text


def test_import_detects_changes(session: Session) -> None:
    user, _ = users_svc.ensure_user(session, 13)
    _seed_transactions(session, user.id, user.timezone)

    year, month = current_month(user.timezone)
    xlsx_bytes = exporting_svc.export_month_to_xlsx(
        session, user.id, year, month, user.timezone, user.currency
    )
    rows, _ = importing_svc.parse_import_rows(xlsx_bytes, user.timezone)
    assert len(rows) == 2

    # Modify one row's amount and drop the other.
    modified = importing_svc.ImportRow(
        row_index=rows[0].row_index,
        id=rows[0].id,
        occurred_at=rows[0].occurred_at,
        type=rows[0].type,
        amount=rows[0].amount + Decimal("100"),
        category_name=rows[0].category_name,
        note=rows[0].note,
    )
    new_rows = [modified]

    existing = transactions_svc.list_for_month(session, user.id, year, month, user.timezone)
    plan = importing_svc.build_import_plan(session, user.id, new_rows, existing)
    assert len(plan.to_update) == 1
    assert len(plan.to_delete) == 1

    created, updated, deleted = importing_svc.apply_import_plan(
        session, user.id, plan, user.timezone
    )
    assert (created, updated, deleted) == (0, 1, 1)

    refreshed = transactions_svc.list_for_month(session, user.id, year, month, user.timezone)
    assert len(refreshed) == 1
    assert refreshed[0].amount == modified.amount
