"""Receipt OCR endpoint."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from pengelola_keuangan.api.deps import CurrentUser, DBSession
from pengelola_keuangan.api.schemas import ReceiptOCRResponse
from pengelola_keuangan.config import get_settings
from pengelola_keuangan.db.models import TransactionType
from pengelola_keuangan.services import categories as cat_svc
from pengelola_keuangan.services import receipt_ocr as ocr_svc

router = APIRouter(prefix="/receipt", tags=["receipt"])

MAX_BYTES = 8 * 1024 * 1024  # 8 MiB

# Accept common image content types from phones / cameras.
_ALLOWED_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}


@router.post("/ocr", response_model=ReceiptOCRResponse)
async def parse_receipt(
    user: CurrentUser,
    session: DBSession,
    image: UploadFile = File(..., description="Foto struk (jpg/png/webp/heic)"),
) -> ReceiptOCRResponse:
    """Upload a receipt image, extract structured fields via Gemini Vision."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="fitur OCR struk belum dikonfigurasi (GEMINI_API_KEY kosong)",
        )

    raw = await image.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file kosong",
        )
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="ukuran file > 8 MB",
        )

    mime = (image.content_type or "image/jpeg").lower()
    if mime not in _ALLOWED_MIME:
        # Tolerate unknown types — Gemini will still try to read it.
        mime = "image/jpeg"

    # Pull user's existing expense categories as hints so suggested_category
    # matches what they already have.
    expense_cats = cat_svc.list_categories(session, user.id, TransactionType.EXPENSE)
    hints = [c.name for c in expense_cats]

    try:
        result = ocr_svc.parse_receipt(
            raw,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            mime_type=mime,
            category_hints=hints,
            default_currency=user.currency or "IDR",
        )
    except ocr_svc.ReceiptParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"gagal baca struk: {exc}",
        ) from exc

    suggested_cat_id: int | None = None
    if result.suggested_category:
        matched = cat_svc.find_category_by_name(
            session, user.id, result.suggested_category, TransactionType.EXPENSE
        )
        if matched is not None:
            suggested_cat_id = matched.id

    return ReceiptOCRResponse(
        is_receipt=result.is_receipt,
        merchant=result.merchant,
        occurred_at=result.occurred_at,
        total_amount=result.total_amount,
        currency=result.currency or user.currency or "IDR",
        suggested_category=result.suggested_category,
        suggested_category_id=suggested_cat_id,
        notes=result.notes,
    )
