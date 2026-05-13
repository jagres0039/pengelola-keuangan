"""Parsing helpers for amounts and natural-language category hints."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Multiplier suffixes commonly used in Indonesian/English shorthand.
_MULTIPLIERS: dict[str, Decimal] = {
    "rb": Decimal("1000"),
    "k": Decimal("1000"),
    "ribu": Decimal("1000"),
    "jt": Decimal("1000000"),
    "jutaan": Decimal("1000000"),
    "juta": Decimal("1000000"),
    "m": Decimal("1000000"),
    "mio": Decimal("1000000"),
    "mil": Decimal("1000000"),
    "b": Decimal("1000000000"),
    "milyar": Decimal("1000000000"),
    "miliar": Decimal("1000000000"),
}

_AMOUNT_RE = re.compile(
    r"""
    ^
    (?P<sign>-)?
    (?P<num>\d+(?:[.,]\d+)*)
    \s*
    (?P<suffix>[a-zA-Z]+)?
    $
    """,
    re.VERBOSE,
)


class ParseError(ValueError):
    """Raised when input cannot be parsed."""


def parse_amount(text: str) -> Decimal:
    """Parse a human-friendly amount into a Decimal.

    Accepts:
      - "5000"          -> 5000
      - "5.000"         -> 5000
      - "5,000"         -> 5000
      - "5000.50"       -> 5000.50
      - "5000,50"       -> 5000.50
      - "5rb"           -> 5000
      - "1.5jt"         -> 1500000
      - "2k"            -> 2000

    Raises:
      ParseError: when the text cannot be interpreted as a positive amount.
    """
    if text is None:
        raise ParseError("Jumlah kosong.")
    cleaned = text.strip().replace(" ", "")
    if not cleaned:
        raise ParseError("Jumlah kosong.")

    match = _AMOUNT_RE.match(cleaned)
    if not match:
        raise ParseError(f"Format jumlah tidak valid: {text!r}")

    sign = match.group("sign") or ""
    num_str = match.group("num")
    suffix = (match.group("suffix") or "").lower()

    # Normalize thousand/decimal separators.
    # Heuristic: the rightmost '.' or ',' that is followed by exactly 1-2 digits
    # is treated as the decimal separator; all others are thousands separators.
    num_str = _normalize_decimal_string(num_str)

    try:
        value = Decimal(num_str)
    except InvalidOperation as exc:
        raise ParseError(f"Format jumlah tidak valid: {text!r}") from exc

    if suffix:
        if suffix not in _MULTIPLIERS:
            raise ParseError(f"Suffix tidak dikenal: {suffix!r}")
        value *= _MULTIPLIERS[suffix]

    if sign == "-":
        value = -value

    if value <= 0:
        raise ParseError("Jumlah harus lebih besar dari 0.")

    return value


def _normalize_decimal_string(num: str) -> str:
    """Normalize a number string with mixed '.' and ',' separators to a Decimal-parseable form."""
    has_dot = "." in num
    has_comma = "," in num
    if not has_dot and not has_comma:
        return num
    if has_dot and has_comma:
        # The last separator that appears is the decimal point.
        if num.rfind(",") > num.rfind("."):
            return num.replace(".", "").replace(",", ".")
        return num.replace(",", "")
    # Only one separator type present.
    sep = "." if has_dot else ","
    parts = num.split(sep)
    if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
        # Treat as decimal.
        return num.replace(",", ".")
    # Treat as thousands separator.
    return num.replace(sep, "")


# Keyword -> category name (case-insensitive substring match on the note).
_CATEGORY_HINTS: dict[str, list[str]] = {
    "Transport": [
        "gojek",
        "grab",
        "uber",
        "ojek",
        "bensin",
        "pertamax",
        "pertalite",
        "parkir",
        "tol",
        "kereta",
        "krl",
        "transjakarta",
        "busway",
        "taksi",
        "taxi",
    ],
    "Makanan": [
        "makan",
        "kopi",
        "coffee",
        "warteg",
        "warung",
        "restoran",
        "resto",
        "starbucks",
        "mcd",
        "kfc",
        "burger",
        "nasi",
        "ayam",
        "bakso",
        "sate",
        "indomie",
        "gofood",
        "grabfood",
        "shopeefood",
    ],
    "Belanja": [
        "indomart",
        "indomaret",
        "alfamart",
        "alfamidi",
        "tokopedia",
        "shopee",
        "lazada",
        "blibli",
        "bukalapak",
        "supermarket",
        "carrefour",
        "transmart",
    ],
    "Tagihan": [
        "listrik",
        "pln",
        "air",
        "pdam",
        "internet",
        "indihome",
        "biznet",
        "wifi",
        "pulsa",
        "kuota",
        "telkomsel",
        "xl",
        "indosat",
        "tri",
        "smartfren",
        "sewa",
        "kost",
        "kosan",
        "kontrakan",
    ],
    "Hiburan": [
        "bioskop",
        "xxi",
        "cgv",
        "netflix",
        "spotify",
        "youtube premium",
        "disney+",
        "hbo",
        "game",
        "steam",
        "playstation",
    ],
    "Kesehatan": [
        "dokter",
        "klinik",
        "puskesmas",
        "rumah sakit",
        "rs",
        "apotek",
        "obat",
        "vitamin",
        "gym",
        "fitness",
    ],
    "Gaji": ["gaji", "salary", "thr"],
    "Freelance": ["freelance", "proyek", "client", "klien"],
    "Bonus": ["bonus", "tunjangan", "thr"],
    "Investasi": ["dividen", "saham", "reksadana", "bunga deposito"],
}


def guess_category_name(note: str | None) -> str | None:
    """Guess a category name from free-text note based on keyword hints.

    Returns ``None`` if no category can be confidently guessed.
    """
    if not note:
        return None
    lowered = note.lower()
    for category, keywords in _CATEGORY_HINTS.items():
        for keyword in keywords:
            if keyword in lowered:
                return category
    return None
