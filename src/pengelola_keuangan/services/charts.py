"""Generate chart PNGs."""

from __future__ import annotations

import io
from decimal import Decimal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pengelola_keuangan.services.formatting import format_month  # noqa: E402
from pengelola_keuangan.services.transactions import (  # noqa: E402
    MonthlySummary,
)


def render_category_pie(summary: MonthlySummary) -> bytes:
    """Render a pie chart of expenses by category."""
    fig, ax = plt.subplots(figsize=(6, 6))
    rows = [r for r in summary.expense_by_category if r.total > 0]
    if not rows:
        ax.text(0.5, 0.5, "Belum ada pengeluaran", ha="center", va="center")
        ax.axis("off")
    else:
        labels = [r.category_name for r in rows]
        values = [float(r.total) for r in rows]
        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        )
        ax.set_title(
            f"Pengeluaran per Kategori — {format_month(summary.year, summary.month)}",
            fontsize=13,
            pad=15,
        )

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def render_trend_chart(
    trend: list[tuple[int, int, Decimal, Decimal]],
) -> bytes:
    """Render a line chart of monthly income vs expense for the last N months."""
    fig, ax = plt.subplots(figsize=(8, 5))
    if not trend:
        ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center")
        ax.axis("off")
    else:
        labels = [format_month(y, m).split()[0][:3] + f" {y % 100:02d}" for y, m, _, _ in trend]
        incomes = [float(i) for _, _, i, _ in trend]
        expenses = [float(e) for _, _, _, e in trend]
        ax.plot(labels, incomes, marker="o", linewidth=2, label="Pemasukan", color="#2ECC71")
        ax.plot(labels, expenses, marker="o", linewidth=2, label="Pengeluaran", color="#E74C3C")
        ax.fill_between(labels, incomes, expenses, alpha=0.1, color="#3498DB")
        ax.set_title("Tren Pemasukan vs Pengeluaran", fontsize=14, pad=12)
        ax.set_ylabel("Jumlah")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="best")
        for tick in ax.get_xticklabels():
            tick.set_rotation(0)

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
