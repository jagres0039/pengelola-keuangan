"""Monthly summary endpoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import (
    CategoryTotalResponse,
    LowBalanceStatus,
    MonthlySummaryResponse,
)
from pengelola_keuangan.services import transactions as tx_svc
from pengelola_keuangan.services.time_helpers import current_month

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/low-balance", response_model=LowBalanceStatus)
def get_low_balance(
    user: CurrentUser,
    session: DBSession,
) -> LowBalanceStatus:
    """Return whether the current month's balance is below the user's threshold."""
    tz = user.timezone or "Asia/Jakarta"
    y, m = current_month(tz)
    summary = tx_svc.summarize_month(session, user.id, y, m, tz)
    balance = summary.balance
    threshold = user.low_balance_threshold
    is_low = balance < threshold
    return LowBalanceStatus(
        is_low=is_low,
        balance=balance,
        threshold=threshold,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
    )


@router.get("", response_model=MonthlySummaryResponse)
def get_summary(
    user: CurrentUser,
    session: DBSession,
    year: int | None = None,
    month: int | None = None,
) -> MonthlySummaryResponse:
    """Return monthly summary for the current month (or specified year+month)."""
    tz = user.timezone or "Asia/Jakarta"
    if year is None or month is None:
        y, m = current_month(tz)
    else:
        try:
            datetime(year, month, 1)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"year/month invalid: {exc}",
            ) from exc
        y, m = year, month

    summary = tx_svc.summarize_month(session, user.id, y, m, tz)
    return MonthlySummaryResponse(
        year=summary.year,
        month=summary.month,
        total_income=summary.total_income,
        total_expense=summary.total_expense,
        balance=summary.balance,
        income_by_category=[
            CategoryTotalResponse(
                category_id=ct.category_id,
                category_name=ct.category_name,
                total=ct.total,
            )
            for ct in summary.income_by_category
        ],
        expense_by_category=[
            CategoryTotalResponse(
                category_id=ct.category_id,
                category_name=ct.category_name,
                total=ct.total,
            )
            for ct in summary.expense_by_category
        ],
    )
