"""Conversation handler for ``/recurring add``."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from pengelola_keuangan.bot.handlers import _require_message, _require_user, _send
from pengelola_keuangan.db.models import Recurring, RecurringFrequency, TransactionType
from pengelola_keuangan.db.session import session_scope
from pengelola_keuangan.services import categories as categories_svc
from pengelola_keuangan.services import users as users_svc
from pengelola_keuangan.services.formatting import format_money
from pengelola_keuangan.services.parsing import ParseError, parse_amount

FREQ, DAY, TYPE, AMOUNT, CATEGORY, NOTE = range(6)

DATA_KEY = "recurring_draft"
WEEKDAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _draft(context: ContextTypes.DEFAULT_TYPE) -> dict[str, object]:
    """Get or create the draft dict in user_data."""
    data = context.user_data
    if data is None:
        raise RuntimeError("user_data unavailable")
    draft = cast(dict[str, object] | None, data.get(DATA_KEY))
    if draft is None:
        draft = {}
        data[DATA_KEY] = draft
    return draft


def _clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear any draft state."""
    if context.user_data is not None:
        context.user_data.pop(DATA_KEY, None)


async def start_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: pick frequency."""
    message = _require_message(update)
    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await _send(message, "🔒 Akses ditolak.")
        return ConversationHandler.END
    _clear(context)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Tiap hari", callback_data="freq:daily"),
                InlineKeyboardButton("Tiap minggu", callback_data="freq:weekly"),
                InlineKeyboardButton("Tiap bulan", callback_data="freq:monthly"),
            ],
            [InlineKeyboardButton("❌ Batal", callback_data="cancel")],
        ]
    )
    await message.reply_text("🔁 Tiap berapa lama?", reply_markup=keyboard)
    return FREQ


async def on_freq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle frequency selection."""
    query = update.callback_query
    if query is None or query.data is None:
        return FREQ
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Dibatalkan.")
        _clear(context)
        return ConversationHandler.END

    _, freq = query.data.split(":")
    draft = _draft(context)
    draft["frequency"] = freq

    if freq == "daily":
        draft["day_of_period"] = 0
        return await _ask_type(query, context)

    if freq == "weekly":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(name, callback_data=f"day:{i}")
                    for i, name in enumerate(WEEKDAYS[:4])
                ],
                [
                    InlineKeyboardButton(name, callback_data=f"day:{i + 4}")
                    for i, name in enumerate(WEEKDAYS[4:])
                ],
                [InlineKeyboardButton("❌ Batal", callback_data="cancel")],
            ]
        )
        await query.edit_message_text("Hari apa?", reply_markup=keyboard)
        return DAY

    if freq == "monthly":
        await query.edit_message_text("Tanggal berapa tiap bulannya? (1-31)\nKetik angka langsung.")
        return DAY

    return FREQ


async def on_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle day-of-period (weekday button or month-day text)."""
    draft = _draft(context)

    if update.callback_query is not None:
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("❌ Dibatalkan.")
            _clear(context)
            return ConversationHandler.END
        if query.data is None or not query.data.startswith("day:"):
            return DAY
        _, raw = query.data.split(":")
        draft["day_of_period"] = int(raw)
        return await _ask_type(query, context)

    message = _require_message(update)
    text = (message.text or "").strip()
    try:
        day = int(text)
    except ValueError:
        await _send(message, "❌ Ketik angka tanggal (1-31).")
        return DAY
    if day < 1 or day > 31:
        await _send(message, "❌ Tanggal harus 1-31.")
        return DAY
    draft["day_of_period"] = day
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💰 Pemasukan", callback_data="type:in"),
                InlineKeyboardButton("💸 Pengeluaran", callback_data="type:out"),
            ],
            [InlineKeyboardButton("❌ Batal", callback_data="cancel")],
        ]
    )
    await message.reply_text("Jenis transaksi?", reply_markup=keyboard)
    return TYPE


async def _ask_type(query: object, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for transaction type."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💰 Pemasukan", callback_data="type:in"),
                InlineKeyboardButton("💸 Pengeluaran", callback_data="type:out"),
            ],
            [InlineKeyboardButton("❌ Batal", callback_data="cancel")],
        ]
    )
    await query.edit_message_text("Jenis transaksi?", reply_markup=keyboard)  # type: ignore[attr-defined]
    _ = context
    return TYPE


async def on_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle transaction type selection."""
    query = update.callback_query
    if query is None or query.data is None:
        return TYPE
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text("❌ Dibatalkan.")
        _clear(context)
        return ConversationHandler.END
    _, raw = query.data.split(":")
    draft = _draft(context)
    draft["type"] = raw
    await query.edit_message_text("Jumlah? (ketik angka, contoh: 500000 atau 1.5jt)")
    return AMOUNT


async def on_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle amount input."""
    message = _require_message(update)
    text = (message.text or "").strip()
    try:
        amount = parse_amount(text)
    except ParseError as exc:
        await _send(message, f"❌ {exc}\nKetik ulang jumlahnya.")
        return AMOUNT
    draft = _draft(context)
    draft["amount"] = str(amount)
    await message.reply_text("Kategori? (ketik nama kategori)")
    return CATEGORY


async def on_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category input."""
    message = _require_message(update)
    text = (message.text or "").strip()
    if not text:
        await _send(message, "❌ Kategori tidak boleh kosong.")
        return CATEGORY
    draft = _draft(context)
    draft["category"] = text
    await message.reply_text("Catatan (opsional, ketik `-` kalau gak ada):")
    return NOTE


async def on_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle note input, save the recurring template, finish."""
    message = _require_message(update)
    text = (message.text or "").strip()
    if text == "-" or text.lower() in {"tidak ada", "skip", "no"}:
        text = ""
    draft = _draft(context)

    tg_user = _require_user(update)
    if not users_svc.is_user_allowed(tg_user.id):
        await _send(message, "🔒 Akses ditolak.")
        _clear(context)
        return ConversationHandler.END

    with session_scope() as session:
        user, _ = users_svc.ensure_user(
            session,
            tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )
        tx_type = TransactionType(cast(str, draft["type"]))
        category = categories_svc.get_or_create_category(
            session, user.id, cast(str, draft["category"]), tx_type
        )
        recurring = Recurring(
            user_id=user.id,
            type=tx_type,
            amount=Decimal(cast(str, draft["amount"])),
            category_id=category.id,
            note=text or None,
            frequency=RecurringFrequency(cast(str, draft["frequency"])),
            day_of_period=int(cast(int, draft.get("day_of_period", 1))),
            active=True,
        )
        session.add(recurring)
        session.flush()
        rid = recurring.id
        currency = user.currency
        freq_label = _freq_label(recurring)
        cat_name = category.name
        amount_label = format_money(recurring.amount, currency)

    _clear(context)
    sign = "+" if tx_type is TransactionType.INCOME else "-"
    await message.reply_text(
        f"✅ Recurring #{rid} di-setup: {freq_label}, otomatis catat "
        f"{sign}{amount_label} ({cat_name})" + (f" — _{text}_" if text else ""),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


def _freq_label(recurring: Recurring) -> str:
    """Human-friendly label of a recurring template's schedule."""
    if recurring.frequency is RecurringFrequency.DAILY:
        return "tiap hari"
    if recurring.frequency is RecurringFrequency.WEEKLY:
        return f"tiap hari {WEEKDAYS[recurring.day_of_period]}"
    return f"tiap tanggal {recurring.day_of_period}"


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel an in-progress wizard."""
    message = _require_message(update)
    _clear(context)
    await _send(message, "❌ Dibatalkan.")
    return ConversationHandler.END


def build_recurring_conversation() -> ConversationHandler[ContextTypes.DEFAULT_TYPE]:
    """Return the ConversationHandler for the /recurring add wizard."""
    return ConversationHandler(
        entry_points=[CommandHandler("recurring_add", start_wizard)],
        states={
            FREQ: [CallbackQueryHandler(on_freq)],
            DAY: [
                CallbackQueryHandler(on_day),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_day),
            ],
            TYPE: [CallbackQueryHandler(on_type)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_category)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_note)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        allow_reentry=True,
    )
