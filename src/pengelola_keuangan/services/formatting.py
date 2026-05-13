"""Formatting helpers for money, dates and summary text."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

INDONESIAN_MONTHS: dict[int, str] = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


def format_money(amount: Decimal, currency: str = "IDR") -> str:
    """Format a Decimal amount with a currency prefix."""
    quantized = (
        amount.quantize(Decimal("1")) if currency == "IDR" else amount.quantize(Decimal("0.01"))
    )
    if currency == "IDR":
        whole = int(quantized)
        formatted = f"{whole:,}".replace(",", ".")
        return f"Rp {formatted}"
    sign = "-" if quantized < 0 else ""
    abs_value = abs(quantized)
    parts = f"{abs_value:,.2f}".split(".")
    parts[0] = parts[0].replace(",", ".")
    return f"{sign}{currency} {parts[0]},{parts[1]}"


def format_month(year: int, month: int) -> str:
    """Return a long Indonesian month label, e.g. ``Mei 2026``."""
    return f"{INDONESIAN_MONTHS.get(month, str(month))} {year}"


def format_datetime(dt: datetime) -> str:
    """Return a short ``dd/mm HH:MM`` representation."""
    return dt.strftime("%d/%m %H:%M")


def percentage(part: Decimal, total: Decimal) -> int:
    """Return ``part / total`` as a 0..N integer percentage (no upper clamp)."""
    if total == 0:
        return 0
    return int((part / total) * 100)
