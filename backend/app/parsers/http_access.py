"""Apache/Nginx access logs in combined (or common) format.

Example::

    203.0.113.7 - - [19/Oct/2026:13:55:36 -0300] "GET /api/catalog HTTP/1.1" 404 1234 "-" "curl/8.5"

The status code is stored and always sets the level (``level_from_status_code``:
502/503/504 CRITICAL, other 5xx ERROR, 4xx WARNING, 2xx/3xx INFO, 1xx DEBUG); a
code outside 100..599 is not stored and the line is INFO. The service is always
"http" and the message reads ``GET /api/catalog 404 1234B``.
Only failed requests (status >= 400) get a category, classified from the
path without its query string.
"""

import re
from datetime import datetime, timedelta, timezone

from app.models.log import LogLevel
from app.parsers.base import ParsedLine
from app.parsers.normalize import build, level_from_status_code, month_number, parse_status_code

name = "http"

_LINE = re.compile(
    r"^(?P<host>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "
    r'"(?P<request>(?:[^"\\]|\\.)*)" (?P<status>\d{3}) (?P<size>\d+|-)'
    r'(?: "(?:[^"\\]|\\.)*" "(?:[^"\\]|\\.)*")?(?:\s.*)?$'  # nginx may append extra fields
)
_TIMESTAMP = re.compile(
    r"^(?P<day>\d{2})/(?P<month>[A-Za-z]{3})/(?P<year>\d{4}):(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}) "
    r"(?P<sign>[+-])(?P<oh>\d{2})(?P<om>\d{2})$"
)


def _timestamp(value: str) -> datetime | None:
    """Parse ``19/Oct/2026:13:55:36 -0300`` without depending on the locale (%b)."""
    match = _TIMESTAMP.match(value)
    month = month_number(match["month"]) if match else None
    if not match or month is None:
        return None
    offset = timedelta(hours=int(match["oh"]), minutes=int(match["om"]))
    try:
        return datetime(
            int(match["year"]),
            month,
            int(match["day"]),
            int(match["h"]),
            int(match["m"]),
            int(match["s"]),
            tzinfo=timezone(-offset if match["sign"] == "-" else offset),
        )
    except ValueError:
        return None


def parse(line: str) -> ParsedLine | None:
    match = _LINE.match(line.strip())
    if not match:
        return None
    timestamp = _timestamp(match["ts"])
    if timestamp is None:
        return None

    status = int(match["status"])
    code = parse_status_code(status)
    size = "0" if match["size"] == "-" else match["size"]
    parts = match["request"].split()
    if len(parts) >= 2:
        request, path = f"{parts[0]} {parts[1]}", parts[1].split("?", 1)[0]
    else:
        request, path = match["request"] or "-", ""
    return build(
        timestamp,
        level_from_status_code(code) if code is not None else LogLevel.INFO,
        f"{request} {status} {size}B",
        "http",
        category_text=path if status >= 400 else "",
        status_code=code,
    )
