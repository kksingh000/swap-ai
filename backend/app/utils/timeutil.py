"""One rule for time in this codebase:

    everything stored in the DB is UTC; everything shown to a human is IST.

SQLite silently drops tzinfo, so values read back are naive and must be
re-stamped as UTC before any comparison.
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.config import settings

IST = ZoneInfo(settings.TIMEZONE)
UTC = timezone.utc


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_ist() -> datetime:
    return datetime.now(IST)


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Treat a naive datetime coming out of the DB as UTC."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    dt = as_utc(dt)
    return dt.astimezone(IST) if dt else None


def human_ist(dt: Optional[datetime]) -> str:
    local = to_ist(dt)
    if not local:
        return ""
    return local.strftime("%a %d %b at %I:%M %p").replace(" 0", " ")
