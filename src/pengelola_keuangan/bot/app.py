"""Build and run the Telegram bot application."""

from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from pengelola_keuangan.bot import handlers
from pengelola_keuangan.bot.recurring_wizard import build_recurring_conversation
from pengelola_keuangan.bot.scheduler import register_jobs
from pengelola_keuangan.config import get_settings
from pengelola_keuangan.db.models import Base
from pengelola_keuangan.db.session import get_engine

logger = logging.getLogger(__name__)


PUBLIC_COMMANDS: list[tuple[str, str]] = [
    ("start", "Mulai pake bot"),
    ("help", "Daftar semua perintah"),
    ("in", "Catat pemasukan"),
    ("out", "Catat pengeluaran"),
    ("summary", "Ringkasan bulan ini"),
    ("history", "Riwayat transaksi terakhir"),
    ("edit", "Edit transaksi"),
    ("delete", "Hapus transaksi"),
    ("categories", "Kelola kategori"),
    ("budget", "Kelola budget per kategori"),
    ("chart", "Chart kategori / trend"),
    ("recurring", "Lihat recurring"),
    ("recurring_add", "Tambah recurring (wizard)"),
    ("reminder", "Atur reminder harian"),
    ("export", "Export CSV / Excel"),
    ("timezone", "Set zona waktu"),
    ("currency", "Set mata uang"),
]


async def _set_commands(application: Application) -> None:
    """Register the visible /command list with Telegram."""
    commands = [BotCommand(name, desc) for name, desc in PUBLIC_COMMANDS]
    await application.bot.set_my_commands(commands)


def _setup_logging() -> None:
    """Configure root logging based on settings."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _create_schema_if_needed() -> None:
    """Create all tables in dev mode (used when not running Alembic migrations)."""
    Base.metadata.create_all(get_engine())


def build_application() -> Application:
    """Build the Telegram Application with all handlers registered."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN belum di-set. Isi di .env atau export sebagai env var."
        )

    application = (
        ApplicationBuilder().token(settings.telegram_bot_token).post_init(_set_commands).build()
    )

    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("timezone", handlers.timezone_command))
    application.add_handler(CommandHandler("currency", handlers.currency_command))

    application.add_handler(CommandHandler("in", handlers.income_command))
    application.add_handler(CommandHandler("out", handlers.expense_command))

    application.add_handler(CommandHandler("history", handlers.history_command))
    application.add_handler(CommandHandler("edit", handlers.edit_command))
    application.add_handler(CommandHandler("delete", handlers.delete_command))

    application.add_handler(CommandHandler("summary", handlers.summary_command))
    application.add_handler(CommandHandler("categories", handlers.categories_command))
    application.add_handler(CommandHandler("budget", handlers.budget_command))
    application.add_handler(CommandHandler("chart", handlers.chart_command))

    application.add_handler(CommandHandler("recurring", handlers.recurring_list_command))
    application.add_handler(build_recurring_conversation())

    application.add_handler(CommandHandler("reminder", handlers.reminder_command))
    application.add_handler(CommandHandler("export", handlers.export_command))

    application.add_handler(
        MessageHandler(filters.Document.FileExtension("xlsx"), handlers.import_document_handler)
    )
    application.add_handler(
        CallbackQueryHandler(handlers.import_callback_handler, pattern=r"^import:")
    )

    application.add_handler(MessageHandler(filters.COMMAND, handlers.unknown_command))

    register_jobs(application)
    return application


def run() -> None:
    """Initialize and run the bot until interrupted."""
    _setup_logging()
    _create_schema_if_needed()
    application = build_application()
    logger.info("Starting bot…")
    application.run_polling(allowed_updates=["message", "callback_query"])
