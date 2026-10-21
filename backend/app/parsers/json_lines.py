"""JSON lines: one object per line.

Recognized keys (first present wins): timestamp/time/@timestamp, level/severity,
service/logger/app, message/msg. Timestamps may be ISO strings or epoch numbers
(seconds or milliseconds). Numeric pino/bunyan levels (10 trace ... 60 fatal)
are mapped too.

The HTTP status code comes from status/status_code/statusCode/http_status/
response_code: the first of those keys holding a code in 100..599 (as a number
or a string like "404") wins, so ``"status": "ok"`` is ignored. An explicit
level always wins; without one the level comes from the status code, or is
INFO when there is none.
"""

import json
from datetime import datetime
from typing import Any

from app.models.log import LogLevel
from app.parsers.base import ParsedLine
from app.parsers.normalize import (
    build,
    level_from_status_code,
    normalize_level,
    parse_epoch,
    parse_iso_timestamp,
    parse_status_code,
)

name = "json"

_TIMESTAMP_KEYS = ("timestamp", "time", "@timestamp")
_LEVEL_KEYS = ("level", "severity")
_SERVICE_KEYS = ("service", "logger", "app")
_MESSAGE_KEYS = ("message", "msg")
_STATUS_KEYS = ("status", "status_code", "statusCode", "http_status", "response_code")

# pino / bunyan numeric levels.
_NUMERIC_LEVELS: dict[int, LogLevel] = {
    10: LogLevel.DEBUG,  # trace
    20: LogLevel.DEBUG,
    30: LogLevel.INFO,
    40: LogLevel.WARNING,
    50: LogLevel.ERROR,
    60: LogLevel.CRITICAL,  # fatal
}


def _first(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if record.get(key) is not None:
            return record[key]
    return None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, str):
        return parse_iso_timestamp(value)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return parse_epoch(value)
    return None


def _status_code(record: dict[str, Any]) -> int | None:
    for key in _STATUS_KEYS:
        if (code := parse_status_code(record.get(key))) is not None:
            return code
    return None


def _level(value: Any, status_code: int | None) -> LogLevel | None:
    if value is None:
        return LogLevel.INFO if status_code is None else level_from_status_code(status_code)
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
    status_code = _status_code(record)
    level = _level(_first(record, _LEVEL_KEYS), status_code)
    message = _first(record, _MESSAGE_KEYS)
    if timestamp is None or level is None or not isinstance(message, str) or not message.strip():
        return None
    return build(timestamp, level, message, _service(_first(record, _SERVICE_KEYS)), status_code=status_code)
