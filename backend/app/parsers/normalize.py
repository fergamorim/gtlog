"""Helpers shared by the format parsers: levels, HTTP status codes, timestamps and ParsedLine assembly."""

import math
import re
from datetime import UTC, datetime

from app.models.log import LogLevel
from app.parsers.base import ParsedLine
from app.parsers.categories import classify_category

SERVICE_MAX_LENGTH = 100

LEVEL_ALIASES: dict[str, LogLevel] = {
    "TRACE": LogLevel.DEBUG,
    "DEBUG": LogLevel.DEBUG,
    "INFO": LogLevel.INFO,
    "INFORMATION": LogLevel.INFO,
    "NOTICE": LogLevel.INFO,
    "WARN": LogLevel.WARNING,
    "WARNING": LogLevel.WARNING,
    "ERR": LogLevel.ERROR,
    "ERROR": LogLevel.ERROR,
    "CRIT": LogLevel.CRITICAL,
    "CRITICAL": LogLevel.CRITICAL,
    "FATAL": LogLevel.CRITICAL,
    "ALERT": LogLevel.CRITICAL,
    "EMERG": LogLevel.CRITICAL,
    "EMERGENCY": LogLevel.CRITICAL,
}

# Syslog severity (PRI % 8) -> level.
SYSLOG_SEVERITY: tuple[LogLevel, ...] = (
    LogLevel.CRITICAL,  # 0 emerg
    LogLevel.CRITICAL,  # 1 alert
    LogLevel.CRITICAL,  # 2 crit
    LogLevel.ERROR,  # 3 err
    LogLevel.WARNING,  # 4 warning
    LogLevel.INFO,  # 5 notice
    LogLevel.INFO,  # 6 info
    LogLevel.DEBUG,  # 7 debug
)


MONTHS: dict[str, int] = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1
    )
}


def month_number(abbreviation: str) -> int | None:
    """'Oct', 'oct' or 'OCT' -> 10; None if not a month abbreviation. Locale-independent."""
    return MONTHS.get(abbreviation.lower())


def normalize_level(value: str) -> LogLevel | None:
    """Map a level name in any case (WARN, err, Fatal...) to LogLevel, or None if unknown."""
    return LEVEL_ALIASES.get(value.strip().upper())


MIN_STATUS_CODE, MAX_STATUS_CODE = 100, 599
# Gateway failures mean the service behind the proxy is down, so they rank above other 5xx.
_CRITICAL_STATUS_CODES = frozenset({502, 503, 504})
# "404" or "404.0" (CSV cells and JSON strings); anything else is not a status code.
_STATUS_TEXT = re.compile(r"^\d{3}(?:\.0+)?$")
# status=404, status: 503, status_code="200", HTTP_STATUS=500 inside a free-text message. The key must
# start a word (so upstream_status=... is ignored) and the code must end one (so status=2000 is too).
_STATUS_IN_TEXT = re.compile(
    r"\b(?:status|status_code|statuscode|http_status|response_code)\s*[=:]\s*\"?(\d{3})\b", re.IGNORECASE
)


def level_from_status_code(code: int) -> LogLevel:
    """Level for an HTTP status code (docs/api.md, "Códigos HTTP e níveis").

    1xx DEBUG, 2xx/3xx INFO, 4xx WARNING, 502/503/504 CRITICAL, other 5xx ERROR.
    """
    if code in _CRITICAL_STATUS_CODES:
        return LogLevel.CRITICAL
    if code >= 500:
        return LogLevel.ERROR
    if code >= 400:
        return LogLevel.WARNING
    if code >= 200:
        return LogLevel.INFO
    return LogLevel.DEBUG


def parse_status_code(value: object) -> int | None:
    """An HTTP status code (100..599) from an int, an integral float or a string like "404" / "404.0".

    Anything else (booleans, "ok", 404.5, 42, 1000) is None.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not _STATUS_TEXT.match(text):
            return None
        value = int(text.split(".", 1)[0])
    if not isinstance(value, int):
        return None
    return value if MIN_STATUS_CODE <= value <= MAX_STATUS_CODE else None


def find_status_code(message: str) -> int | None:
    """The first ``status=404``-style code in a free-text message, or None."""
    for match in _STATUS_IN_TEXT.finditer(message):
        if (code := parse_status_code(match[1])) is not None:
            return code
    return None


def to_utc(value: datetime) -> datetime:
    """Return a tz-aware UTC datetime; naive values are assumed to already be UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_iso_timestamp(value: str) -> datetime | None:
    """Parse ISO 8601 (also 'YYYY-MM-DD HH:MM:SS,ms' and a trailing Z) into UTC, or None."""
    try:
        return to_utc(datetime.fromisoformat(value.strip().replace(",", ".")))
    except (ValueError, OverflowError):
        return None


# Epoch values above this are taken as milliseconds (year 2286 in seconds).
_MAX_EPOCH_SECONDS = 10_000_000_000


def parse_epoch(value: float) -> datetime | None:
    """Epoch seconds, or milliseconds when too large to be seconds, into UTC; None if out of range."""
    if not math.isfinite(value):
        return None
    seconds = value / 1000 if value > _MAX_EPOCH_SECONDS else value
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def clean_text(value: str) -> str:
    """Drop NUL characters and replace lone surrogates, which Postgres text columns reject."""
    return value.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")


def build(
    timestamp: datetime,
    level: LogLevel,
    message: str,
    service: str | None,
    *,
    category_text: str | None = None,
    status_code: int | None = None,
) -> ParsedLine:
    """Assemble a ParsedLine: UTC timestamp, clean text, truncated service and derived category.

    The category is classified from ``category_text`` when given (pass "" for
    no category), otherwise from the message.
    """
    message = clean_text(message).strip()
    service = clean_text(service or "").strip()[:SERVICE_MAX_LENGTH] or None
    return ParsedLine(
        timestamp=to_utc(timestamp),
        level=level,
        message=message,
        service=service,
        category=classify_category(message if category_text is None else category_text),
        status_code=status_code,
    )
