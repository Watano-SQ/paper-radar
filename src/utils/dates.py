from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from dateutil import parser


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def iso_week_label(value: date | datetime | None = None) -> str:
    current = value or utc_now()
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def days_ago_iso(days_back: int) -> str:
    return (utc_now().date() - timedelta(days=days_back)).isoformat()


def to_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        date_parts = value.get("date-parts")
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2]) if len(parts) > 2 else 1
            return date(year, month, day).isoformat()
    if isinstance(value, list) and value:
        return to_iso_date(value[0])
    text = str(value).strip()
    if not text:
        return None
    try:
        return parser.parse(text).date().isoformat()
    except (ValueError, OverflowError, TypeError):
        return None


def year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None
