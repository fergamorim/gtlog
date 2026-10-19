"""Apache/Nginx access logs in combined (or common) format.

Example::

    203.0.113.7 - - [19/Oct/2026:13:55:36 -0300] "GET /api/catalog HTTP/1.1" 404 1234 "-" "curl/8.5"

Level comes from the status code (5xx ERROR, 4xx WARNING, else INFO), the
service is always "http" and the message reads ``GET /api/catalog 404 1234B``.
Only failed requests (status >= 400) get a category, classified from the
path without its query string.
"""

import re
from datetime import datetime, timedelta, timezone

from app.parsers.base import ParsedLine
from app.parsers.normalize import build, level_from_http_status, month_number

name = "http"

_LINE = re.compile(
    r'^(?P<host>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] '
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
            int(match["year"]), month, int(match["day"]),
            int(match["h"]), int(match["m"]), int(match["s"]),
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
    size = "0" if match["size"] == "-" else match["size"]
    parts = match["request"].split()
    if len(parts) >= 2:
        request, path = f"{parts[0]} {parts[1]}", parts[1].split("?", 1)[0]
    else:
        request, path = match["request"] or "-", ""
    return build(
        timestamp,
        level_from_http_status(status),
        f"{request} {status} {size}B",
        "http",
        category_text=path if status >= 400 else "",
    )
