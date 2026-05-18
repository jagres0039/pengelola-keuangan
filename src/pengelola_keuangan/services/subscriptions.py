"""Subscription / billing service: trial + monthly paid plan with manual transfer verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import Payment, PaymentStatus, User

TRIAL_DAYS = 14
SUBSCRIPTION_DAYS = 30
MONTHLY_PRICE_IDR = Decimal("5000")


@dataclass(frozen=True)
class SubscriptionStatus:
    """Current subscription state for a user, computed from trial/paid timestamps."""

    state: str
    active: bool
    can_write: bool
    expires_at: datetime | None
    days_left: int
    has_pending_payment: bool

    @property
    def is_trial(self) -> bool:
        return self.state == "trial"

    @property
    def is_paid(self) -> bool:
        return self.state == "active"

    @property
    def is_expired(self) -> bool:
        return self.state == "expired"


def ensure_trial(user: User, *, now: datetime | None = None) -> None:
    """Initialize `trial_ends_at` for a brand-new user (idempotent)."""
    if user.trial_ends_at is not None or user.subscription_ends_at is not None:
        return
    moment = now if now is not None else datetime.now(UTC)
    user.trial_ends_at = moment + timedelta(days=TRIAL_DAYS)


def _aware(dt: datetime | None) -> datetime | None:
    """Force a datetime to be UTC-aware (SQLite returns naive timestamps)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def get_status(user: User, session: Session, *, now: datetime | None = None) -> SubscriptionStatus:
    """Compute current subscription state from user's trial/paid timestamps."""
    moment = now if now is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)

    paid_until = _aware(user.subscription_ends_at)
    if paid_until is not None and paid_until > moment:
        delta = paid_until - moment
        return SubscriptionStatus(
            state="active",
            active=True,
            can_write=True,
            expires_at=paid_until,
            days_left=max(0, delta.days),
            has_pending_payment=_has_pending_payment(user, session),
        )

    trial_until = _aware(user.trial_ends_at)
    if trial_until is not None and trial_until > moment:
        delta = trial_until - moment
        return SubscriptionStatus(
            state="trial",
            active=True,
            can_write=True,
            expires_at=trial_until,
            days_left=max(0, delta.days),
            has_pending_payment=_has_pending_payment(user, session),
        )

    expires_at = paid_until or trial_until
    return SubscriptionStatus(
        state="expired",
        active=False,
        can_write=False,
        expires_at=expires_at,
        days_left=0,
        has_pending_payment=_has_pending_payment(user, session),
    )


def _has_pending_payment(user: User, session: Session) -> bool:
    stmt = select(Payment.id).where(
        Payment.user_id == user.id,
        Payment.status == PaymentStatus.PENDING,
    )
    return session.execute(stmt).first() is not None


def submit_payment(
    *,
    session: Session,
    user: User,
    amount: Decimal,
    method: str,
    proof_note: str | None,
) -> Payment:
    """Create a new pending payment claim awaiting admin verification."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    method_clean = method.strip().lower()
    if not method_clean:
        raise ValueError("method is required")
    payment = Payment(
        user_id=user.id,
        amount=amount,
        method=method_clean[:32],
        proof_note=(proof_note or "").strip()[:500] or None,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    session.flush()
    return payment


def approve_payment(
    *,
    session: Session,
    payment: Payment,
    admin: User,
    now: datetime | None = None,
) -> Payment:
    """Approve a pending payment and extend the user's subscription by SUBSCRIPTION_DAYS."""
    if payment.status != PaymentStatus.PENDING:
        raise ValueError(f"payment is already {payment.status}")

    moment = now if now is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    target_user = payment.user
    current_end = _aware(target_user.subscription_ends_at)
    period_start = current_end if current_end is not None and current_end > moment else moment
    period_end = period_start + timedelta(days=SUBSCRIPTION_DAYS)

    payment.status = PaymentStatus.APPROVED
    payment.period_start = period_start
    payment.period_end = period_end
    payment.decided_at = moment
    payment.decided_by_user_id = admin.id
    target_user.subscription_ends_at = period_end
    session.flush()
    return payment


def reject_payment(
    *,
    session: Session,
    payment: Payment,
    admin: User,
    reason: str,
    now: datetime | None = None,
) -> Payment:
    """Reject a pending payment with a human-readable reason."""
    if payment.status != PaymentStatus.PENDING:
        raise ValueError(f"payment is already {payment.status}")
    payment.status = PaymentStatus.REJECTED
    payment.rejection_reason = reason.strip()[:255] or "ditolak"
    payment.decided_at = now if now is not None else datetime.now(UTC)
    payment.decided_by_user_id = admin.id
    session.flush()
    return payment


def list_pending_payments(session: Session) -> list[Payment]:
    """All pending payments, oldest first (admin view)."""
    stmt = (
        select(Payment).where(Payment.status == PaymentStatus.PENDING).order_by(Payment.created_at)
    )
    return list(session.execute(stmt).scalars().all())


def list_user_payments(session: Session, user: User, *, limit: int = 20) -> list[Payment]:
    """Recent payments for a single user."""
    stmt = (
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
