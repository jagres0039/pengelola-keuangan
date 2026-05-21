"""Multi-akun kas (accounts) + transfer endpoints.

Pengusaha-mode feature. Each account has an ``opening_balance`` and a
computed ``balance`` = opening_balance + sum(income txns) - sum(expense
txns) + transfers_in - transfers_out.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import asc, func, select

from pengelola_keuangan.api.deps import CurrentUser, CurrentUserCanWrite, DBSession
from pengelola_keuangan.api.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    TransferCreate,
    TransferResponse,
)
from pengelola_keuangan.db.models import (
    Account,
    AccountKind,
    Transaction,
    TransactionType,
    Transfer,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])
transfers_router = APIRouter(prefix="/transfers", tags=["transfers"])


def _balance_for(session: DBSession, account: Account) -> Decimal:
    """Compute current balance for an account."""
    base = account.opening_balance or Decimal("0")

    income_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.account_id == account.id,
        Transaction.type == TransactionType.INCOME,
    )
    expense_q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.account_id == account.id,
        Transaction.type == TransactionType.EXPENSE,
    )
    transfer_in_q = select(func.coalesce(func.sum(Transfer.amount), 0)).where(
        Transfer.to_account_id == account.id,
    )
    transfer_out_q = select(func.coalesce(func.sum(Transfer.amount), 0)).where(
        Transfer.from_account_id == account.id,
    )

    income = Decimal(session.execute(income_q).scalar_one() or 0)
    expense = Decimal(session.execute(expense_q).scalar_one() or 0)
    transfer_in = Decimal(session.execute(transfer_in_q).scalar_one() or 0)
    transfer_out = Decimal(session.execute(transfer_out_q).scalar_one() or 0)

    return base + income - expense + transfer_in - transfer_out


def _to_response(session: DBSession, account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        name=account.name,
        kind=AccountKind(account.kind).value,
        opening_balance=account.opening_balance,
        balance=_balance_for(session, account),
        archived=account.archived_at is not None,
        created_at=account.created_at,
    )


def _get_owned_account(session: DBSession, user_id: int, account_id: int) -> Account:
    acc = session.get(Account, account_id)
    if acc is None or acc.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="akun gak ketemu")
    return acc


@router.get("", response_model=list[AccountResponse])
def list_accounts(
    user: CurrentUser,
    session: DBSession,
    include_archived: bool = False,
) -> list[AccountResponse]:
    """List user's accounts with computed balance."""
    stmt = select(Account).where(Account.user_id == user.id)
    if not include_archived:
        stmt = stmt.where(Account.archived_at.is_(None))
    stmt = stmt.order_by(asc(Account.created_at))
    rows = list(session.scalars(stmt))
    return [_to_response(session, a) for a in rows]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate, user: CurrentUserCanWrite, session: DBSession
) -> AccountResponse:
    """Create a new account."""
    acc = Account(
        user_id=user.id,
        name=payload.name.strip(),
        kind=AccountKind(payload.kind),
        opening_balance=payload.opening_balance,
    )
    session.add(acc)
    session.flush()
    return _to_response(session, acc)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, user: CurrentUser, session: DBSession) -> AccountResponse:
    """Get one account by id."""
    return _to_response(session, _get_owned_account(session, user.id, account_id))


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    user: CurrentUserCanWrite,
    session: DBSession,
) -> AccountResponse:
    """Patch account fields."""
    acc = _get_owned_account(session, user.id, account_id)
    if payload.name is not None:
        acc.name = payload.name.strip()
    if payload.kind is not None:
        acc.kind = AccountKind(payload.kind)
    if payload.opening_balance is not None:
        acc.opening_balance = payload.opening_balance
    session.flush()
    return _to_response(session, acc)


@router.post("/{account_id}/archive", response_model=AccountResponse)
def archive_account(
    account_id: int, user: CurrentUserCanWrite, session: DBSession
) -> AccountResponse:
    """Archive an account (keeps history; can be unarchived)."""
    acc = _get_owned_account(session, user.id, account_id)
    if acc.archived_at is None:
        acc.archived_at = datetime.now(UTC)
        session.flush()
    return _to_response(session, acc)


@router.post("/{account_id}/unarchive", response_model=AccountResponse)
def unarchive_account(
    account_id: int, user: CurrentUserCanWrite, session: DBSession
) -> AccountResponse:
    """Unarchive a previously archived account."""
    acc = _get_owned_account(session, user.id, account_id)
    if acc.archived_at is not None:
        acc.archived_at = None
        session.flush()
    return _to_response(session, acc)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, user: CurrentUserCanWrite, session: DBSession) -> None:
    """Hard-delete an account.

    Rejected if there are transactions or transfers referencing it; archive
    instead.
    """
    acc = _get_owned_account(session, user.id, account_id)
    tx_count = session.execute(
        select(func.count(Transaction.id)).where(Transaction.account_id == acc.id)
    ).scalar_one()
    transfer_count = session.execute(
        select(func.count(Transfer.id)).where(
            (Transfer.from_account_id == acc.id) | (Transfer.to_account_id == acc.id)
        )
    ).scalar_one()
    if (tx_count or 0) > 0 or (transfer_count or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="akun masih punya transaksi/transfer; arsipkan saja",
        )
    session.delete(acc)
    session.flush()


# ----- transfers -----


def _transfer_to_response(transfer: Transfer) -> TransferResponse:
    return TransferResponse(
        id=transfer.id,
        from_account_id=transfer.from_account_id,
        from_account_name=transfer.from_account.name,
        to_account_id=transfer.to_account_id,
        to_account_name=transfer.to_account.name,
        amount=transfer.amount,
        note=transfer.note,
        occurred_at=transfer.occurred_at,
        created_at=transfer.created_at,
    )


@transfers_router.get("", response_model=list[TransferResponse])
def list_transfers(
    user: CurrentUser, session: DBSession, limit: int = 50
) -> list[TransferResponse]:
    """List the user's most recent transfers."""
    limit = max(1, min(limit, 200))
    stmt = (
        select(Transfer)
        .where(Transfer.user_id == user.id)
        .order_by(Transfer.occurred_at.desc())
        .limit(limit)
    )
    rows = list(session.scalars(stmt))
    return [_transfer_to_response(t) for t in rows]


@transfers_router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: TransferCreate, user: CurrentUserCanWrite, session: DBSession
) -> TransferResponse:
    """Record a transfer between two accounts owned by the same user."""
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="akun asal & tujuan harus beda",
        )
    src = _get_owned_account(session, user.id, payload.from_account_id)
    dst = _get_owned_account(session, user.id, payload.to_account_id)
    transfer = Transfer(
        user_id=user.id,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=payload.amount,
        note=(payload.note or "").strip() or None,
        occurred_at=payload.occurred_at or datetime.now(UTC),
    )
    session.add(transfer)
    session.flush()
    session.refresh(transfer)
    return _transfer_to_response(transfer)


@transfers_router.delete("/{transfer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transfer(transfer_id: int, user: CurrentUserCanWrite, session: DBSession) -> None:
    """Delete a transfer."""
    transfer = session.get(Transfer, transfer_id)
    if transfer is None or transfer.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transfer gak ketemu")
    session.delete(transfer)
    session.flush()
