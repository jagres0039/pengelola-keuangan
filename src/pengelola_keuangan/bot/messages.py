"""User-facing message templates (Indonesian)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pengelola_keuangan.db.models import (
    Category,
    Recurring,
    RecurringFrequency,
    Transaction,
    TransactionType,
)
from pengelola_keuangan.services.budgets import BudgetStatus
from pengelola_keuangan.services.formatting import (
    format_datetime,
    format_money,
    format_month,
    percentage,
)
from pengelola_keuangan.services.time_helpers import to_user_tz
from pengelola_keuangan.services.transactions import MonthlySummary

WEEK_DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def welcome(name: str | None) -> str:
    """Welcome message for /start."""
    greeting = f"Halo {name}" if name else "Halo bro"
    return (
        f"👋 {greeting}! Gw bot pengelola keuangan lo.\n\n"
        "Pake perintah ini buat mulai:\n"
        "• `/in 5000000 gaji` — catat pemasukan\n"
        "• `/out 35000 makan siang` — catat pengeluaran\n"
        "• `/summary` — ringkasan bulan ini\n"
        "• `/help` — lihat semua perintah\n\n"
        "Default timezone: *Asia/Jakarta*, mata uang: *IDR*.\n"
        "Ganti dengan `/timezone Asia/Jakarta` atau `/currency USD` kalau perlu."
    )


HELP_TEXT = (
    "📚 *Daftar Perintah*\n\n"
    "*Pemasukan & Pengeluaran*\n"
    "`/in <jumlah> [kategori] [catatan]`\n"
    "`/out <jumlah> [kategori] [catatan]`\n"
    "Contoh: `/out 35rb makan siang gojek`\n\n"
    "*Ringkasan & Riwayat*\n"
    "`/summary` — bulan ini\n"
    "`/summary 2026-04` — bulan tertentu\n"
    "`/history [n]` — n transaksi terakhir (default 10)\n"
    "`/edit <id> <field> <value>` — field: amount | note | category\n"
    "`/delete <id>` — hapus transaksi\n\n"
    "*Kategori*\n"
    "`/categories` — lihat semua kategori\n"
    "`/categories add in|out <nama>` — tambah kategori\n"
    "`/categories rename <id> <nama_baru>`\n"
    "`/categories del <id>`\n\n"
    "*Budget*\n"
    "`/budget` — lihat status bulan ini\n"
    "`/budget set <kategori> <jumlah>`\n"
    "`/budget del <kategori>`\n\n"
    "*Chart*\n"
    "`/chart` — pie chart kategori\n"
    "`/chart trend` — line chart 6 bulan\n\n"
    "*Recurring*\n"
    "`/recurring` — daftar recurring\n"
    "`/recurring add` — wizard tambah recurring\n"
    "`/recurring del <id>`\n\n"
    "*Reminder*\n"
    "`/reminder on [jam]` — reminder harian (default 20:00)\n"
    "`/reminder off`\n\n"
    "*Export / Import*\n"
    "`/export csv` atau `/export xlsx`\n"
    "Kirim file .xlsx ke chat ini buat import\n\n"
    "*Pengaturan*\n"
    "`/timezone <IANA>` — contoh: `Asia/Jakarta`, `Asia/Makassar`\n"
    "`/currency <CODE>` — contoh: `IDR`, `USD`\n"
)


def transaction_recorded(
    transaction: Transaction,
    category: Category | None,
    currency: str,
    budget_status: BudgetStatus | None,
    tz_name: str,
) -> str:
    """Confirmation message after a transaction is recorded."""
    sign = "+" if transaction.type is TransactionType.INCOME else "-"
    emoji = "💰" if transaction.type is TransactionType.INCOME else "💸"
    verb = "Pemasukan" if transaction.type is TransactionType.INCOME else "Pengeluaran"
    cat_name = category.name if category else "Tanpa kategori"
    cat_emoji = (category.emoji + " ") if (category and category.emoji) else ""

    local_dt = to_user_tz(transaction.occurred_at, tz_name)
    lines = [
        f"✅ {emoji} {verb}: {sign}{format_money(transaction.amount, currency)}",
        f"Kategori: {cat_emoji}{cat_name} • {local_dt.strftime('%d %b %Y %H:%M')}",
    ]
    if transaction.note:
        lines.append(f"Catatan: _{transaction.note}_")
    lines.append(f"ID: `#{transaction.id}`")

    if budget_status is not None:
        if budget_status.over_budget:
            over = budget_status.spent - budget_status.limit
            lines.append("")
            lines.append(
                f"⚠️ *HATI-HATI!* {budget_status.category_name} udah "
                f"{format_money(budget_status.spent, currency)} / "
                f"{format_money(budget_status.limit, currency)} "
                f"({budget_status.percent}%). Lewat {format_money(over, currency)}."
            )
        elif budget_status.percent >= 80:
            lines.append("")
            lines.append(
                f"⚠️ Budget *{budget_status.category_name}* {budget_status.percent}% terpakai "
                f"({format_money(budget_status.spent, currency)} / "
                f"{format_money(budget_status.limit, currency)})."
            )
        else:
            lines.append(
                f"_Total {budget_status.category_name} bulan ini: "
                f"{format_money(budget_status.spent, currency)} / "
                f"{format_money(budget_status.limit, currency)} "
                f"({budget_status.percent}%)_"
            )
    return "\n".join(lines)


def summary_text(summary: MonthlySummary, currency: str) -> str:
    """Pretty-printed monthly summary."""
    header = f"📊 *Ringkasan {format_month(summary.year, summary.month)}*"
    body = [
        "",
        f"💰 Total Masuk:   {format_money(Decimal(summary.total_income), currency)}",
        f"💸 Total Keluar:  {format_money(Decimal(summary.total_expense), currency)}",
        f"💵 Saldo Bulan:   {format_money(Decimal(summary.balance), currency)}",
    ]
    if summary.expense_by_category:
        body.append("")
        body.append("*Top pengeluaran:*")
        top_total = summary.total_expense
        for row in summary.expense_by_category[:5]:
            pct = percentage(row.total, top_total)
            body.append(f"• {row.category_name}: {format_money(row.total, currency)} ({pct}%)")
    if summary.income_by_category:
        body.append("")
        body.append("*Top pemasukan:*")
        top_total = summary.total_income
        for row in summary.income_by_category[:5]:
            pct = percentage(row.total, top_total)
            body.append(f"• {row.category_name}: {format_money(row.total, currency)} ({pct}%)")
    body.append("")
    body.append("Pake `/chart` buat lihat visualnya.")
    return header + "\n" + "\n".join(body)


def history_text(transactions: list[Transaction], currency: str, tz_name: str) -> str:
    """Pretty-printed recent transactions list."""
    if not transactions:
        return "Belum ada transaksi. Pake `/in` atau `/out` buat mulai catat."
    lines = ["📜 *Transaksi terakhir:*", ""]
    for transaction in transactions:
        local_dt = to_user_tz(transaction.occurred_at, tz_name)
        sign = "+" if transaction.type is TransactionType.INCOME else "-"
        cat = transaction.category.name if transaction.category else "—"
        note = f" _{transaction.note}_" if transaction.note else ""
        lines.append(
            f"`#{transaction.id:>4}` {sign}{format_money(transaction.amount, currency)} "
            f"• {cat} • {format_datetime(local_dt)}{note}"
        )
    return "\n".join(lines)


def categories_text(income: list[Category], expense: list[Category]) -> str:
    """List categories grouped by type."""

    def fmt(cats: list[Category]) -> str:
        if not cats:
            return "_(belum ada)_"
        return "\n".join(f"`#{c.id:>3}` {c.emoji or ''} {c.name}" for c in cats)

    return f"*Kategori*\n\n💰 *Pemasukan*\n{fmt(income)}\n\n💸 *Pengeluaran*\n{fmt(expense)}"


def budget_status_text(statuses: list[BudgetStatus], currency: str) -> str:
    """Pretty-printed budget status list."""
    if not statuses:
        return "Belum ada budget. Pake `/budget set <kategori> <jumlah>` buat mulai."
    lines = ["📌 *Status Budget Bulan Ini*", ""]
    for status in statuses:
        icon = "🟢"
        if status.over_budget:
            icon = "🔴"
        elif status.percent >= 80:
            icon = "🟡"
        lines.append(
            f"{icon} *{status.category_name}*: "
            f"{format_money(status.spent, currency)} / "
            f"{format_money(status.limit, currency)} ({status.percent}%)"
        )
    return "\n".join(lines)


def recurring_text(items: list[Recurring]) -> str:
    """Pretty-printed list of recurring templates."""
    if not items:
        return "Belum ada recurring. Pake `/recurring add` buat mulai."
    lines = ["🔁 *Recurring Transactions*", ""]
    for item in items:
        freq = (
            item.frequency.value
            if isinstance(item.frequency, RecurringFrequency)
            else item.frequency
        )
        when = _recurring_when(item)
        verb = "Pemasukan" if item.type is TransactionType.INCOME else "Pengeluaran"
        sign = "+" if item.type is TransactionType.INCOME else "-"
        cat = item.category.name if item.category else "—"
        note = f" — _{item.note}_" if item.note else ""
        lines.append(
            f"`#{item.id}` {verb} {sign}{format_money(Decimal(item.amount))} • {cat} • {freq} {when}{note}"
        )
    return "\n".join(lines)


def _recurring_when(item: Recurring) -> str:
    """Format the human-readable schedule for a recurring template."""
    if item.frequency is RecurringFrequency.DAILY:
        return "tiap hari"
    if item.frequency is RecurringFrequency.WEEKLY:
        idx = max(0, min(6, item.day_of_period))
        return f"tiap hari {WEEK_DAYS_ID[idx]}"
    if item.frequency is RecurringFrequency.MONTHLY:
        return f"tiap tanggal {item.day_of_period}"
    return ""


def reminder_text(currency: str) -> str:
    """The daily reminder ping."""
    _ = currency
    return (
        "🔔 Jangan lupa catat pengeluaran hari ini ya.\n"
        "Pake `/in <jumlah>` atau `/out <jumlah>`.\n"
        "Kalau gak ada, ya udah, abaikan aja pesan ini."
    )


def parse_error_message(message: str) -> str:
    """Format a friendly parse error."""
    return f"❌ {message}\n\nContoh: `/out 35000 makan siang` atau `/out 35rb makan siang`"


def deleted_message(transaction: Transaction, currency: str) -> str:
    """Confirmation after a delete."""
    sign = "+" if transaction.type is TransactionType.INCOME else "-"
    cat = transaction.category.name if transaction.category else "—"
    return (
        f"✅ #{transaction.id} dihapus ({sign}{format_money(transaction.amount, currency)} • {cat})"
    )


def updated_message(transaction: Transaction, field: str, currency: str) -> str:
    """Confirmation after an edit."""
    cat = transaction.category.name if transaction.category else "—"
    return (
        f"✅ #{transaction.id} {field} berhasil diubah.\n"
        f"Sekarang: {format_money(transaction.amount, currency)} • {cat}"
        + (f" • _{transaction.note}_" if transaction.note else "")
    )


def import_preview_text(
    created: int,
    updated: int,
    deleted: int,
    errors: list[str],
) -> str:
    """Preview of an import plan."""
    lines = ["📤 *Preview Import*", ""]
    lines.append(f"• Baris baru: *{created}*")
    lines.append(f"• Baris diubah: *{updated}*")
    lines.append(f"• Baris dihapus: *{deleted}*")
    if errors:
        lines.append("")
        lines.append("*Error:*")
        for err in errors[:10]:
            lines.append(f"• {err}")
        if len(errors) > 10:
            lines.append(f"…dan {len(errors) - 10} error lainnya")
    lines.append("")
    lines.append("Konfirmasi dengan tombol di bawah.")
    return "\n".join(lines)


def import_applied_text(created: int, updated: int, deleted: int) -> str:
    """Confirmation after an import is applied."""
    return f"✅ Import selesai.\n• {created} ditambahkan\n• {updated} diubah\n• {deleted} dihapus"


def access_denied() -> str:
    """Shown when a user is not in the allow-list."""
    return (
        "🔒 Maaf, bot ini hanya bisa dipake oleh user yang sudah didaftarkan.\n"
        "Hubungi admin bot untuk minta akses."
    )


def not_registered() -> str:
    """Shown when a user has not /start-ed yet."""
    return "Halo! Ketik /start dulu buat mulai pake bot."


def settings_changed(field: str, value: str) -> str:
    """Confirmation for /timezone or /currency."""
    return f"✅ {field} di-set ke *{value}*."


def reminder_status(enabled: bool, hour: int) -> str:
    """Status text for /reminder."""
    if enabled:
        return f"🔔 Reminder harian *aktif* setiap jam *{hour:02d}:00*."
    return "🔕 Reminder harian *nonaktif*."


def now_label(dt: datetime) -> str:
    """Human-friendly current time label."""
    return dt.strftime("%d %b %Y %H:%M")
