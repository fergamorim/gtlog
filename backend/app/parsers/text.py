"""Plain text lines that start with a timestamp and a level.

Accepted shapes (``[service]`` is optional in the first three)::

    2026-10-19T10:00:00Z ERROR [payments] card declined
    2026-10-19T10:00:00Z [ERROR] [payments] card declined
    2026-10-19T10:00:00Z ERROR: card declined
    2026-10-19 10:00:00,123 - payments.api - ERROR - card declined   (Python logging; service = logger)

The timestamp is ISO 8601 or ``YYYY-MM-DD HH:MM:SS[,ms]``. A ``status=404``-style
pair in the message sets the HTTP status code; the line's own level is kept.
"""

import re

from app.parsers.base import ParsedLine
from app.parsers.normalize import build, find_status_code, normalize_level, parse_iso_timestamp

name = "text"

_TS = r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"

_LINE = re.compile(
    _TS
    + r"\s+(?:\[(?P<bracketed>[A-Za-z]+)\]|(?P<level>[A-Za-z]+):?)"
    + r"\s+(?:\[(?P<service>[^\]]*)\]\s*)?"
    + r"(?P<message>\S.*)$"
)
_PYTHON_LOGGING = re.compile(_TS + r" - (?P<service>\S+) - (?P<level>[A-Za-z]+) - (?P<message>\S.*)$")


def parse(line: str) -> ParsedLine | None:
    line = line.strip()
    match = _PYTHON_LOGGING.match(line) or _LINE.match(line)
    if not match:
        return None
    groups = match.groupdict()
    level = normalize_level(groups.get("bracketed") or groups["level"])
    timestamp = parse_iso_timestamp(match["ts"])
    if level is None or timestamp is None:
        return None
    message = match["message"]
    return build(timestamp, level, message, match["service"], status_code=find_status_code(message))
