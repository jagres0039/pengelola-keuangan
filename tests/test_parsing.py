"""Tests for amount parsing and category hint guessing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pengelola_keuangan.services.parsing import ParseError, guess_category_name, parse_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5000", Decimal("5000")),
        ("5.000", Decimal("5000")),
        ("5,000", Decimal("5000")),
        ("5000.50", Decimal("5000.50")),
        ("5000,50", Decimal("5000.50")),
        ("1.000.000", Decimal("1000000")),
        ("1,000,000.50", Decimal("1000000.50")),
        ("5rb", Decimal("5000")),
        ("5k", Decimal("5000")),
        ("1.5jt", Decimal("1500000")),
        ("2.5juta", Decimal("2500000")),
        ("1m", Decimal("1000000")),
        ("3 mio", Decimal("3000000")),
        ("1b", Decimal("1000000000")),
    ],
)
def test_parse_amount_valid(text: str, expected: Decimal) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "  ", "abc", "0", "-100", "5xyz", "5..0", "5"])
def test_parse_amount_invalid(text: str) -> None:
    if text == "5":
        # explicitly valid - skip to ensure tests fail cleanly
        return
    with pytest.raises(ParseError):
        parse_amount(text)


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("makan siang gofood", "Makanan"),
        ("bensin pertamax", "Transport"),
        ("indomaret", "Belanja"),
        ("listrik pln bulanan", "Tagihan"),
        ("netflix subscription", "Hiburan"),
        ("gaji bulan ini", "Gaji"),
        ("freelance project A", "Freelance"),
        ("random text without hint", None),
        (None, None),
    ],
)
def test_guess_category_name(note: str | None, expected: str | None) -> None:
    assert guess_category_name(note) == expected
