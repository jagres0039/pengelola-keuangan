"""Telegram command handlers."""

from __future__ import annotations

import io
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC
from datetime import datetime as datetime_t
from decimal import Decimal
from typing import Any, cast

from sqlalchemy.orm import Session
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Message,
    Update,
)
from telegram import (
    User as TelegramUser,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from pengelola_keuangan.bot import messages
from pengelola_keuangan.config import get_settings
from pengelola_keuangan.db.models import TransactionType, User
from pengelola_keuangan.db.session import session_scope
from pengelola_keuangan.services import budgets as budgets_svc
from pengelola_keuangan.services import categories as categories_svc
from pengelola_keuangan.services import charts as charts_svc
from pengelola_keuangan.services import exporting as exporting_svc
from pengelola_keuangan.services import importing as importing_svc
from pengelola_keuangan.services import receipt_ocr as receipt_ocr_svc
from pengelola_keuangan.services import recurring as recurring_svc
from pengelola_keuangan.services import transactions as transactions_svc
from pengelola_keuangan.services import users as users_svc
from pengelola_keuangan.services.formatting import format_money, format_month
from pengelola_keuangan.services.parsing import (
    ParseError,
    guess_category_name,
    parse_amount,
)
from pengelola_keuangan.services.time_helpers import (
    current_month,
    is_valid_timezone,
    parse_year_month,
)

logger = logging.getLogger(__name__)

# Conversation state for /recurring add.
(
    RECURRING_FREQ,
    RECURRING_DAY,
    RECURRING_TYPE,
    RECURRING_AMOUNT,
    RECURRING_CATEGORY,
    RECURRING_NOTE,
) = range(6)

# Context storage keys.
PENDING_IMPORT_KEY = "pending_import"
PENDING_DELETE_KEY = "pending_delete"
PENDING_RECEIPT_KEY = "pending_receipt"


def _require_message(update: Update) -> Message:
    """Return the effective message or raise."""
    if update.effective_message is None:
        raise RuntimeError("Update has no message")
    return update.effective_message


def _require_user(update: Update) -> TelegramUser:
    """Return the effective Telegram user or raise."""
    if update.effective_user is None:
        raise RuntimeError("Update has no user")
    return update.effective_user


async def _send(message: Message, text: str, **kwargs: object) -> None:
    """Reply with HTML/Markdown disabled if formatting fails."""
    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, **kwargs)  # type: ignore[arg-type]
    except Exception:
        await message.reply_text(text, **kwargs)  # type: ignore[arg-type]


WithUser = Callable[[Update, ContextTypes.DEFAULT_TYPE, Session, User], Coroutine[Any, Any, None]]


def _with_user(
    handler: WithUser,
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """Decorator: open a session, resolve/create the user, then dispatch."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = _require_message(update)
        tg_user = _require_user(update)
        if not users_svc.is_user_allowed(tg_user.id):
            await _send(message, messages.access_denied())
            return
        with session_scope() as session:
            user, _ = users_svc.ensure_user(
                session,
                tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
            )
            await handler(update, context, session, user)

    return wrapper


# --------------------------------------------------------------------------- #
# Basic commands
# --------------------------------------------------------------------------- #


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    _ = context
    message = _require_message(update)
    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await _send(message, messages.access_denied())
        return
    with session_scope() as session:
        users_svc.ensure_user(
            session,
            tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
    await _send(message, messages.welcome(tg_user.first_name))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    _ = context
    message = _require_message(update)
    await _send(message, messages.HELP_TEXT)


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


@_with_user
async def timezone_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /timezone <name>."""
    message = _require_message(update)
    args = context.args or []
    if not args:
        await _send(
            message, f"Timezone saat ini: *{user.timezone}*. Pake `/timezone Asia/Jakarta`."
        )
        return
    tz_name = args[0].strip()
    if not is_valid_timezone(tz_name):
        await _send(message, f"❌ Timezone *{tz_name}* tidak dikenal.")
        return
    user.timezone = tz_name
    session.flush()
    await _send(message, messages.settings_changed("Timezone", tz_name))


@_with_user
async def currency_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /currency <CODE>."""
    message = _require_message(update)
    args = context.args or []
    if not args:
        await _send(message, f"Mata uang saat ini: *{user.currency}*. Pake `/currency IDR`.")
        return
    currency = args[0].strip().upper()
    if not (currency.isalpha() and len(currency) == 3):
        await _send(message, "❌ Mata uang harus 3 huruf, contoh: `IDR`, `USD`, `EUR`.")
        return
    user.currency = currency
    session.flush()
    await _send(message, messages.settings_changed("Mata uang", currency))


# --------------------------------------------------------------------------- #
# Transactions: /in and /out
# --------------------------------------------------------------------------- #


async def _record_transaction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    transaction_type: TransactionType,
) -> None:
    """Shared implementation of /in and /out."""

    async def inner(
        update_: Update,
        context_: ContextTypes.DEFAULT_TYPE,
        session: Session,
        user: User,
    ) -> None:
        message = _require_message(update_)
        args = context_.args or []
        if not args:
            verb = "Pemasukan" if transaction_type is TransactionType.INCOME else "Pengeluaran"
            await _send(
                message,
                f"❌ Format: `/{'in' if transaction_type is TransactionType.INCOME else 'out'} "
                "<jumlah> [kategori] [catatan]`\n"
                f"Contoh {verb.lower()}: `/{'in' if transaction_type is TransactionType.INCOME else 'out'} "
                "35000 makan siang`",
            )
            return
        try:
            amount = parse_amount(args[0])
        except ParseError as exc:
            await _send(message, messages.parse_error_message(str(exc)))
            return

        rest = " ".join(args[1:]).strip()
        category_name, note = _split_category_and_note(session, user.id, rest, transaction_type)

        if category_name is None:
            guessed = guess_category_name(rest)
            if guessed is not None:
                guessed_cat = categories_svc.find_category_by_name(
                    session, user.id, guessed, transaction_type
                )
                if guessed_cat is not None:
                    category_name = guessed_cat.name

        if category_name is None:
            category = categories_svc.fallback_category(session, user.id, transaction_type)
        else:
            category = categories_svc.get_or_create_category(
                session, user.id, category_name, transaction_type
            )

        transaction = transactions_svc.create_transaction(
            session,
            user_id=user.id,
            transaction_type=transaction_type,
            amount=amount,
            category_id=category.id,
            note=note or None,
            user_tz=user.timezone,
        )

        budget_status: budgets_svc.BudgetStatus | None = None
        if transaction_type is TransactionType.EXPENSE:
            budget = budgets_svc.get_budget(session, user.id, category.id)
            if budget is not None:
                spent = transactions_svc.total_for_category_this_month(
                    session, user.id, category.id, user.timezone
                )
                budget_status = budgets_svc.BudgetStatus(
                    category_id=category.id,
                    category_name=category.name,
                    limit=Decimal(budget.monthly_limit),
                    spent=spent,
                )

        await _send(
            message,
            messages.transaction_recorded(
                transaction, category, user.currency, budget_status, user.timezone
            ),
        )

    await _with_user(inner)(update, context)


def _split_category_and_note(
    session: Session,
    user_id: int,
    text: str,
    transaction_type: TransactionType,
) -> tuple[str | None, str | None]:
    """Greedily match the longest leading sequence of words as a category, the rest as note."""
    text = text.strip()
    if not text:
        return None, None
    words = text.split()
    for size in range(len(words), 0, -1):
        candidate = " ".join(words[:size])
        category = categories_svc.find_category_by_name(
            session, user_id, candidate, transaction_type
        )
        if category is not None:
            note = " ".join(words[size:]).strip() or None
            return category.name, note
    # No match: first word is treated as a new category, the rest is note.
    return words[0], " ".join(words[1:]).strip() or None


async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /in."""
    await _record_transaction(update, context, TransactionType.INCOME)


async def expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /out."""
    await _record_transaction(update, context, TransactionType.EXPENSE)


# --------------------------------------------------------------------------- #
# History / edit / delete
# --------------------------------------------------------------------------- #


@_with_user
async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /history [n]."""
    message = _require_message(update)
    args = context.args or []
    limit = 10
    if args:
        try:
            limit = max(1, min(50, int(args[0])))
        except ValueError:
            await _send(message, "❌ Format: `/history [n]` (n = 1..50)")
            return
    transactions = transactions_svc.list_recent(session, user.id, limit=limit)
    await _send(message, messages.history_text(transactions, user.currency, user.timezone))


@_with_user
async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /delete <id>."""
    message = _require_message(update)
    args = context.args or []
    if not args:
        await _send(message, "❌ Format: `/delete <id>`")
        return
    try:
        transaction_id = int(args[0].lstrip("#"))
    except ValueError:
        await _send(message, "❌ ID harus angka.")
        return
    transaction = transactions_svc.delete_transaction(session, user.id, transaction_id)
    if transaction is None:
        await _send(message, f"❌ Transaksi #{transaction_id} tidak ditemukan.")
        return
    await _send(message, messages.deleted_message(transaction, user.currency))


@_with_user
async def edit_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /edit <id> <field> <value...>."""
    message = _require_message(update)
    args = context.args or []
    if len(args) < 3:
        await _send(
            message,
            "❌ Format: `/edit <id> <field> <value>`\nField: `amount` | `note` | `category`",
        )
        return
    try:
        transaction_id = int(args[0].lstrip("#"))
    except ValueError:
        await _send(message, "❌ ID harus angka.")
        return

    field = args[1].lower().strip()
    value = " ".join(args[2:]).strip()
    transaction = transactions_svc.get_transaction(session, user.id, transaction_id)
    if transaction is None:
        await _send(message, f"❌ Transaksi #{transaction_id} tidak ditemukan.")
        return

    if field in ("amount", "jumlah"):
        try:
            amount = parse_amount(value)
        except ParseError as exc:
            await _send(message, messages.parse_error_message(str(exc)))
            return
        transactions_svc.update_transaction_fields(session, user.id, transaction_id, amount=amount)
        await _send(message, messages.updated_message(transaction, "Jumlah", user.currency))
        return

    if field in ("note", "catatan"):
        transactions_svc.update_transaction_fields(session, user.id, transaction_id, note=value)
        await _send(message, messages.updated_message(transaction, "Catatan", user.currency))
        return

    if field in ("category", "kategori"):
        category = categories_svc.get_or_create_category(session, user.id, value, transaction.type)
        transactions_svc.update_transaction_fields(
            session, user.id, transaction_id, category_id=category.id
        )
        await _send(message, messages.updated_message(transaction, "Kategori", user.currency))
        return

    await _send(message, "❌ Field tidak dikenal. Pilih: `amount`, `note`, `category`.")


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


@_with_user
async def summary_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /summary [YYYY-MM]."""
    message = _require_message(update)
    args = context.args or []
    if args:
        try:
            year, month = parse_year_month(args[0])
        except ValueError:
            await _send(message, "❌ Format bulan: `YYYY-MM`. Contoh: `/summary 2026-04`.")
            return
    else:
        year, month = current_month(user.timezone)
    summary = transactions_svc.summarize_month(session, user.id, year, month, user.timezone)
    await _send(message, messages.summary_text(summary, user.currency))


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #


@_with_user
async def categories_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /categories [add|rename|del ...]."""
    message = _require_message(update)
    args = context.args or []

    if not args:
        income = categories_svc.list_categories(session, user.id, TransactionType.INCOME)
        expense = categories_svc.list_categories(session, user.id, TransactionType.EXPENSE)
        await _send(message, messages.categories_text(income, expense))
        return

    sub = args[0].lower()
    if sub == "add":
        if len(args) < 3 or args[1].lower() not in {"in", "out"}:
            await _send(message, "❌ Format: `/categories add in|out <nama>`")
            return
        tx_type = TransactionType.INCOME if args[1].lower() == "in" else TransactionType.EXPENSE
        name = " ".join(args[2:]).strip()
        category = categories_svc.get_or_create_category(session, user.id, name, tx_type)
        await _send(message, f"✅ Kategori *{category.name}* ({tx_type.value}) siap dipake.")
        return

    if sub == "rename":
        if len(args) < 3:
            await _send(message, "❌ Format: `/categories rename <id> <nama_baru>`")
            return
        try:
            category_id = int(args[1].lstrip("#"))
        except ValueError:
            await _send(message, "❌ ID harus angka.")
            return
        new_name = " ".join(args[2:]).strip()
        renamed = categories_svc.rename_category(session, user.id, category_id, new_name)
        if renamed is None:
            await _send(message, f"❌ Kategori #{category_id} tidak ditemukan.")
            return
        await _send(message, f"✅ Kategori #{renamed.id} sekarang *{renamed.name}*.")
        return

    if sub in ("del", "delete"):
        if len(args) < 2:
            await _send(message, "❌ Format: `/categories del <id>`")
            return
        try:
            category_id = int(args[1].lstrip("#"))
        except ValueError:
            await _send(message, "❌ ID harus angka.")
            return
        ok = categories_svc.delete_category(session, user.id, category_id)
        if not ok:
            await _send(message, f"❌ Kategori #{category_id} tidak ditemukan.")
            return
        await _send(message, f"✅ Kategori #{category_id} dihapus.")
        return

    await _send(message, "❌ Subperintah tidak dikenal. Pake `add`, `rename`, atau `del`.")


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #


@_with_user
async def budget_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /budget [set|del ...]."""
    message = _require_message(update)
    args = context.args or []

    if not args:
        statuses = budgets_svc.list_budget_status(session, user.id, user.timezone)
        await _send(message, messages.budget_status_text(statuses, user.currency))
        return

    sub = args[0].lower()
    if sub == "set":
        if len(args) < 3:
            await _send(message, "❌ Format: `/budget set <kategori> <jumlah>`")
            return
        category_name = args[1]
        try:
            amount = parse_amount(args[2])
        except ParseError as exc:
            await _send(message, messages.parse_error_message(str(exc)))
            return
        category = categories_svc.get_or_create_category(
            session, user.id, category_name, TransactionType.EXPENSE
        )
        budgets_svc.set_budget(session, user.id, category.id, amount)
        await _send(
            message,
            f"✅ Budget *{category.name}* = {format_money(amount, user.currency)}/bulan.",
        )
        return

    if sub in ("del", "delete", "off"):
        if len(args) < 2:
            await _send(message, "❌ Format: `/budget del <kategori>`")
            return
        category_name = args[1]
        existing = categories_svc.find_category_by_name(
            session, user.id, category_name, TransactionType.EXPENSE
        )
        if existing is None:
            await _send(message, f"❌ Kategori *{category_name}* tidak ditemukan.")
            return
        ok = budgets_svc.delete_budget(session, user.id, existing.id)
        if not ok:
            await _send(message, f"❌ Belum ada budget untuk *{existing.name}*.")
            return
        await _send(message, f"✅ Budget *{existing.name}* dihapus.")
        return

    await _send(message, "❌ Subperintah tidak dikenal. Pake `set` atau `del`.")


# --------------------------------------------------------------------------- #
# Chart
# --------------------------------------------------------------------------- #


@_with_user
async def chart_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /chart [trend]."""
    message = _require_message(update)
    args = context.args or []
    if args and args[0].lower() == "trend":
        trend = transactions_svc.expense_trend(session, user.id, months=6, tz_name=user.timezone)
        png = charts_svc.render_trend_chart(trend)
        await message.reply_photo(
            photo=InputFile(io.BytesIO(png), filename="trend.png"),
            caption=f"Tren 6 bulan terakhir — {format_month(*current_month(user.timezone))}",
        )
        return
    year, month = current_month(user.timezone)
    summary = transactions_svc.summarize_month(session, user.id, year, month, user.timezone)
    png = charts_svc.render_category_pie(summary)
    await message.reply_photo(
        photo=InputFile(io.BytesIO(png), filename="pie.png"),
        caption=f"Pengeluaran per Kategori — {format_month(year, month)}",
    )


# --------------------------------------------------------------------------- #
# Export & Import
# --------------------------------------------------------------------------- #


@_with_user
async def export_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /export csv|xlsx [YYYY-MM]."""
    message = _require_message(update)
    args = context.args or []
    fmt = args[0].lower() if args else "xlsx"
    if fmt not in {"csv", "xlsx"}:
        await _send(message, "❌ Format: `/export csv` atau `/export xlsx`")
        return
    if len(args) > 1:
        try:
            year, month = parse_year_month(args[1])
        except ValueError:
            await _send(message, "❌ Format bulan: `YYYY-MM`.")
            return
    else:
        year, month = current_month(user.timezone)

    if fmt == "csv":
        data = exporting_svc.export_month_to_csv(session, user.id, year, month, user.timezone)
        filename = f"keuangan-{year}-{month:02d}.csv"
    else:
        data = exporting_svc.export_month_to_xlsx(
            session, user.id, year, month, user.timezone, user.currency
        )
        filename = f"keuangan-{year}-{month:02d}.xlsx"

    await message.reply_document(
        document=InputFile(io.BytesIO(data), filename=filename),
        caption=f"📎 Export {format_month(year, month)}",
    )


@_with_user
async def import_document_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle xlsx document uploads as an import."""
    message = _require_message(update)
    document = message.document
    if document is None:
        return
    filename = (document.file_name or "").lower()
    if not filename.endswith(".xlsx"):
        await _send(message, "❌ Cuma file .xlsx yang didukung untuk import.")
        return

    file = await document.get_file()
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    file_bytes = bio.getvalue()

    rows, parse_errors = importing_svc.parse_import_rows(file_bytes, user.timezone)
    if not rows and parse_errors:
        await _send(message, "❌ File tidak bisa di-parse:\n" + "\n".join(parse_errors[:5]))
        return

    months: set[tuple[int, int]] = set()
    for row in rows:
        if row.occurred_at is not None:
            months.add((row.occurred_at.year, row.occurred_at.month))
    if not months:
        months = {current_month(user.timezone)}

    existing = []
    for year, month in months:
        existing.extend(
            transactions_svc.list_for_month(session, user.id, year, month, user.timezone)
        )

    plan = importing_svc.build_import_plan(session, user.id, rows, existing)
    plan.errors.extend(parse_errors)

    context.user_data[PENDING_IMPORT_KEY] = {  # type: ignore[index]
        "file": file_bytes,
        "months": list(months),
    }

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Apply", callback_data="import:apply"),
                InlineKeyboardButton("❌ Batal", callback_data="import:cancel"),
            ]
        ]
    )
    await message.reply_text(
        messages.import_preview_text(
            len(plan.to_create), len(plan.to_update), len(plan.to_delete), plan.errors
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def import_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Apply/Cancel button on an import preview."""
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()

    pending = cast(dict[str, object] | None, context.user_data.get(PENDING_IMPORT_KEY))  # type: ignore[union-attr]
    if pending is None:
        await query.edit_message_text("⌛ Tidak ada import yang menunggu.")
        return

    if query.data == "import:cancel":
        context.user_data.pop(PENDING_IMPORT_KEY, None)  # type: ignore[union-attr]
        await query.edit_message_text("❌ Import dibatalkan.")
        return

    if query.data != "import:apply":
        return

    file_bytes = cast(bytes, pending.get("file"))
    months = cast(list[tuple[int, int]], pending.get("months", []))

    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await query.edit_message_text(messages.access_denied())
        return

    with session_scope() as session:
        user, _ = users_svc.ensure_user(
            session,
            tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        rows, parse_errors = importing_svc.parse_import_rows(file_bytes, user.timezone)
        existing = []
        for year, month in months:
            existing.extend(
                transactions_svc.list_for_month(session, user.id, year, month, user.timezone)
            )
        plan = importing_svc.build_import_plan(session, user.id, rows, existing)
        plan.errors.extend(parse_errors)
        created, updated, deleted = importing_svc.apply_import_plan(
            session, user.id, plan, user.timezone
        )
    context.user_data.pop(PENDING_IMPORT_KEY, None)  # type: ignore[union-attr]
    await query.edit_message_text(
        messages.import_applied_text(created, updated, deleted),
        parse_mode=ParseMode.MARKDOWN,
    )


# --------------------------------------------------------------------------- #
# Reminder
# --------------------------------------------------------------------------- #


@_with_user
async def reminder_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /reminder on|off [hour]."""
    _ = context
    message = _require_message(update)
    args = context.args or []
    if not args:
        await _send(message, messages.reminder_status(user.reminder_enabled, user.reminder_hour))
        return
    cmd = args[0].lower()
    if cmd == "off":
        user.reminder_enabled = False
        session.flush()
        await _send(message, messages.reminder_status(False, user.reminder_hour))
        return
    if cmd == "on":
        hour = 20
        if len(args) > 1:
            try:
                hour = max(0, min(23, int(args[1])))
            except ValueError:
                await _send(message, "❌ Format jam harus angka 0..23.")
                return
        user.reminder_enabled = True
        user.reminder_hour = hour
        session.flush()
        await _send(message, messages.reminder_status(True, hour))
        return
    await _send(message, "❌ Format: `/reminder on [jam]` atau `/reminder off`.")


# --------------------------------------------------------------------------- #
# Recurring (list + delete; add wizard lives in `bot/recurring_wizard.py`)
# --------------------------------------------------------------------------- #


@_with_user
async def recurring_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    user: User,
) -> None:
    """Handle /recurring (list) and /recurring del <id>."""
    message = _require_message(update)
    args = context.args or []
    if len(args) >= 1 and args[0].lower() in {"del", "delete"}:
        if len(args) < 2:
            await _send(message, "❌ Format: `/recurring del <id>`")
            return
        try:
            rid = int(args[1].lstrip("#"))
        except ValueError:
            await _send(message, "❌ ID harus angka.")
            return
        ok = recurring_svc.delete_recurring(session, user.id, rid)
        if not ok:
            await _send(message, f"❌ Recurring #{rid} tidak ditemukan.")
            return
        await _send(message, f"✅ Recurring #{rid} dihapus.")
        return
    items = recurring_svc.list_recurring(session, user.id)
    await _send(message, messages.recurring_text(items))


# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fallback for unrecognized commands."""
    _ = context
    message = _require_message(update)
    await _send(message, "❓ Perintah tidak dikenal. Ketik /help untuk daftar perintah.")


# --------------------------------------------------------------------------- #
# Receipt OCR (kirim foto struk -> Gemini Vision)
# --------------------------------------------------------------------------- #


async def receipt_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a photo upload as a receipt OCR request."""
    message = _require_message(update)
    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await _send(message, messages.access_denied())
        return

    settings = get_settings()
    if not settings.gemini_api_key:
        await _send(message, messages.receipt_disabled())
        return

    photos = message.photo or ()
    document = message.document
    image_bytes: bytes | None = None
    mime_type = "image/jpeg"

    if photos:
        photo = max(photos, key=lambda p: (p.width or 0) * (p.height or 0))
        file = await photo.get_file()
        bio = io.BytesIO()
        await file.download_to_memory(out=bio)
        image_bytes = bio.getvalue()
    elif document is not None and (document.mime_type or "").startswith("image/"):
        file = await document.get_file()
        bio = io.BytesIO()
        await file.download_to_memory(out=bio)
        image_bytes = bio.getvalue()
        mime_type = document.mime_type or "image/jpeg"

    if image_bytes is None:
        return

    notice = await message.reply_text(messages.receipt_scanning())

    with session_scope() as session:
        user, _ = users_svc.ensure_user(
            session,
            tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        expense_categories = categories_svc.list_categories(
            session, user.id, TransactionType.EXPENSE
        )
        category_names = [c.name for c in expense_categories]
        user_currency = user.currency
        user_tz = user.timezone

    try:
        result = receipt_ocr_svc.parse_receipt(
            image_bytes,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            mime_type=mime_type,
            category_hints=category_names,
            default_currency=user_currency,
        )
    except receipt_ocr_svc.ReceiptParseError as exc:
        logger.warning("Receipt parse failed: %s", exc)
        try:
            await notice.edit_text(messages.receipt_parse_failed(str(exc)))
        except Exception:
            await message.reply_text(messages.receipt_parse_failed(str(exc)))
        return

    if not result.is_receipt:
        try:
            await notice.edit_text(messages.receipt_not_a_receipt())
        except Exception:
            await message.reply_text(messages.receipt_not_a_receipt())
        return

    if result.total_amount <= 0:
        try:
            await notice.edit_text(
                messages.receipt_parse_failed("Total tidak terdeteksi dari struk.")
            )
        except Exception:
            await message.reply_text(
                messages.receipt_parse_failed("Total tidak terdeteksi dari struk.")
            )
        return

    # Determine which existing category matches the suggestion (case-insensitive).
    chosen_name: str | None = None
    if result.suggested_category:
        suggestion = result.suggested_category.strip().lower()
        for name in category_names:
            if name.lower() == suggestion:
                chosen_name = name
                break

    display_category = chosen_name or result.suggested_category or "Lainnya"

    pending = {
        "merchant": result.merchant,
        "amount": str(result.total_amount),
        "occurred_at": result.occurred_at.isoformat() if result.occurred_at else None,
        "category_name": chosen_name,
        "notes": result.notes,
    }
    context.user_data[PENDING_RECEIPT_KEY] = pending  # type: ignore[index]

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Simpan", callback_data="receipt:save"),
                InlineKeyboardButton("❌ Batal", callback_data="receipt:cancel"),
            ]
        ]
    )
    preview = messages.receipt_preview(
        merchant=result.merchant,
        amount=result.total_amount,
        currency=user_currency,
        occurred_at=result.occurred_at,
        category_name=display_category,
        notes=result.notes,
        tz_name=user_tz,
    )
    try:
        await notice.edit_text(preview, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except Exception:
        await message.reply_text(preview, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def receipt_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Save/Cancel buttons under a receipt preview."""
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()

    pending = cast(dict[str, object] | None, context.user_data.get(PENDING_RECEIPT_KEY))  # type: ignore[union-attr]

    if query.data == "receipt:cancel":
        context.user_data.pop(PENDING_RECEIPT_KEY, None)  # type: ignore[union-attr]
        await query.edit_message_text(messages.receipt_cancelled())
        return

    if query.data != "receipt:save":
        return

    if pending is None:
        await query.edit_message_text("⌛ Tidak ada struk yang menunggu.")
        return

    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await query.edit_message_text(messages.access_denied())
        return

    amount = Decimal(cast(str, pending["amount"]))
    occurred_at_iso = cast(str | None, pending.get("occurred_at"))
    occurred_at: datetime_t | None = None
    if occurred_at_iso:
        try:
            occurred_at = datetime_t.fromisoformat(occurred_at_iso)
        except ValueError:
            occurred_at = None

    merchant = cast(str, pending.get("merchant") or "")
    category_name = cast(str | None, pending.get("category_name"))
    notes = cast(str, pending.get("notes") or "")

    note_parts: list[str] = []
    if merchant:
        note_parts.append(merchant)
    if notes and notes.lower() != merchant.lower():
        note_parts.append(notes)
    note = " — ".join(note_parts) if note_parts else None

    with session_scope() as session:
        user, _ = users_svc.ensure_user(
            session,
            tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        if category_name:
            category = categories_svc.get_or_create_category(
                session, user.id, category_name, TransactionType.EXPENSE
            )
        else:
            category = categories_svc.fallback_category(session, user.id, TransactionType.EXPENSE)

        transaction = transactions_svc.create_transaction(
            session,
            user_id=user.id,
            transaction_type=TransactionType.EXPENSE,
            amount=amount,
            category_id=category.id,
            note=note,
            occurred_at=occurred_at,
            user_tz=user.timezone,
        )
        currency = user.currency
        msg = messages.receipt_saved(transaction, category, currency)

    context.user_data.pop(PENDING_RECEIPT_KEY, None)  # type: ignore[union-attr]
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)


# --------------------------------------------------------------------------- #
# /link — bind PWA email account to this Telegram chat
# --------------------------------------------------------------------------- #


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /link <CODE> — link this Telegram chat to a PWA email account.

    Flow:
    1. User registers on PWA (email + password) -> gets a 6-char link code
    2. User opens bot and types /link ABC123
    3. Bot validates code & expiry, then merges the two User rows:
       - Telegram user's transactions/categories/budgets/recurring move to PWA user
       - Telegram user row is deleted; PWA user gets telegram_user_id set
       - From now on, bot & PWA share the same data
    """
    from sqlalchemy import select as _select

    message = _require_message(update)
    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await _send(message, messages.access_denied())
        return

    args = context.args or []
    if not args:
        await _send(
            message,
            "🔗 *Link akun PWA*\n\n"
            "1. Login di PWA → menu *Settings* → *Hubungkan ke Telegram*\n"
            "2. Copy kode 6-huruf yang muncul\n"
            "3. Kirim ke bot: `/link KODE`\n\n"
            "Kode berlaku 15 menit.",
        )
        return

    code = args[0].strip().upper()
    if not code or len(code) > 16:
        await _send(message, "❌ Format: `/link <KODE>` (6-16 huruf).")
        return

    with session_scope() as session:
        from datetime import datetime

        pwa_user = session.scalar(_select(User).where(User.link_code == code))
        if pwa_user is None:
            await _send(message, "❌ Kode tidak valid atau sudah kadaluarsa.")
            return
        if pwa_user.link_code_expires_at is None or pwa_user.link_code_expires_at < datetime.now(
            UTC
        ):
            await _send(message, "❌ Kode sudah kadaluarsa. Generate ulang di PWA.")
            return
        if pwa_user.telegram_user_id is not None and pwa_user.telegram_user_id != tg_user.id:
            await _send(
                message,
                "❌ Akun PWA ini sudah ditautkan ke chat Telegram lain.",
            )
            return

        # Existing Telegram-only user (created previously via bot)?
        existing = session.scalar(_select(User).where(User.telegram_user_id == tg_user.id))
        if existing is not None and existing.id != pwa_user.id:
            # Merge: move all data from existing -> pwa_user.
            from pengelola_keuangan.db.models import (
                Budget as _B,
            )
            from pengelola_keuangan.db.models import (
                Category as _C,
            )
            from pengelola_keuangan.db.models import (
                Recurring as _R,
            )
            from pengelola_keuangan.db.models import (
                Transaction as _T,
            )

            # 1. Copy any non-default categories from the Telegram-only user that
            #    don't yet exist on the PWA user. Flush so we have IDs to re-point to.
            pwa_cats: dict[tuple[str, TransactionType], _C] = {
                (c.name.lower(), c.type): c
                for c in session.scalars(_select(_C).where(_C.user_id == pwa_user.id))
            }
            for cat in list(session.scalars(_select(_C).where(_C.user_id == existing.id))):
                key = (cat.name.lower(), cat.type)
                if key in pwa_cats:
                    continue
                new_cat = _C(
                    user_id=pwa_user.id,
                    name=cat.name,
                    type=cat.type,
                    emoji=cat.emoji,
                    is_default=cat.is_default,
                )
                session.add(new_cat)
                pwa_cats[key] = new_cat
            session.flush()

            # 2. Re-point transactions onto the PWA user using the now-complete category map.
            for tx in session.scalars(_select(_T).where(_T.user_id == existing.id)):
                tx.user_id = pwa_user.id
                if tx.category is not None:
                    match = pwa_cats.get((tx.category.name.lower(), tx.type))
                    if match is not None:
                        tx.category_id = match.id

            # 3. Re-point recurring templates similarly.
            for rec in session.scalars(_select(_R).where(_R.user_id == existing.id)):
                rec.user_id = pwa_user.id
                if rec.category is not None:
                    match = pwa_cats.get((rec.category.name.lower(), rec.type))
                    if match is not None:
                        rec.category_id = match.id

            # 4. Copy budgets (skip if PWA user already has one for that category-by-name).
            pwa_budget_cat_names = {
                c.name.lower()
                for c in session.scalars(
                    _select(_C).join(_B, _B.category_id == _C.id).where(_B.user_id == pwa_user.id)
                )
            }
            for budget in session.scalars(_select(_B).where(_B.user_id == existing.id)):
                cat_name = budget.category.name.lower()
                if cat_name in pwa_budget_cat_names:
                    continue
                match = pwa_cats.get((cat_name, TransactionType.EXPENSE))
                if match is None:
                    continue
                session.add(
                    _B(
                        user_id=pwa_user.id,
                        category_id=match.id,
                        monthly_limit=budget.monthly_limit,
                    )
                )

            session.flush()
            # Now delete existing telegram-only user (cascade removes leftovers)
            session.delete(existing)
            session.flush()

        pwa_user.telegram_user_id = tg_user.id
        if tg_user.username and not pwa_user.username:
            pwa_user.username = tg_user.username
        if tg_user.first_name and not pwa_user.first_name:
            pwa_user.first_name = tg_user.first_name
        pwa_user.link_code = None
        pwa_user.link_code_expires_at = None
        session.flush()
        email = pwa_user.email or "(tanpa email)"

    await _send(
        message,
        f"✅ Akun PWA *{email}* sudah ditautkan!\nSekarang data lo sama di bot & PWA.",
    )
