"""Background scheduler for reminders and recurring transactions."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from telegram.ext import Application, ContextTypes

from pengelola_keuangan.bot import messages
from pengelola_keuangan.db.models import User
from pengelola_keuangan.db.session import session_scope
from pengelola_keuangan.services import recurring as recurring_svc
from pengelola_keuangan.services.time_helpers import now_in

logger = logging.getLogger(__name__)


async def reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send daily reminder pings to users whose local hour matches their setting."""
    pending: list[tuple[int, str]] = []
    with session_scope() as session:
        users = list(session.scalars(select(User).where(User.reminder_enabled.is_(True))))
        for user in users:
            if user.telegram_user_id is None:
                continue
            local: datetime = now_in(user.timezone or "Asia/Jakarta")
            if local.hour == user.reminder_hour and local.minute < 5:
                pending.append((user.telegram_user_id, user.currency))

    for chat_id, currency in pending:
        try:
            await context.bot.send_message(chat_id=chat_id, text=messages.reminder_text(currency))
        except Exception as exc:  # pragma: no cover - network
            logger.warning("Failed to send reminder to %s: %s", chat_id, exc)


async def recurring_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process all due recurring transactions."""
    _ = context
    with session_scope() as session:
        count = recurring_svc.run_due_recurring(session)
    if count:
        logger.info("Ran %d recurring transactions.", count)


def register_jobs(application: Application) -> None:
    """Register periodic jobs on the application's job queue."""
    job_queue = application.job_queue
    if job_queue is None:
        logger.warning("JobQueue not available; reminders & recurring jobs disabled.")
        return
    job_queue.run_repeating(reminder_job, interval=300, first=10, name="reminders")
    job_queue.run_repeating(recurring_job, interval=900, first=30, name="recurring")
