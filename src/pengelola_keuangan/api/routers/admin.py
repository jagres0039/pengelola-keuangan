"""Admin endpoints for manual payment verification."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from pengelola_keuangan.api.deps import CurrentAdmin, DBSession
from pengelola_keuangan.api.schemas import (
    AdminPaymentResponse,
    PaymentRejectRequest,
)
from pengelola_keuangan.db.models import Payment, PaymentStatus
from pengelola_keuangan.services import subscriptions as sub_svc

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_admin_response(payment: Payment) -> AdminPaymentResponse:
    return AdminPaymentResponse(
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
        user_id=payment.user_id,
        user_email=payment.user.email if payment.user is not None else None,
        user_first_name=payment.user.first_name if payment.user is not None else None,
    )


@router.get("/payments/pending", response_model=list[AdminPaymentResponse])
def list_pending(admin: CurrentAdmin, session: DBSession) -> list[AdminPaymentResponse]:
    """List all payments awaiting verification (oldest first)."""
    _ = admin
    payments = sub_svc.list_pending_payments(session)
    return [_to_admin_response(p) for p in payments]


@router.post("/payments/{payment_id}/approve", response_model=AdminPaymentResponse)
def approve(payment_id: int, admin: CurrentAdmin, session: DBSession) -> AdminPaymentResponse:
    """Approve a pending payment and extend user's subscription by 30 days."""
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment gak ketemu")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"payment udah {payment.status}",
        )
    sub_svc.approve_payment(session=session, payment=payment, admin=admin)
    session.flush()
    return _to_admin_response(payment)


@router.post("/payments/{payment_id}/reject", response_model=AdminPaymentResponse)
def reject(
    payment_id: int,
    payload: PaymentRejectRequest,
    admin: CurrentAdmin,
    session: DBSession,
) -> AdminPaymentResponse:
    """Reject a pending payment with a reason."""
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment gak ketemu")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"payment udah {payment.status}",
        )
    sub_svc.reject_payment(session=session, payment=payment, admin=admin, reason=payload.reason)
    session.flush()
    return _to_admin_response(payment)
