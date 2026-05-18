"""Timezone-aware datetime helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_zoneinfo(name: str) -> ZoneInfo:
    """Return a ZoneInfo, falling back to UTC if the name is invalid."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    """Return True iff `name` is a valid IANA timezone."""
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return False
    return True


def now_in(tz_name: str) -> datetime:
    """Current time in the given timezone."""
    return datetime.now(tz=get_zoneinfo(tz_name))


def month_bounds(
    year: int,
    month: int,
    tz_name: str,
) -> tuple[datetime, datetime]:
    """Return [start, end) datetimes (timezone aware) for a calendar month."""
    tz = get_zoneinfo(tz_name)
    start = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end = datetime(year, month + 1, 1, tzinfo=tz)
    return start, end


def current_month(tz_name: str) -> tuple[int, int]:
    """Return (year, month) for the current calendar month in the given timezone."""
    now = now_in(tz_name)
    return now.year, now.month


def shift_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """Add `delta` months to (year, month), normalizing the result."""
    idx = year * 12 + (month - 1) + delta
    return idx // 12, (idx % 12) + 1


def parse_year_month(text: str) -> tuple[int, int]:
    """Parse a ``YYYY-MM`` string."""
    parts = text.strip().split("-")
    if len(parts) != 2:
        raise ValueError(f"Expected YYYY-MM, got {text!r}")
    return int(parts[0]), int(parts[1])


def to_user_tz(dt: datetime, tz_name: str) -> datetime:
    """Convert a (possibly-naive UTC) datetime to the user's timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(get_zoneinfo(tz_name))


def add_days(dt: datetime, days: int) -> datetime:
    """Return dt advanced by ``days`` calendar days."""
    return dt + timedelta(days=days)
