"""Transaction endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import (
    TransactionCreate,
    TransactionItemInput,
    TransactionItemResponse,
    TransactionResponse,
    TransactionUpdate,
)
from pengelola_keuangan.db.models import Transaction, TransactionType
from pengelola_keuangan.services import categories as cat_svc
from pengelola_keuangan.services import transactions as tx_svc

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _to_response(tx: Transaction) -> TransactionResponse:
    return TransactionResponse(
        id=tx.id,
        type=tx.type.value if hasattr(tx.type, "value") else str(tx.type),
        amount=tx.amount,
        category_id=tx.category_id,
        category_name=tx.category.name if tx.category is not None else None,
        note=tx.note,
        occurred_at=tx.occurred_at,
        items=[
            TransactionItemResponse(
                id=item.id,
                name=item.name,
                qty=item.qty,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in tx.items
        ],
    )


def _to_item_inputs(items: list[TransactionItemInput]) -> list[tx_svc.ItemInput]:
    return [
        tx_svc.ItemInput(
            name=item.name.strip(),
            qty=item.qty,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
        )
        for item in items
    ]


@router.get("", response_model=list[TransactionResponse])
def list_recent(
    user: CurrentUser,
    session: DBSession,
    limit: int = 50,
) -> list[TransactionResponse]:
    """List the user's most recent transactions."""
    limit = max(1, min(limit, 200))
    rows = tx_svc.list_recent(session, user.id, limit=limit)
    return [_to_response(r) for r in rows]


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    user: CurrentUser,
    session: DBSession,
) -> TransactionResponse:
    """Create a transaction."""
    tx_type = TransactionType(payload.type)
    cat_id = payload.category_id
    if cat_id is not None:
        cat = cat_svc.get_category_by_id(session, user.id, cat_id)
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="kategori gak ketemu",
            )
        if cat.type != tx_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="kategori beda type sama transaksi",
            )
    tx = tx_svc.create_transaction(
        session,
        user_id=user.id,
        transaction_type=tx_type,
        amount=payload.amount,
        category_id=cat_id,
        note=payload.note,
        occurred_at=payload.occurred_at,
        user_tz=user.timezone,
        items=_to_item_inputs(payload.items),
    )
    return _to_response(tx)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    user: CurrentUser,
    session: DBSession,
) -> TransactionResponse:
    """Update fields of an existing transaction."""
    tx = tx_svc.get_transaction(session, user.id, transaction_id)
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="transaksi gak ketemu",
        )
    if payload.amount is not None:
        tx.amount = payload.amount
    if payload.category_id is not None:
        cat = cat_svc.get_category_by_id(session, user.id, payload.category_id)
        if cat is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="kategori gak ketemu",
            )
        if cat.type != tx.type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="kategori beda type sama transaksi",
            )
        tx.category_id = cat.id
    if payload.note is not None:
        tx.note = payload.note.strip() or None
    if payload.occurred_at is not None:
        tx.occurred_at = payload.occurred_at
    if payload.items is not None:
        tx_svc.replace_items(session, user.id, tx.id, _to_item_inputs(payload.items))
    session.flush()
    return _to_response(tx)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    user: CurrentUser,
    session: DBSession,
) -> None:
    """Delete a transaction."""
    deleted = tx_svc.delete_transaction(session, user.id, transaction_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="transaksi gak ketemu",
        )
