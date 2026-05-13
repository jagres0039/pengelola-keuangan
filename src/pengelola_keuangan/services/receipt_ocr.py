"""Receipt OCR via Google Gemini Vision API.

Parses a receipt image into a structured ``OCRResult`` containing merchant,
date, total amount, and a suggested category (matched against the user's
existing categories when possible).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Maximum image size we accept before sending to the API (bytes).
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB


class ReceiptParseError(RuntimeError):
    """Raised when a receipt cannot be parsed."""


class _ReceiptSchema(BaseModel):
    """JSON schema we ask Gemini to populate.

    Field names are intentionally simple/snake_case so the model fills them
    reliably. We use plain strings instead of native datetime/Decimal so the
    schema stays JSON-friendly.
    """

    model_config = ConfigDict(extra="ignore")

    is_receipt: bool = Field(description="True kalau gambar ini struk/invoice/bukti bayar.")
    merchant: str = Field(default="", description="Nama merchant / toko / penjual.")
    date_iso: str = Field(
        default="",
        description="Tanggal transaksi dalam format ISO 'YYYY-MM-DD' atau 'YYYY-MM-DDTHH:MM'. Kosong kalau tidak ada.",
    )
    total_amount: float = Field(
        default=0.0,
        description="Total akhir yang dibayar (angka, tanpa simbol mata uang). 0 kalau tidak ditemukan.",
    )
    currency: str = Field(default="", description="Kode mata uang 3-huruf (IDR/USD/...).")
    suggested_category: str = Field(
        default="",
        description="Nama kategori yang paling cocok dari daftar yang diberikan. Boleh kosong.",
    )
    notes: str = Field(default="", description="Ringkasan singkat (1 kalimat) tentang transaksi.")


@dataclass(slots=True)
class OCRResult:
    """Result of parsing a receipt image."""

    is_receipt: bool
    merchant: str
    occurred_at: datetime | None
    total_amount: Decimal
    currency: str
    suggested_category: str
    notes: str
    raw_text: str

    def is_valid(self) -> bool:
        """Return True if the result is usable for creating a transaction."""
        return self.is_receipt and self.total_amount > 0


def _parse_iso_datetime(value: str) -> datetime | None:
    """Best-effort ISO datetime parsing. Returns None when value cannot be parsed."""
    value = (value or "").strip()
    if not value:
        return None
    candidates = [
        value,
        value.replace("Z", "+00:00"),
        value + "T00:00:00" if len(value) == 10 else value,
    ]
    for cand in candidates:
        try:
            return datetime.fromisoformat(cand)
        except ValueError:
            continue
    return None


def _coerce_decimal(value: float | int | str) -> Decimal:
    """Coerce a numeric/str value into a non-negative Decimal."""
    try:
        if isinstance(value, str):
            # Strip currency symbols / whitespace.
            cleaned = "".join(ch for ch in value if ch.isdigit() or ch in {".", ",", "-"})
            cleaned = cleaned.replace(",", "")
            dec = Decimal(cleaned) if cleaned else Decimal(0)
        else:
            dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        dec = Decimal(0)
    if dec < 0:
        dec = Decimal(0)
    return dec


def _build_prompt(category_hints: Sequence[str], default_currency: str) -> str:
    cats = ", ".join(category_hints) if category_hints else "(tidak ada)"
    return (
        "Tugas: Lo adalah parser struk pembayaran berbahasa Indonesia. "
        "Lihat gambar yang dilampirkan dan ekstrak data berikut.\n\n"
        "Aturan:\n"
        "- Kalau gambar BUKAN struk/invoice/bukti bayar (misal: meme, foto orang, screenshot chat), "
        "  set 'is_receipt'=false dan kosongin field lainnya.\n"
        "- 'total_amount' = total akhir yang dibayar, BUKAN subtotal atau diskon. "
        "  Cari kata kunci 'Total', 'Grand Total', 'Bayar', 'Tunai', 'Cash', 'Total Bayar'.\n"
        "- Kembalikan angka mentah tanpa simbol mata uang dan tanpa pemisah ribuan "
        "  (contoh: 87500.00 untuk Rp87.500).\n"
        "- 'date_iso' = format ISO. Kalau jam tidak ada, cukup 'YYYY-MM-DD'.\n"
        f"- Currency default '{default_currency}' kalau struk tidak menyebutkan mata uang eksplisit.\n"
        "- 'suggested_category' wajib dari salah satu kategori berikut "
        f"(case-sensitive): {cats}. Kalau tidak ada yang pas, biarkan kosong.\n"
        "- 'merchant' = nama toko/penjual (singkat, contoh: 'Indomaret', 'Gojek', 'KFC').\n"
        "- 'notes' = ringkasan 1 kalimat singkat tentang transaksi "
        "(contoh: 'Belanja di Indomaret Sudirman, 5 item').\n"
        "\n"
        "Jawab HANYA dengan JSON sesuai skema yang diminta. Tanpa penjelasan tambahan."
    )


def parse_receipt(
    image_bytes: bytes,
    *,
    api_key: str,
    model: str = "gemini-2.5-flash",
    mime_type: str = "image/jpeg",
    category_hints: Sequence[str] | None = None,
    default_currency: str = "IDR",
) -> OCRResult:
    """Send the receipt image to Gemini and parse the response.

    Args:
        image_bytes: raw bytes of the receipt photo (JPEG/PNG/WEBP).
        api_key: Google AI Studio API key.
        model: Gemini model name.
        mime_type: MIME type of the image. Default ``image/jpeg``.
        category_hints: list of category names the user already has. Gemini will
            pick from these (case-sensitive).
        default_currency: fallback currency when not mentioned on the receipt.

    Returns:
        OCRResult populated from the model output.

    Raises:
        ReceiptParseError: when the API call fails or returns unusable data.
    """
    if not api_key:
        raise ReceiptParseError("GEMINI_API_KEY belum di-set.")
    if not image_bytes:
        raise ReceiptParseError("Gambar kosong.")
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ReceiptParseError(
            f"Gambar terlalu besar ({len(image_bytes) // 1024} KB). Maks {MAX_IMAGE_SIZE // 1024} KB."
        )

    # Import lazily so unit tests can run without the package installed.
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(category_hints or [], default_currency)

    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    try:
        response = client.models.generate_content(
            model=model,
            contents=[image_part, prompt],  # type: ignore[arg-type]
            config={
                "response_mime_type": "application/json",
                "response_schema": _ReceiptSchema,
                "temperature": 0.0,
            },
        )
    except Exception as exc:  # pragma: no cover - depends on remote API
        logger.exception("Gemini API error")
        raise ReceiptParseError(f"Gagal kontak Gemini API: {exc}") from exc

    parsed: _ReceiptSchema | None = getattr(response, "parsed", None)
    raw_text: str = (getattr(response, "text", None) or "").strip()
    if parsed is None:
        # Fallback: try parsing raw_text as JSON.
        import json

        try:
            parsed = _ReceiptSchema.model_validate(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ReceiptParseError(
                f"Respons Gemini tidak bisa di-parse: {raw_text[:200]}"
            ) from exc

    return OCRResult(
        is_receipt=bool(parsed.is_receipt),
        merchant=(parsed.merchant or "").strip(),
        occurred_at=_parse_iso_datetime(parsed.date_iso),
        total_amount=_coerce_decimal(parsed.total_amount),
        currency=(parsed.currency or "").strip().upper() or default_currency,
        suggested_category=(parsed.suggested_category or "").strip(),
        notes=(parsed.notes or "").strip(),
        raw_text=raw_text,
    )
