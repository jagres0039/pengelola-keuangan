"""Category endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from pengelola_keuangan.db.models import TransactionType
from pengelola_keuangan.services import categories as cat_svc

router = APIRouter(prefix="/categories", tags=["categories"])


def _to_response(category: object) -> CategoryResponse:
    return CategoryResponse.model_validate(category)


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    user: CurrentUser,
    session: DBSession,
    type: str | None = None,
) -> list[CategoryResponse]:
    """List user's categories, optionally filtered by type (in/out)."""
    tx_type: TransactionType | None = None
    if type is not None:
        if type not in ("in", "out"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="type harus 'in' atau 'out'",
            )
        tx_type = TransactionType(type)
    rows = cat_svc.list_categories(session, user.id, tx_type)
    return [_to_response(row) for row in rows]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    user: CurrentUser,
    session: DBSession,
) -> CategoryResponse:
    """Create (or get) a category."""
    cat = cat_svc.get_or_create_category(
        session,
        user.id,
        payload.name.strip(),
        TransactionType(payload.type),
        emoji=payload.emoji,
    )
    return _to_response(cat)


@router.patch("/{category_id}", response_model=CategoryResponse)
def rename_category(
    category_id: int,
    payload: CategoryUpdate,
    user: CurrentUser,
    session: DBSession,
) -> CategoryResponse:
    """Rename a category."""
    cat = cat_svc.rename_category(session, user.id, category_id, payload.name.strip())
    if cat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="kategori gak ketemu",
        )
    return _to_response(cat)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, user: CurrentUser, session: DBSession) -> None:
    """Delete a category."""
    ok = cat_svc.delete_category(session, user.id, category_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="kategori gak ketemu",
        )
