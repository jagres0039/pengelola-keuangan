"""Export to XLSX + import from XLSX with preview/apply workflow."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import (
    ImportApplyRequest,
    ImportApplyResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
)
from pengelola_keuangan.services import exporting as export_svc
from pengelola_keuangan.services import importing as import_svc
from pengelola_keuangan.services import transactions as tx_svc
from pengelola_keuangan.services.time_helpers import current_month

router = APIRouter(tags=["data"])

MAX_IMPORT_BYTES = 8 * 1024 * 1024  # 8 MiB
PLAN_TTL_SECONDS = 600  # plans expire after 10 minutes


@dataclass
class _StoredPlan:
    """In-memory cache entry for an import plan awaiting confirmation."""

    user_id: int
    rows: list[import_svc.ImportRow]
    plan: import_svc.ImportPlan
    tz_name: str
    expires_at: float
    transaction_ids: list[int] = field(default_factory=list)


_PLAN_CACHE: dict[str, _StoredPlan] = {}


def _expire_old_plans() -> None:
    now = time.time()
    expired = [pid for pid, stored in _PLAN_CACHE.items() if stored.expires_at < now]
    for pid in expired:
        _PLAN_CACHE.pop(pid, None)


def _row_to_preview(
    row: import_svc.ImportRow,
    *,
    action: str,
    transaction_id: int | None = None,
) -> ImportPreviewRow:
    return ImportPreviewRow(
        action=action,
        row_index=row.row_index,
        transaction_id=transaction_id,
        type=row.type.value,
        amount=row.amount,
        category_name=row.category_name,
        note=row.note or None,
        occurred_at=row.occurred_at,
    )


@router.get("/export/xlsx")
def export_xlsx(
    user: CurrentUser,
    session: DBSession,
    year: int | None = None,
    month: int | None = None,
) -> Response:
    """Download an XLSX file with transactions for a given month."""
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

    data = export_svc.export_month_to_xlsx(
        session, user.id, y, m, tz, currency=user.currency or "IDR"
    )
    filename = f"pengelola-keuangan-{y:04d}-{m:02d}.xlsx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    user: CurrentUser,
    session: DBSession,
    file: UploadFile = File(..., description="File .xlsx hasil export"),
    year: int | None = None,
    month: int | None = None,
) -> ImportPreviewResponse:
    """Upload an XLSX file, return preview of changes (no DB writes yet)."""
    _expire_old_plans()
    raw = await file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file kosong",
        )
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="ukuran file > 8 MB",
        )

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

    rows, errors = import_svc.parse_import_rows(raw, tz)
    existing = tx_svc.list_for_month(session, user.id, y, m, tz)
    plan = import_svc.build_import_plan(session, user.id, rows, existing)

    plan_id = secrets.token_urlsafe(16)
    _PLAN_CACHE[plan_id] = _StoredPlan(
        user_id=user.id,
        rows=rows,
        plan=plan,
        tz_name=tz,
        expires_at=time.time() + PLAN_TTL_SECONDS,
        transaction_ids=[tx.id for tx in existing],
    )

    return ImportPreviewResponse(
        plan_id=plan_id,
        to_create=[_row_to_preview(row, action="create") for row in plan.to_create],
        to_update=[
            _row_to_preview(row, action="update", transaction_id=existing_tx.id)
            for row, existing_tx in plan.to_update
        ],
        to_delete=[
            ImportPreviewRow(
                action="delete",
                row_index=None,
                transaction_id=tx.id,
                type=tx.type.value if hasattr(tx.type, "value") else str(tx.type),
                amount=tx.amount,
                category_name=tx.category.name if tx.category is not None else "",
                note=tx.note,
                occurred_at=tx.occurred_at,
            )
            for tx in plan.to_delete
        ],
        errors=list(plan.errors) + list(errors),
    )


@router.post("/import/apply", response_model=ImportApplyResponse)
def import_apply(
    payload: ImportApplyRequest,
    user: CurrentUser,
    session: DBSession,
) -> ImportApplyResponse:
    """Apply a previously-previewed import plan."""
    _expire_old_plans()
    stored = _PLAN_CACHE.pop(payload.plan_id, None)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="plan tidak ditemukan atau sudah kadaluarsa, silakan upload ulang",
        )
    if stored.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="plan ini bukan milik user kamu",
        )

    created, updated, deleted = import_svc.apply_import_plan(
        session, user.id, stored.plan, stored.tz_name
    )
    return ImportApplyResponse(created=created, updated=updated, deleted=deleted)
