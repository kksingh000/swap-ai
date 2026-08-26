"""Natural-language callback-time parser for Indian English / Hindi / Hinglish.

"call me tomorrow morning", "kal shaam 6 baje", "after 6", "next Monday",
"this weekend", "parso 11 baje" -> a concrete Asia/Kolkata timestamp, plus a
confidence score and a human-readable interpretation so the dashboard can show
exactly how a vague phrase was resolved.
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings

IST = ZoneInfo(settings.TIMEZONE)

PART_OF_DAY = {
    "morning": (10, 0),
    "subah": (10, 0),
    "सुबह": (10, 0),
    "noon": (12, 30),
    "afternoon": (15, 0),
    "dopahar": (15, 0),
    "दोपहर": (15, 0),
    "evening": (18, 30),
    "shaam": (18, 30),
    "sham": (18, 30),
    "शाम": (18, 30),
    "night": (20, 0),
    "raat": (20, 0),
    "रात": (20, 0),
    # Telugu
    "ఉదయం": (10, 0),
    "మధ్యాహ్నం": (15, 0),
    "సాయంత్రం": (18, 30),
    "రాత్రి": (20, 0),
    # Kannada
    "ಬೆಳಿಗ್ಗೆ": (10, 0),
    "ಮಧ್ಯಾಹ್ನ": (15, 0),
    "ಸಂಜೆ": (18, 30),
    "ರಾತ್ರಿ": (20, 0),
}

WEEKDAYS = {
    "monday": 0, "mon": 0, "somvar": 0,
    "tuesday": 1, "tue": 1, "tues": 1, "mangalvar": 1,
    "wednesday": 2, "wed": 2, "budhvar": 2,
    "thursday": 3, "thu": 3, "thurs": 3, "guruvar": 3,
    "friday": 4, "fri": 4, "shukravar": 4,
    "saturday": 5, "sat": 5, "shanivar": 5,
    "sunday": 6, "sun": 6, "ravivar": 6,
}

DEFAULT_HOUR = 11
BUSINESS_START = 9
BUSINESS_END = 21

_TIME_RE = re.compile(
    r"\b(?P<hour>[01]?\d|2[0-3])\s*(?::|\.)?\s*(?P<minute>[0-5]\d)?\s*"
    r"(?P<mer>am|pm|a\.m\.|p\.m\.|baje|बजे)?",
    re.I,
)
_AFTER_RE = re.compile(r"\b(after|baad|ke baad|post|after\s+)\s*(?P<hour>[01]?\d|2[0-3])\b", re.I)
_IN_HOURS_RE = re.compile(r"\bin\s+(?P<n>\d+)\s*(hour|hr|hours|ghante|ghanta)\b", re.I)
_IN_MINS_RE = re.compile(r"\bin\s+(?P<n>\d+)\s*(minute|min|mins|minutes)\b", re.I)


def parse_callback_time(text: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Return {scheduled_time, confidence, interpretation, original_text}."""
    now = (now or datetime.now(IST)).astimezone(IST)
    low = (text or "").lower().strip()

    if not low:
        return _result(_default_slot(now + timedelta(days=1)), 0.3, "No time given, defaulted to tomorrow 11 AM", text)

    # --- relative offsets ------------------------------------------------
    match = _IN_MINS_RE.search(low)
    if match:
        target = now + timedelta(minutes=int(match.group("n")))
        return _result(target, 0.95, f"In {match.group('n')} minutes", text)

    match = _IN_HOURS_RE.search(low)
    if match:
        target = now + timedelta(hours=int(match.group("n")))
        return _result(target, 0.95, f"In {match.group('n')} hours", text)

    # --- which day -------------------------------------------------------
    day_offset: Optional[int] = None
    day_label = ""
    confidence = 0.6

    if re.search(r"(ఎల్లుండి|ನಾಡಿದ್ದು)", low):
        day_offset, day_label, confidence = 2, "day after tomorrow", 0.9
    elif re.search(r"(రేపు|ನಾಳೆ)", low):
        day_offset, day_label, confidence = 1, "tomorrow", 0.9
    elif re.search(r"(ఈరోజు|ఇప్పుడే|ಇವತ್ತು|ಈಗಲೇ)", low):
        day_offset, day_label, confidence = 0, "today", 0.9
    elif re.search(r"\b(parso|day after tomorrow|परसों)\b", low):
        day_offset, day_label, confidence = 2, "day after tomorrow", 0.9
    elif re.search(r"\b(tomorrow|kal|कल)\b", low):
        day_offset, day_label, confidence = 1, "tomorrow", 0.9
    elif re.search(r"\b(today|aaj|abhi|आज)\b", low):
        day_offset, day_label, confidence = 0, "today", 0.9
    elif re.search(r"\b(weekend|is weekend|saturday se)\b", low):
        days_to_saturday = (5 - now.weekday()) % 7 or 7
        day_offset, day_label, confidence = days_to_saturday, "this weekend (Saturday)", 0.7
    elif re.search(r"\b(next week|agle hafte|agle week)\b", low):
        day_offset, day_label, confidence = 7 - now.weekday(), "next week (Monday)", 0.6
    elif re.search(r"\b(next month|agle mahine)\b", low):
        day_offset, day_label, confidence = 30, "next month", 0.4
    else:
        for name, weekday in WEEKDAYS.items():
            if re.search(rf"\b{name}\b", low):
                delta = (weekday - now.weekday()) % 7
                if delta == 0 or "next" in low or "agle" in low:
                    delta = delta or 7
                day_offset = delta
                day_label = name.title()
                confidence = 0.85
                break

    # --- what time -------------------------------------------------------
    hour: Optional[int] = None
    minute = 0
    time_label = ""

    after = _AFTER_RE.search(low)
    if after:
        hour = int(after.group("hour"))
        if hour < 8:
            hour += 12  # "after 6" on a sales call means 6 PM
        hour = min(hour + 1, BUSINESS_END)
        time_label = f"after {after.group('hour')}, scheduled at {hour}:00"
        confidence = max(confidence, 0.8)
    else:
        for word, (h, m) in PART_OF_DAY.items():
            if word in low:
                hour, minute = h, m
                time_label = f"{word} defaulted to {h}:{m:02d}"
                confidence = max(confidence, 0.75)
                break

        explicit = _explicit_time(low)
        if explicit:
            hour, minute = explicit
            time_label = f"{hour:02d}:{minute:02d}"
            confidence = max(confidence, 0.9)

    if day_offset is None and hour is None:
        return _result(
            _default_slot(now + timedelta(days=1)),
            0.35,
            "Could not read a specific time, defaulted to tomorrow 11 AM",
            text,
        )

    if day_offset is None:
        day_offset = 0
        day_label = "today"
    if hour is None:
        hour, minute = DEFAULT_HOUR, 0
        time_label = f"no time given, defaulted to {DEFAULT_HOUR} AM"
        confidence = min(confidence, 0.6)

    target = (now + timedelta(days=day_offset)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    # Never schedule in the past or outside calling hours.
    notes = []
    if target <= now:
        target += timedelta(days=1)
        notes.append("time had passed, moved to next day")
    if target.hour < BUSINESS_START:
        target = target.replace(hour=BUSINESS_START, minute=0)
        notes.append(f"moved to {BUSINESS_START} AM calling hours")
        confidence = min(confidence, 0.7)
    elif target.hour >= BUSINESS_END:
        target = (target + timedelta(days=1)).replace(hour=BUSINESS_START, minute=0)
        notes.append("outside calling hours, moved to next morning")
        confidence = min(confidence, 0.7)

    interpretation = ", ".join(p for p in [day_label, time_label, *notes] if p)
    return _result(target, round(confidence, 2), interpretation, text)


def _explicit_time(low: str) -> Optional[tuple]:
    for match in _TIME_RE.finditer(low):
        raw_hour = match.group("hour")
        mer = (match.group("mer") or "").lower().replace(".", "")
        minute = int(match.group("minute") or 0)
        if not raw_hour:
            continue
        hour = int(raw_hour)
        # A bare number with no meridiem/baje is probably not a time.
        if not mer:
            continue
        if mer in ("pm", "pm"):
            hour = hour if hour == 12 else hour + 12
        elif mer == "am":
            hour = 0 if hour == 12 else hour
        elif mer in ("baje", "बजे"):
            if hour < 8:
                hour += 12  # "6 baje" on an evening callback means 6 PM
        if 0 <= hour <= 23:
            return hour, minute
    return None


def _default_slot(day: datetime) -> datetime:
    return day.replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0)


def _result(target: datetime, confidence: float, interpretation: str, original: str) -> Dict[str, Any]:
    if target.tzinfo is None:
        target = target.replace(tzinfo=IST)
    return {
        "original_text": original,
        "scheduled_time": target.astimezone(IST),
        "scheduled_time_iso": target.astimezone(IST).isoformat(),
        "human_time": target.astimezone(IST).strftime("%a %d %b at %I:%M %p").replace(" 0", " "),
        "confidence": confidence,
        "interpretation": interpretation,
        "timezone": settings.TIMEZONE,
    }
