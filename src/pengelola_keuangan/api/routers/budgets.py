"""Budget endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import BudgetCreate, BudgetResponse
from pengelola_keuangan.db.models import TransactionType
from pengelola_keuangan.services import budgets as budget_svc
from pengelola_keuangan.services import categories as cat_svc

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetResponse])
def list_budgets(user: CurrentUser, session: DBSession) -> list[BudgetResponse]:
    """List budget vs actual for the current month."""
    statuses = budget_svc.list_budget_status(session, user.id, user.timezone or "Asia/Jakarta")
    return [
        BudgetResponse(
            id=s.category_id,
            category_id=s.category_id,
            category_name=s.category_name,
            monthly_limit=s.limit,
            spent=s.spent,
            remaining=s.remaining,
        )
        for s in statuses
    ]


@router.put("", response_model=BudgetResponse)
def upsert_budget(
    payload: BudgetCreate,
    user: CurrentUser,
    session: DBSession,
) -> BudgetResponse:
    """Create or update a monthly budget for a category."""
    cat = cat_svc.get_category_by_id(session, user.id, payload.category_id)
    if cat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="kategori gak ketemu",
        )
    if cat.type != TransactionType.EXPENSE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="budget hanya untuk kategori pengeluaran",
        )
    budget_svc.set_budget(session, user.id, payload.category_id, payload.monthly_limit)
    spent = budget_svc.list_budget_status(session, user.id, user.timezone or "Asia/Jakarta")
    target = next((s for s in spent if s.category_id == payload.category_id), None)
    if target is None:
        return BudgetResponse(
            id=payload.category_id,
            category_id=payload.category_id,
            category_name=cat.name,
            monthly_limit=payload.monthly_limit,
            spent=cat.transactions[0].amount if cat.transactions else 0,  # type: ignore[arg-type]
            remaining=payload.monthly_limit,
        )
    return BudgetResponse(
        id=target.category_id,
        category_id=target.category_id,
        category_name=target.category_name,
        monthly_limit=target.limit,
        spent=target.spent,
        remaining=target.remaining,
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(category_id: int, user: CurrentUser, session: DBSession) -> None:
    """Delete a budget."""
    ok = budget_svc.delete_budget(session, user.id, category_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="budget gak ketemu",
        )
