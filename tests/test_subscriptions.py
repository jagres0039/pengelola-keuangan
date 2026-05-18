"""Tests for the subscription lifecycle service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from pengelola_keuangan.db.models import PaymentStatus, User
from pengelola_keuangan.services import subscriptions as sub_svc


def _make_user(session: Session, **fields: object) -> User:
    defaults: dict[str, object] = {"email": "u@example.com", "password_hash": "x"}
    defaults.update(fields)
    user = User(**defaults)  # type: ignore[arg-type]
    session.add(user)
    session.flush()
    return user


def test_ensure_trial_sets_14_day_trial(session: Session) -> None:
    user = _make_user(session)
    now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    sub_svc.ensure_trial(user, now=now)
    assert user.trial_ends_at == now + timedelta(days=14)


def test_ensure_trial_is_idempotent(session: Session) -> None:
    existing = datetime(2026, 1, 1, tzinfo=UTC)
    user = _make_user(session, trial_ends_at=existing)
    sub_svc.ensure_trial(user)
    assert user.trial_ends_at == existing


def test_get_status_returns_trial_when_in_window(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    user = _make_user(session, trial_ends_at=now + timedelta(days=10))
    status = sub_svc.get_status(user, session, now=now)
    assert status.state == "trial"
    assert status.active is True
    assert status.can_write is True
    assert status.days_left == 10


def test_get_status_returns_expired_when_trial_passed(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    user = _make_user(session, trial_ends_at=now - timedelta(days=1))
    status = sub_svc.get_status(user, session, now=now)
    assert status.state == "expired"
    assert status.can_write is False


def test_get_status_active_when_paid(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    user = _make_user(
        session,
        trial_ends_at=now - timedelta(days=30),
        subscription_ends_at=now + timedelta(days=5),
    )
    status = sub_svc.get_status(user, session, now=now)
    assert status.state == "active"
    assert status.days_left == 5


def test_submit_payment_creates_pending(session: Session) -> None:
    user = _make_user(session)
    payment = sub_svc.submit_payment(
        session=session,
        user=user,
        amount=Decimal("5000"),
        method="bank_transfer",
        proof_note="transfer BCA",
    )
    assert payment.status == PaymentStatus.PENDING
    assert payment.amount == Decimal("5000")
    assert payment.method == "bank_transfer"
    assert payment.proof_note == "transfer BCA"


def test_submit_payment_rejects_invalid_amount(session: Session) -> None:
    user = _make_user(session)
    with pytest.raises(ValueError):
        sub_svc.submit_payment(
            session=session,
            user=user,
            amount=Decimal(0),
            method="bank_transfer",
            proof_note=None,
        )


def test_approve_payment_stacks_on_remaining_trial(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    trial_end = now + timedelta(days=2)
    user = _make_user(session, trial_ends_at=trial_end)
    admin = _make_user(session, email="admin@example.com", is_admin=True)
    payment = sub_svc.submit_payment(
        session=session, user=user, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    sub_svc.approve_payment(session=session, payment=payment, admin=admin, now=now)
    assert payment.status == PaymentStatus.APPROVED
    assert payment.period_start == trial_end
    assert user.subscription_ends_at == trial_end + timedelta(days=30)


def test_approve_payment_uses_now_when_trial_already_expired(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    user = _make_user(session, trial_ends_at=now - timedelta(days=1))
    admin = _make_user(session, email="admin@example.com", is_admin=True)
    payment = sub_svc.submit_payment(
        session=session, user=user, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    sub_svc.approve_payment(session=session, payment=payment, admin=admin, now=now)
    assert payment.period_start == now
    assert user.subscription_ends_at == now + timedelta(days=30)


def test_approve_payment_stacks_when_already_active(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    current_end = now + timedelta(days=10)
    user = _make_user(session, subscription_ends_at=current_end)
    admin = _make_user(session, email="admin@example.com", is_admin=True)
    payment = sub_svc.submit_payment(
        session=session, user=user, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    sub_svc.approve_payment(session=session, payment=payment, admin=admin, now=now)
    assert user.subscription_ends_at == current_end + timedelta(days=30)


def test_reject_payment(session: Session) -> None:
    user = _make_user(session)
    admin = _make_user(session, email="admin@example.com", is_admin=True)
    payment = sub_svc.submit_payment(
        session=session, user=user, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    sub_svc.reject_payment(
        session=session, payment=payment, admin=admin, reason="bukti tidak valid"
    )
    assert payment.status == PaymentStatus.REJECTED
    assert payment.rejection_reason == "bukti tidak valid"


def test_get_status_flags_pending_payment(session: Session) -> None:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    user = _make_user(session, trial_ends_at=now + timedelta(days=5))
    sub_svc.submit_payment(
        session=session, user=user, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    status = sub_svc.get_status(user, session, now=now)
    assert status.has_pending_payment is True


def test_list_pending_payments_oldest_first(session: Session) -> None:
    u1 = _make_user(session, email="u1@example.com")
    u2 = _make_user(session, email="u2@example.com")
    p1 = sub_svc.submit_payment(
        session=session, user=u1, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    p2 = sub_svc.submit_payment(
        session=session, user=u2, amount=Decimal("5000"), method="bank_transfer", proof_note=None
    )
    pending = sub_svc.list_pending_payments(session)
    assert [p.id for p in pending] == [p1.id, p2.id]
