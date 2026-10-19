"""JSON lines: one object per line.

Recognized keys (first present wins): timestamp/time/@timestamp, level/severity,
service/logger/app, message/msg. Timestamps may be ISO strings or epoch numbers
(seconds or milliseconds). A missing level defaults to INFO; numeric
pino/bunyan levels (10 trace ... 60 fatal) are mapped too.
"""

import json
import math
from datetime import UTC, datetime
from typing import Any

from app.models.log import LogLevel
from app.parsers.base import ParsedLine
from app.parsers.normalize import build, normalize_level, parse_iso_timestamp

name = "json"

_TIMESTAMP_KEYS = ("timestamp", "time", "@timestamp")
_LEVEL_KEYS = ("level", "severity")
_SERVICE_KEYS = ("service", "logger", "app")
_MESSAGE_KEYS = ("message", "msg")

# pino / bunyan numeric levels.
_NUMERIC_LEVELS: dict[int, LogLevel] = {
    10: LogLevel.DEBUG,  # trace
    20: LogLevel.DEBUG,
    30: LogLevel.INFO,
    40: LogLevel.WARNING,
    50: LogLevel.ERROR,
    60: LogLevel.CRITICAL,  # fatal
}

# Epoch values above this are taken as milliseconds (year 2286 in seconds).
_MAX_EPOCH_SECONDS = 10_000_000_000


def _first(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if record.get(key) is not None:
            return record[key]
    return None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, str):
        return parse_iso_timestamp(value)
    if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value):
        seconds = value / 1000 if value > _MAX_EPOCH_SECONDS else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (ValueError, OverflowError, OSError):
            return None
    return None


def _level(value: Any) -> LogLevel | None:
    if value is None:
        return LogLevel.INFO
    if isinstance(value, str):
        return normalize_level(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return _NUMERIC_LEVELS.get(value)
    return None


def _service(value: Any) -> str | None:
    if isinstance(value, dict):  # ECS style: {"service": {"name": "api"}}
        value = value.get("name")
    return value if isinstance(value, str) else None


def parse(line: str) -> ParsedLine | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        record = json.loads(line)
    except (ValueError, RecursionError):
        return None
    if not isinstance(record, dict):
        return None

    timestamp = _timestamp(_first(record, _TIMESTAMP_KEYS))
    level = _level(_first(record, _LEVEL_KEYS))
    message = _first(record, _MESSAGE_KEYS)
    if timestamp is None or level is None or not isinstance(message, str) or not message.strip():
        return None
    return build(timestamp, level, message, _service(_first(record, _SERVICE_KEYS)))
