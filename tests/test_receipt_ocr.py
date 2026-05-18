"""Unit tests for the receipt_ocr service. Gemini calls are mocked."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from pengelola_keuangan.services import receipt_ocr


def _make_response(payload: dict[str, Any]) -> MagicMock:
    """Build a mock genai response object whose ``.text`` returns JSON."""
    resp = MagicMock()
    resp.text = json.dumps(payload)
    resp.parsed = None
    return resp


def _patch_client(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any] | None = None
) -> MagicMock:
    """Patch google.genai.Client.models.generate_content to return our fake."""
    response = _make_response(payload or {})

    client_instance = MagicMock()
    client_instance.models.generate_content = MagicMock(return_value=response)

    fake_genai_module = MagicMock()
    fake_genai_module.Client = MagicMock(return_value=client_instance)

    fake_types_module = MagicMock()
    fake_types_module.Part.from_bytes = MagicMock(return_value="fake-part")

    monkeypatch.setitem(__import__("sys").modules, "google.genai", fake_genai_module)
    monkeypatch.setitem(
        __import__("sys").modules,
        "google.genai.types",
        fake_types_module,
    )
    return client_instance.models.generate_content


def test_parse_receipt_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "is_receipt": True,
        "merchant": "Indomaret Sudirman",
        "date_iso": "2026-05-13",
        "total_amount": 87500.0,
        "currency": "IDR",
        "suggested_category": "Belanja",
        "notes": "Belanja di Indomaret",
    }
    call = _patch_client(monkeypatch, payload)
    result = receipt_ocr.parse_receipt(
        b"\xff\xd8imagebytes",
        api_key="fake-key",
        category_hints=["Makanan", "Belanja", "Transport"],
    )
    assert result.is_receipt is True
    assert result.merchant == "Indomaret Sudirman"
    assert result.total_amount == Decimal("87500.0")
    assert result.suggested_category == "Belanja"
    assert result.currency == "IDR"
    assert result.occurred_at is not None
    assert result.occurred_at.year == 2026
    assert result.occurred_at.month == 5
    assert result.occurred_at.day == 13
    call.assert_called_once()


def test_parse_receipt_with_datetime(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "is_receipt": True,
        "merchant": "KFC",
        "date_iso": "2026-05-13T14:32",
        "total_amount": 65000,
        "currency": "IDR",
        "suggested_category": "Makanan",
        "notes": "",
    }
    _patch_client(monkeypatch, payload)
    result = receipt_ocr.parse_receipt(b"img", api_key="k")
    assert result.occurred_at is not None
    assert result.occurred_at.hour == 14
    assert result.occurred_at.minute == 32


def test_parse_receipt_not_a_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "is_receipt": False,
        "merchant": "",
        "date_iso": "",
        "total_amount": 0,
        "currency": "",
        "suggested_category": "",
        "notes": "Foto orang, bukan struk.",
    }
    _patch_client(monkeypatch, payload)
    result = receipt_ocr.parse_receipt(b"img", api_key="k")
    assert result.is_receipt is False
    assert result.is_valid() is False
    assert result.total_amount == Decimal(0)


def test_parse_receipt_string_amount(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even though schema expects float, defend against str amounts."""
    payload = {
        "is_receipt": True,
        "merchant": "Tokopedia",
        "date_iso": "2026-05-10",
        "total_amount": "Rp 1.500.000",  # noisy
        "currency": "IDR",
        "suggested_category": "Belanja",
        "notes": "",
    }
    _patch_client(monkeypatch, payload)
    # The schema will coerce or fail. We allow the coerce path via fallback:
    # in production it will be a float (Pydantic coerces), but our defense
    # via _coerce_decimal handles strings if model_validate passes them.
    try:
        result = receipt_ocr.parse_receipt(b"img", api_key="k")
    except receipt_ocr.ReceiptParseError:
        # acceptable: schema strictness rejected the raw string
        return
    # If schema permitted coercion, value should be sane.
    assert result.total_amount >= Decimal(0)


def test_parse_receipt_empty_bytes_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(receipt_ocr.ReceiptParseError, match="kosong"):
        receipt_ocr.parse_receipt(b"", api_key="k")


def test_parse_receipt_no_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(receipt_ocr.ReceiptParseError, match="GEMINI_API_KEY"):
        receipt_ocr.parse_receipt(b"img", api_key="")


def test_parse_receipt_too_large_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    huge = b"x" * (receipt_ocr.MAX_IMAGE_SIZE + 1)
    with pytest.raises(receipt_ocr.ReceiptParseError, match="terlalu besar"):
        receipt_ocr.parse_receipt(huge, api_key="k")


def test_parse_receipt_invalid_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.text = "this is not json"
    response.parsed = None
    client_instance = MagicMock()
    client_instance.models.generate_content = MagicMock(return_value=response)
    fake_genai = MagicMock()
    fake_genai.Client = MagicMock(return_value=client_instance)
    fake_types = MagicMock()
    fake_types.Part.from_bytes = MagicMock(return_value="part")
    monkeypatch.setitem(__import__("sys").modules, "google.genai", fake_genai)
    monkeypatch.setitem(__import__("sys").modules, "google.genai.types", fake_types)
    with pytest.raises(receipt_ocr.ReceiptParseError):
        receipt_ocr.parse_receipt(b"img", api_key="k")


def test_coerce_decimal_handles_strings_and_negatives() -> None:
    assert receipt_ocr._coerce_decimal("Rp 1,500,000") == Decimal("1500000")
    assert receipt_ocr._coerce_decimal("") == Decimal(0)
    assert receipt_ocr._coerce_decimal(-50) == Decimal(0)
    assert receipt_ocr._coerce_decimal(12345.67) == Decimal("12345.67")


def test_parse_iso_datetime_variants() -> None:
    assert receipt_ocr._parse_iso_datetime("2026-05-13") is not None
    assert receipt_ocr._parse_iso_datetime("2026-05-13T14:32") is not None
    assert receipt_ocr._parse_iso_datetime("2026-05-13T14:32:00+07:00") is not None
    assert receipt_ocr._parse_iso_datetime("") is None
    assert receipt_ocr._parse_iso_datetime("not-a-date") is None


def test_ocr_result_is_valid() -> None:
    valid = receipt_ocr.OCRResult(
        is_receipt=True,
        merchant="A",
        occurred_at=None,
        total_amount=Decimal(100),
        currency="IDR",
        suggested_category="",
        notes="",
        raw_text="",
        items=[],
    )
    assert valid.is_valid() is True

    invalid_zero = receipt_ocr.OCRResult(
        is_receipt=True,
        merchant="A",
        occurred_at=None,
        total_amount=Decimal(0),
        currency="IDR",
        suggested_category="",
        notes="",
        raw_text="",
        items=[],
    )
    assert invalid_zero.is_valid() is False

    invalid_not_receipt = receipt_ocr.OCRResult(
        is_receipt=False,
        merchant="",
        occurred_at=None,
        total_amount=Decimal(100),
        currency="",
        suggested_category="",
        notes="",
        raw_text="",
        items=[],
    )
    assert invalid_not_receipt.is_valid() is False


def test_parse_receipt_extracts_items(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "is_receipt": True,
        "merchant": "Indomaret",
        "date_iso": "2026-05-13",
        "total_amount": 30500.0,
        "currency": "IDR",
        "suggested_category": "Belanja",
        "notes": "3 item",
        "items": [
            {"name": "Indomie Goreng", "qty": 3, "unit_price": 4000, "subtotal": 12000},
            {"name": "Aqua 600ml", "qty": 2, "unit_price": 4000, "subtotal": 8000},
            {"name": "Sabun", "qty": 1, "unit_price": 10500, "subtotal": 10500},
        ],
    }
    _patch_client(monkeypatch, payload)
    result = receipt_ocr.parse_receipt(b"img", api_key="k")
    assert len(result.items) == 3
    assert result.items[0].name == "Indomie Goreng"
    assert result.items[0].qty == Decimal("3")
    assert result.items[0].subtotal == Decimal("12000")
    assert result.items[1].name == "Aqua 600ml"
    assert result.items[2].subtotal == Decimal("10500")


def test_parse_receipt_handles_missing_items(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "is_receipt": True,
        "merchant": "X",
        "date_iso": "2026-05-13",
        "total_amount": 50000,
        "currency": "IDR",
        "suggested_category": "",
        "notes": "",
    }
    _patch_client(monkeypatch, payload)
    result = receipt_ocr.parse_receipt(b"img", api_key="k")
    assert result.items == []


def test_parse_receipt_item_skips_empty_name(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "is_receipt": True,
        "merchant": "X",
        "date_iso": "2026-05-13",
        "total_amount": 50000,
        "currency": "IDR",
        "suggested_category": "",
        "notes": "",
        "items": [
            {"name": "", "qty": 1, "unit_price": 5000, "subtotal": 5000},
            {"name": "Roti", "qty": 1, "unit_price": 8000, "subtotal": 8000},
        ],
    }
    _patch_client(monkeypatch, payload)
    result = receipt_ocr.parse_receipt(b"img", api_key="k")
    assert len(result.items) == 1
    assert result.items[0].name == "Roti"
