"""Inventory (stok barang) endpoints for Pengusaha mode."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select

from pengelola_keuangan.api.deps import CurrentUser, CurrentUserCanWrite, DBSession
from pengelola_keuangan.api.schemas import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementResponse,
)
from pengelola_keuangan.db.models import (
    InventoryItem,
    InventoryMovement,
    MovementReason,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _stock_and_last_cost(session: DBSession, item_id: int) -> tuple[Decimal, Decimal | None]:
    stock_q = select(func.coalesce(func.sum(InventoryMovement.qty_delta), 0)).where(
        InventoryMovement.inventory_item_id == item_id
    )
    stock = Decimal(session.execute(stock_q).scalar_one() or 0)
    cost_q = (
        select(InventoryMovement.unit_cost)
        .where(
            InventoryMovement.inventory_item_id == item_id,
            InventoryMovement.unit_cost.is_not(None),
        )
        .order_by(desc(InventoryMovement.occurred_at))
        .limit(1)
    )
    last_cost = session.execute(cost_q).scalar_one_or_none()
    return stock, last_cost


def _to_response(session: DBSession, item: InventoryItem) -> InventoryItemResponse:
    stock, last_cost = _stock_and_last_cost(session, item.id)
    return InventoryItemResponse(
        id=item.id,
        name=item.name,
        sku=item.sku,
        unit=item.unit,
        stock=stock,
        last_cost=last_cost,
        archived=item.archived_at is not None,
        created_at=item.created_at,
    )


def _movement_to_response(m: InventoryMovement) -> InventoryMovementResponse:
    return InventoryMovementResponse(
        id=m.id,
        inventory_item_id=m.inventory_item_id,
        qty_delta=m.qty_delta,
        unit_cost=m.unit_cost,
        reason=MovementReason(m.reason).value,
        note=m.note,
        occurred_at=m.occurred_at,
        created_at=m.created_at,
    )


def _get_owned(session: DBSession, user_id: int, item_id: int) -> InventoryItem:
    item = session.get(InventoryItem, item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="barang gak ketemu")
    return item


@router.get("", response_model=list[InventoryItemResponse])
def list_items(
    user: CurrentUser,
    session: DBSession,
    q: str | None = Query(default=None, max_length=128),
    include_archived: bool = False,
) -> list[InventoryItemResponse]:
    """List inventory items with computed stock + last_cost."""
    stmt = select(InventoryItem).where(InventoryItem.user_id == user.id)
    if not include_archived:
        stmt = stmt.where(InventoryItem.archived_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(InventoryItem.name.ilike(like), InventoryItem.sku.ilike(like)))
    stmt = stmt.order_by(asc(InventoryItem.name))
    rows = list(session.scalars(stmt))
    return [_to_response(session, item) for item in rows]


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: InventoryItemCreate, user: CurrentUserCanWrite, session: DBSession
) -> InventoryItemResponse:
    """Create new item; optionally seed initial stock + cost."""
    item = InventoryItem(
        user_id=user.id,
        name=payload.name.strip(),
        sku=(payload.sku or "").strip() or None,
        unit=payload.unit.strip(),
    )
    session.add(item)
    session.flush()

    if payload.initial_stock and payload.initial_stock > 0:
        movement = InventoryMovement(
            user_id=user.id,
            inventory_item_id=item.id,
            qty_delta=payload.initial_stock,
            unit_cost=payload.initial_cost,
            reason=MovementReason.INITIAL,
            note="initial stock",
            occurred_at=datetime.now(UTC),
        )
        session.add(movement)
        session.flush()

    return _to_response(session, item)


@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_item(item_id: int, user: CurrentUser, session: DBSession) -> InventoryItemResponse:
    return _to_response(session, _get_owned(session, user.id, item_id))


@router.patch("/{item_id}", response_model=InventoryItemResponse)
def update_item(
    item_id: int,
    payload: InventoryItemUpdate,
    user: CurrentUserCanWrite,
    session: DBSession,
) -> InventoryItemResponse:
    item = _get_owned(session, user.id, item_id)
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.sku is not None:
        item.sku = payload.sku.strip() or None
    if payload.unit is not None:
        item.unit = payload.unit.strip()
    session.flush()
    return _to_response(session, item)


@router.post("/{item_id}/archive", response_model=InventoryItemResponse)
def archive_item(
    item_id: int, user: CurrentUserCanWrite, session: DBSession
) -> InventoryItemResponse:
    item = _get_owned(session, user.id, item_id)
    if item.archived_at is None:
        item.archived_at = datetime.now(UTC)
        session.flush()
    return _to_response(session, item)


@router.post("/{item_id}/unarchive", response_model=InventoryItemResponse)
def unarchive_item(
    item_id: int, user: CurrentUserCanWrite, session: DBSession
) -> InventoryItemResponse:
    item = _get_owned(session, user.id, item_id)
    if item.archived_at is not None:
        item.archived_at = None
        session.flush()
    return _to_response(session, item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, user: CurrentUserCanWrite, session: DBSession) -> None:
    """Hard-delete item & all its movements. Use archive if you want history."""
    item = _get_owned(session, user.id, item_id)
    session.delete(item)
    session.flush()


# ----- movements -----


@router.get("/{item_id}/movements", response_model=list[InventoryMovementResponse])
def list_movements(
    item_id: int,
    user: CurrentUser,
    session: DBSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[InventoryMovementResponse]:
    item = _get_owned(session, user.id, item_id)
    stmt = (
        select(InventoryMovement)
        .where(InventoryMovement.inventory_item_id == item.id)
        .order_by(desc(InventoryMovement.occurred_at))
        .limit(limit)
    )
    rows = list(session.scalars(stmt))
    return [_movement_to_response(m) for m in rows]


@router.post(
    "/{item_id}/movements",
    response_model=InventoryMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_movement(
    item_id: int,
    payload: InventoryMovementCreate,
    user: CurrentUserCanWrite,
    session: DBSession,
) -> InventoryMovementResponse:
    """Record a stock movement.

    Validation: stock can't go negative after applying this movement.
    """
    item = _get_owned(session, user.id, item_id)
    if payload.qty_delta == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="qty_delta tidak boleh nol",
        )
    current, _ = _stock_and_last_cost(session, item.id)
    new_stock = current + payload.qty_delta
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"stok tidak cukup (sekarang {current}, dikurangi {-payload.qty_delta})",
        )
    movement = InventoryMovement(
        user_id=user.id,
        inventory_item_id=item.id,
        qty_delta=payload.qty_delta,
        unit_cost=payload.unit_cost,
        reason=MovementReason(payload.reason),
        note=(payload.note or "").strip() or None,
        occurred_at=payload.occurred_at or datetime.now(UTC),
    )
    session.add(movement)
    session.flush()
    return _movement_to_response(movement)


@router.delete("/{item_id}/movements/{movement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movement(
    item_id: int,
    movement_id: int,
    user: CurrentUserCanWrite,
    session: DBSession,
) -> None:
    item = _get_owned(session, user.id, item_id)
    movement = session.get(InventoryMovement, movement_id)
    if movement is None or movement.user_id != user.id or movement.inventory_item_id != item.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movement gak ketemu")
    # Deleting a stock-in movement could push stock negative — reject.
    current, _ = _stock_and_last_cost(session, item.id)
    new_stock = current - movement.qty_delta
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="hapus movement ini bikin stok jadi negatif",
        )
    session.delete(movement)
    session.flush()
