"""Direktori (customer / supplier) endpoints.

Pengusaha-mode feature. Endpoints are reachable by any authenticated user
(profile_mode is enforced on the UI layer to keep the API simple and to
allow Standar users to view legacy data if they ever switch modes), but
the directory only makes sense alongside the Pengusaha features.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import asc, select

from pengelola_keuangan.api.deps import CurrentUser, CurrentUserCanWrite, DBSession
from pengelola_keuangan.api.schemas import ContactCreate, ContactResponse, ContactUpdate
from pengelola_keuangan.db.models import Contact, ContactKind

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _to_response(contact: Contact) -> ContactResponse:
    return ContactResponse(
        id=contact.id,
        name=contact.name,
        kind=ContactKind(contact.kind).value,
        phone=contact.phone,
        address=contact.address,
        notes=contact.notes,
        archived=contact.archived_at is not None,
        created_at=contact.created_at,
    )


@router.get("", response_model=list[ContactResponse])
def list_contacts(
    user: CurrentUser,
    session: DBSession,
    kind: str | None = Query(default=None, pattern="^(customer|supplier|both)$"),
    q: str | None = Query(default=None, max_length=128),
    include_archived: bool = False,
) -> list[ContactResponse]:
    """List the authenticated user's contacts (optional kind / search filter)."""
    stmt = select(Contact).where(Contact.user_id == user.id)
    if kind is not None:
        # ``both`` matches everything except pure-supplier when filtering by customer
        # and vice-versa. Simpler: kind filter matches that exact value or ``both``.
        stmt = stmt.where(Contact.kind.in_([kind, ContactKind.BOTH.value]))
    if q is not None and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(Contact.name.ilike(like))
    if not include_archived:
        stmt = stmt.where(Contact.archived_at.is_(None))
    stmt = stmt.order_by(asc(Contact.name))
    rows = list(session.scalars(stmt))
    return [_to_response(c) for c in rows]


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate, user: CurrentUserCanWrite, session: DBSession
) -> ContactResponse:
    """Create a new directory entry."""
    contact = Contact(
        user_id=user.id,
        name=payload.name.strip(),
        kind=ContactKind(payload.kind),
        phone=(payload.phone or "").strip() or None,
        address=(payload.address or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
    )
    session.add(contact)
    session.flush()
    return _to_response(contact)


def _get_owned(session: DBSession, user_id: int, contact_id: int) -> Contact:
    contact = session.get(Contact, contact_id)
    if contact is None or contact.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kontak gak ketemu")
    return contact


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(contact_id: int, user: CurrentUser, session: DBSession) -> ContactResponse:
    """Get one contact by id."""
    return _to_response(_get_owned(session, user.id, contact_id))


@router.patch("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: CurrentUserCanWrite,
    session: DBSession,
) -> ContactResponse:
    """Patch contact fields."""
    contact = _get_owned(session, user.id, contact_id)
    if payload.name is not None:
        contact.name = payload.name.strip()
    if payload.kind is not None:
        contact.kind = ContactKind(payload.kind)
    if payload.phone is not None:
        contact.phone = payload.phone.strip() or None
    if payload.address is not None:
        contact.address = payload.address.strip() or None
    if payload.notes is not None:
        contact.notes = payload.notes.strip() or None
    session.flush()
    return _to_response(contact)


@router.post("/{contact_id}/archive", response_model=ContactResponse)
def archive_contact(
    contact_id: int, user: CurrentUserCanWrite, session: DBSession
) -> ContactResponse:
    """Archive a contact (soft-delete). Records are kept for piutang/hutang history."""
    contact = _get_owned(session, user.id, contact_id)
    if contact.archived_at is None:
        contact.archived_at = datetime.now(UTC)
        session.flush()
    return _to_response(contact)


@router.post("/{contact_id}/unarchive", response_model=ContactResponse)
def unarchive_contact(
    contact_id: int, user: CurrentUserCanWrite, session: DBSession
) -> ContactResponse:
    """Unarchive a previously archived contact."""
    contact = _get_owned(session, user.id, contact_id)
    if contact.archived_at is not None:
        contact.archived_at = None
        session.flush()
    return _to_response(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, user: CurrentUserCanWrite, session: DBSession) -> None:
    """Hard-delete a contact (only if not referenced elsewhere; safe before piutang/hutang)."""
    contact = _get_owned(session, user.id, contact_id)
    session.delete(contact)
    session.flush()
