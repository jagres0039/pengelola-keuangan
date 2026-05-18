"""Default categories seeded for new users."""

from __future__ import annotations

from pengelola_keuangan.db.models import TransactionType

DEFAULT_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Gaji", "💰"),
    ("Bonus", "🎁"),
    ("Freelance", "💼"),
    ("Investasi", "📈"),
    ("Lainnya", "✨"),
]

DEFAULT_EXPENSE_CATEGORIES: list[tuple[str, str]] = [
    ("Makanan", "🍽️"),
    ("Transport", "🚗"),
    ("Belanja", "🛒"),
    ("Tagihan", "🧾"),
    ("Hiburan", "🎬"),
    ("Kesehatan", "🏥"),
    ("Pendidikan", "📚"),
    ("Lainnya", "✨"),
]


def default_categories_for(
    transaction_type: TransactionType,
) -> list[tuple[str, str]]:
    """Return the default categories for the given transaction type."""
    if transaction_type is TransactionType.INCOME:
        return DEFAULT_INCOME_CATEGORIES
    return DEFAULT_EXPENSE_CATEGORIES
