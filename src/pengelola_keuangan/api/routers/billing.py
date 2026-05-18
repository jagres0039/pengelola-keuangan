"""Billing endpoints: subscription status, payment submission, payment history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import (
    PaymentResponse,
    PaymentSubmitRequest,
    SubscriptionStatusResponse,
)
from pengelola_keuangan.config import get_settings
from pengelola_keuangan.db.models import Payment, PaymentStatus
from pengelola_keuangan.services import subscriptions as sub_svc

router = APIRouter(prefix="/billing", tags=["billing"])


def _payment_to_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        amount=payment.amount,
        method=payment.method,
        proof_note=payment.proof_note,
        status=(payment.status.value if hasattr(payment.status, "value") else str(payment.status)),
        period_start=payment.period_start,
        period_end=payment.period_end,
        decided_at=payment.decided_at,
        rejection_reason=payment.rejection_reason,
        created_at=payment.created_at,
    )


@router.get("/status", response_model=SubscriptionStatusResponse)
def get_subscription_status(user: CurrentUser, session: DBSession) -> SubscriptionStatusResponse:
    """Return current trial/paid status + price + payment instructions."""
    sub = sub_svc.get_status(user, session)
    settings = get_settings()
    return SubscriptionStatusResponse(
        state=sub.state,
        active=sub.active,
        can_write=sub.can_write,
        expires_at=sub.expires_at,
        days_left=sub.days_left,
        has_pending_payment=sub.has_pending_payment,
        monthly_price=sub_svc.MONTHLY_PRICE_IDR,
        currency=user.currency or "IDR",
        billing_instructions=settings.billing_instructions,
    )


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def submit_payment(
    payload: PaymentSubmitRequest, user: CurrentUser, session: DBSession
) -> PaymentResponse:
    """Submit a manual payment claim awaiting admin verification."""
    pending = session.scalar(
        select(Payment).where(Payment.user_id == user.id, Payment.status == PaymentStatus.PENDING)
    )
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="udah ada pembayaran pending; tunggu admin verifikasi dulu",
        )
    try:
        payment = sub_svc.submit_payment(
            session=session,
            user=user,
            amount=payload.amount,
            method=payload.method,
            proof_note=payload.proof_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _payment_to_response(payment)


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(user: CurrentUser, session: DBSession) -> list[PaymentResponse]:
    """List the authenticated user's recent payments."""
    payments = sub_svc.list_user_payments(session, user)
    return [_payment_to_response(p) for p in payments]
