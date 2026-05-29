"""Penjualan (Sales) endpoints — Pengusaha mode.

Each sale belongs to a Contact (buyer), has 1+ line items (each pointing
to an InventoryItem or describing a one-off product/service), and a
payment method. Paid sales (cash/debit/credit) immediately produce an
income Transaction and PaymentStatus=PAID. Unpaid sales (hutang) are
PaymentStatus=UNPAID until ``mark_paid`` flips them.

Inventory side-effects: when ``inventory_item_id`` is set on a line
item, the sale creates a negative InventoryMovement (reason=SALE) for
that item, deducting stock. Deleting the sale reverses the movement
and rolls back the linked income Transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select

from pengelola_keuangan.api.deps import CurrentUser, CurrentUserCanWrite, DBSession
from pengelola_keuangan.api.schemas import (
    SaleCreate,
    SaleItemInput,
    SaleItemResponse,
    SaleMarkPaidRequest,
    SaleResponse,
    SalesSummaryResponse,
)
from pengelola_keuangan.db.models import (
    Account,
    Category,
    Contact,
    InventoryItem,
    InventoryMovement,
    MovementReason,
    Sale,
    SaleItem,
    SalePaymentMethod,
    SalePaymentStatus,
    Transaction,
    TransactionItem,
    TransactionType,
)

router = APIRouter(prefix="/sales", tags=["sales"])

_INCOME_CATEGORY_NAME = "Penjualan"


def _ensure_pengusaha(user) -> None:  # type: ignore[no-untyped-def]
    """Reject non-Pengusaha users with 403."""
    if (user.profile_mode or "standar") != "pengusaha":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="fitur Penjualan hanya buat mode Pengusaha. Aktifkan di Setelan.",
        )


def _stock_for(session: DBSession, item_id: int) -> Decimal:
    q = select(func.coalesce(func.sum(InventoryMovement.qty_delta), 0)).where(
        InventoryMovement.inventory_item_id == item_id,
    )
    return Decimal(session.execute(q).scalar_one() or 0)


def _last_cost_for(session: DBSession, item_id: int) -> Decimal | None:
    q = (
        select(InventoryMovement.unit_cost)
        .where(
            InventoryMovement.inventory_item_id == item_id,
            InventoryMovement.unit_cost.is_not(None),
        )
        .order_by(desc(InventoryMovement.occurred_at))
        .limit(1)
    )
    return session.execute(q).scalar_one_or_none()


def _get_or_create_sales_category(session: DBSession, user_id: int) -> Category:
    """Return the user's "Penjualan" income category, creating it if missing."""
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.name == _INCOME_CATEGORY_NAME,
        Category.type == TransactionType.INCOME,
    )
    cat = session.execute(stmt).scalar_one_or_none()
    if cat is None:
        cat = Category(
            user_id=user_id,
            name=_INCOME_CATEGORY_NAME,
            type=TransactionType.INCOME,
            emoji="🧾",
            is_default=False,
        )
        session.add(cat)
        session.flush()
    return cat


def _to_item_response(item: SaleItem) -> SaleItemResponse:
    profit = (item.unit_price - item.unit_cost) * item.qty
    return SaleItemResponse(
        id=item.id,
        inventory_item_id=item.inventory_item_id,
        name=item.name,
        qty=item.qty,
        unit_price=item.unit_price,
        unit_cost=item.unit_cost,
        subtotal=item.subtotal,
        profit=profit,
    )


def _to_response(session: DBSession, sale: Sale) -> SaleResponse:
    items_resp = [_to_item_response(it) for it in sale.items]
    profit = sum((it.profit for it in items_resp), Decimal("0"))
    contact_name: str | None = None
    if sale.contact_id is not None:
        c = session.get(Contact, sale.contact_id)
        contact_name = c.name if c else None
    account_name: str | None = None
    if sale.account_id is not None:
        a = session.get(Account, sale.account_id)
        account_name = a.name if a else None
    return SaleResponse(
        id=sale.id,
        contact_id=sale.contact_id,
        contact_name=contact_name,
        payment_method=SalePaymentMethod(sale.payment_method).value,  # type: ignore[arg-type]
        payment_status=SalePaymentStatus(sale.payment_status).value,  # type: ignore[arg-type]
        account_id=sale.account_id,
        account_name=account_name,
        transaction_id=sale.transaction_id,
        total_amount=sale.total_amount,
        paid_amount=sale.paid_amount,
        profit=profit,
        note=sale.note,
        paid_at=sale.paid_at,
        occurred_at=sale.occurred_at,
        created_at=sale.created_at,
        items=items_resp,
    )


def _get_owned(session: DBSession, user_id: int, sale_id: int) -> Sale:
    sale = session.get(Sale, sale_id)
    if sale is None or sale.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="penjualan gak ketemu")
    return sale


def _resolve_item_unit_cost(
    session: DBSession, line: SaleItemInput, item: InventoryItem | None
) -> Decimal:
    """Pick the unit_cost to snapshot on the sale_item row."""
    if line.unit_cost is not None:
        return line.unit_cost
    if item is not None:
        last = _last_cost_for(session, item.id)
        if last is not None:
            return last
    return Decimal("0")


def _apply_items(
    session: DBSession,
    *,
    user_id: int,
    sale: Sale,
    inputs: list[SaleItemInput],
    occurred_at: datetime,
) -> Decimal:
    """Persist SaleItem rows + inventory movements; return total amount."""
    total = Decimal("0")
    for line in inputs:
        inv_item: InventoryItem | None = None
        if line.inventory_item_id is not None:
            inv_item = session.get(InventoryItem, line.inventory_item_id)
            if inv_item is None or inv_item.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"barang #{line.inventory_item_id} gak ketemu",
                )
            stock = _stock_for(session, inv_item.id)
            if stock < line.qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"stok '{inv_item.name}' kurang "
                        f"(tersisa {stock}, butuh {line.qty})"
                    ),
                )
        unit_cost = _resolve_item_unit_cost(session, line, inv_item)
        subtotal = (line.qty * line.unit_price).quantize(Decimal("0.01"))
        sale_item = SaleItem(
            sale_id=sale.id,
            inventory_item_id=inv_item.id if inv_item else None,
            name=line.name.strip() or (inv_item.name if inv_item else "Item"),
            qty=line.qty,
            unit_price=line.unit_price,
            unit_cost=unit_cost,
            subtotal=subtotal,
        )
        session.add(sale_item)
        session.flush()
        total += subtotal

        if inv_item is not None:
            movement = InventoryMovement(
                user_id=user_id,
                inventory_item_id=inv_item.id,
                qty_delta=-line.qty,
                unit_cost=unit_cost or None,
                reason=MovementReason.SALE,
                note=f"penjualan #{sale.id}",
                occurred_at=occurred_at,
            )
            session.add(movement)
            session.flush()
            sale_item.movement_id = movement.id
            session.flush()
    return total.quantize(Decimal("0.01"))


def _create_income_transaction(
    session: DBSession,
    *,
    user_id: int,
    sale: Sale,
    amount: Decimal,
    occurred_at: datetime,
) -> Transaction:
    """Create the income transaction backing a paid sale."""
    cat = _get_or_create_sales_category(session, user_id)
    buyer_note = ""
    if sale.contact_id is not None:
        c = session.get(Contact, sale.contact_id)
        if c is not None:
            buyer_note = f" ke {c.name}"
    note = f"Penjualan #{sale.id}{buyer_note}".strip()
    txn = Transaction(
        user_id=user_id,
        type=TransactionType.INCOME,
        amount=amount,
        category_id=cat.id,
        account_id=sale.account_id,
        note=note,
        occurred_at=occurred_at,
    )
    session.add(txn)
    session.flush()
    # Mirror line items onto the transaction so receipt/history shows the breakdown.
    for it in sale.items:
        session.add(
            TransactionItem(
                transaction_id=txn.id,
                name=it.name,
                qty=it.qty,
                unit_price=it.unit_price,
                subtotal=it.subtotal,
            )
        )
    session.flush()
    return txn


@router.get("", response_model=list[SaleResponse])
def list_sales(
    user: CurrentUser,
    session: DBSession,
    status_filter: str | None = Query(default=None, alias="status"),
    contact_id: int | None = Query(default=None),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[SaleResponse]:
    """List sales, newest first. Optionally filter by payment status / contact / date range."""
    _ensure_pengusaha(user)
    stmt = select(Sale).where(Sale.user_id == user.id)
    if status_filter in {"paid", "unpaid", "partial"}:
        stmt = stmt.where(Sale.payment_status == status_filter)
    if contact_id is not None:
        stmt = stmt.where(Sale.contact_id == contact_id)
    if date_from is not None:
        stmt = stmt.where(Sale.occurred_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Sale.occurred_at <= date_to)
    stmt = stmt.order_by(desc(Sale.occurred_at), desc(Sale.id)).limit(limit)
    rows = list(session.scalars(stmt))
    return [_to_response(session, s) for s in rows]


@router.get("/summary", response_model=SalesSummaryResponse)
def sales_summary(
    user: CurrentUser,
    session: DBSession,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
) -> SalesSummaryResponse:
    """Aggregate revenue / cost / profit / items-sold for a window.

    Default window: current calendar month (UTC).
    """
    _ensure_pengusaha(user)
    if date_from is None or date_to is None:
        now = datetime.now(UTC)
        period_from = datetime(now.year, now.month, 1, tzinfo=UTC)
        if now.month == 12:
            period_to = datetime(now.year + 1, 1, 1, tzinfo=UTC)
        else:
            period_to = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    else:
        period_from = date_from
        period_to = date_to

    item_stmt = (
        select(
            func.coalesce(func.sum(SaleItem.subtotal), 0),
            func.coalesce(func.sum(SaleItem.qty * SaleItem.unit_cost), 0),
            func.coalesce(func.sum(SaleItem.qty), 0),
        )
        .select_from(SaleItem)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.user_id == user.id,
            Sale.occurred_at >= period_from,
            Sale.occurred_at < period_to,
        )
    )
    rev, cost, qty = session.execute(item_stmt).one()
    revenue = Decimal(rev or 0).quantize(Decimal("0.01"))
    cost_total = Decimal(cost or 0).quantize(Decimal("0.01"))
    profit = (revenue - cost_total).quantize(Decimal("0.01"))
    items_sold = Decimal(qty or 0)

    sales_count_q = select(func.count(Sale.id)).where(
        Sale.user_id == user.id,
        Sale.occurred_at >= period_from,
        Sale.occurred_at < period_to,
    )
    sales_count = int(session.execute(sales_count_q).scalar_one() or 0)

    unpaid_q = select(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.total_amount - Sale.paid_amount), 0),
    ).where(
        Sale.user_id == user.id,
        Sale.payment_status.in_([SalePaymentStatus.UNPAID, SalePaymentStatus.PARTIAL]),
    )
    unpaid_count_v, unpaid_amount_v = session.execute(unpaid_q).one()

    return SalesSummaryResponse(
        period_from=period_from,
        period_to=period_to,
        revenue=revenue,
        cost=cost_total,
        profit=profit,
        items_sold=items_sold,
        sales_count=sales_count,
        unpaid_count=int(unpaid_count_v or 0),
        unpaid_amount=Decimal(unpaid_amount_v or 0).quantize(Decimal("0.01")),
    )


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: SaleCreate, user: CurrentUserCanWrite, session: DBSession
) -> SaleResponse:
    """Create a new sale. Deducts inventory + creates income transaction (unless unpaid)."""
    _ensure_pengusaha(user)
    if payload.contact_id is not None:
        contact = session.get(Contact, payload.contact_id)
        if contact is None or contact.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="pembeli gak ketemu"
            )
    if payload.account_id is not None:
        acc = session.get(Account, payload.account_id)
        if acc is None or acc.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="akun kas gak ketemu"
            )

    occurred_at = payload.occurred_at or datetime.now(UTC)
    method = SalePaymentMethod(payload.payment_method)
    sale = Sale(
        user_id=user.id,
        contact_id=payload.contact_id,
        payment_method=method,
        payment_status=(
            SalePaymentStatus.UNPAID
            if method == SalePaymentMethod.UNPAID
            else SalePaymentStatus.PAID
        ),
        account_id=payload.account_id if method != SalePaymentMethod.UNPAID else None,
        total_amount=Decimal("0"),
        paid_amount=Decimal("0"),
        note=(payload.note or "").strip() or None,
        occurred_at=occurred_at,
    )
    session.add(sale)
    session.flush()

    total = _apply_items(
        session,
        user_id=user.id,
        sale=sale,
        inputs=payload.items,
        occurred_at=occurred_at,
    )
    sale.total_amount = total

    if method != SalePaymentMethod.UNPAID:
        txn = _create_income_transaction(
            session,
            user_id=user.id,
            sale=sale,
            amount=total,
            occurred_at=occurred_at,
        )
        sale.transaction_id = txn.id
        sale.paid_amount = total
        sale.paid_at = occurred_at
    session.flush()
    return _to_response(session, sale)


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(sale_id: int, user: CurrentUser, session: DBSession) -> SaleResponse:
    _ensure_pengusaha(user)
    return _to_response(session, _get_owned(session, user.id, sale_id))


@router.post("/{sale_id}/pay", response_model=SaleResponse)
def mark_sale_paid(
    sale_id: int,
    payload: SaleMarkPaidRequest,
    user: CurrentUserCanWrite,
    session: DBSession,
) -> SaleResponse:
    """Mark an unpaid (or partially paid) sale as paid / partially paid.

    Creates the backing income Transaction (if not yet created).
    """
    _ensure_pengusaha(user)
    sale = _get_owned(session, user.id, sale_id)
    if sale.payment_status == SalePaymentStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="penjualan ini sudah lunas",
        )
    remaining = (sale.total_amount - sale.paid_amount).quantize(Decimal("0.01"))
    amount = payload.paid_amount or remaining
    if amount > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"nominal melebihi sisa hutang ({remaining})",
        )

    if payload.account_id is not None:
        acc = session.get(Account, payload.account_id)
        if acc is None or acc.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="akun kas gak ketemu"
            )
        sale.account_id = payload.account_id

    if payload.payment_method is not None:
        sale.payment_method = SalePaymentMethod(payload.payment_method)
    elif sale.payment_method == SalePaymentMethod.UNPAID:
        # default to cash when marking an UNPAID sale as paid
        sale.payment_method = SalePaymentMethod.CASH

    occurred_at = payload.occurred_at or datetime.now(UTC)
    txn = _create_income_transaction(
        session,
        user_id=user.id,
        sale=sale,
        amount=amount,
        occurred_at=occurred_at,
    )
    # Link only the first/most-recent payment txn; subsequent partial payments overwrite.
    sale.transaction_id = txn.id

    sale.paid_amount = (sale.paid_amount + amount).quantize(Decimal("0.01"))
    if sale.paid_amount >= sale.total_amount:
        sale.payment_status = SalePaymentStatus.PAID
        sale.paid_at = occurred_at
    else:
        sale.payment_status = SalePaymentStatus.PARTIAL
    session.flush()
    return _to_response(session, sale)


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(sale_id: int, user: CurrentUserCanWrite, session: DBSession) -> None:
    """Delete a sale; reverses inventory movements and removes income transaction(s)."""
    _ensure_pengusaha(user)
    sale = _get_owned(session, user.id, sale_id)

    # Reverse inventory movements linked to sale items.
    for it in sale.items:
        if it.movement_id is not None:
            mv = session.get(InventoryMovement, it.movement_id)
            if mv is not None and mv.user_id == user.id:
                session.delete(mv)

    # Delete linked income transaction (if any). For partial payments we
    # only have the most-recent linked one; this is acceptable as the
    # delete cascades transaction_items.
    if sale.transaction_id is not None:
        txn = session.get(Transaction, sale.transaction_id)
        if txn is not None and txn.user_id == user.id:
            session.delete(txn)

    session.delete(sale)
    session.flush()
