"""Tests for money / month formatting."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pengelola_keuangan.services.formatting import format_money, format_month, percentage


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        (Decimal("0"), "IDR", "Rp 0"),
        (Decimal("1000"), "IDR", "Rp 1.000"),
        (Decimal("1000000"), "IDR", "Rp 1.000.000"),
        (Decimal("5000.49"), "IDR", "Rp 5.000"),
        (Decimal("5000.50"), "IDR", "Rp 5.000"),
    ],
)
def test_format_money_idr(amount: Decimal, currency: str, expected: str) -> None:
    assert format_money(amount, currency) == expected


def test_format_money_usd() -> None:
    assert format_money(Decimal("1234.5"), "USD") == "USD 1.234,50"


def test_format_money_negative_usd() -> None:
    assert format_money(Decimal("-99.99"), "USD") == "-USD 99,99"


def test_format_month_indonesian() -> None:
    assert format_month(2026, 5) == "Mei 2026"
    assert format_month(2025, 12) == "Desember 2025"


def test_percentage_zero_total() -> None:
    assert percentage(Decimal("100"), Decimal("0")) == 0


def test_percentage_basic() -> None:
    assert percentage(Decimal("50"), Decimal("200")) == 25
