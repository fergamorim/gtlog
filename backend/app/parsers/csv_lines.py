"""CSV with a header row::

    timestamp,level,service,message
    2026-10-05T14:03:22Z,ERROR,payments,"timeout calling catalog, after 15023ms"

The first non-blank line is the header. Its delimiter is ``,``, ``;`` or tab
(whichever splits it into the most columns and still yields a valid header).
Column names are matched case-insensitively, first alias wins (see
``_COLUMN_ALIASES``): besides the JSON-lines names it knows common export
columns such as ``sys_updated_at``/``opened_at``, ``priority``/``impact`` and
``assignment_group``/``category``. Only a timestamp column is required (``ts`` and names ending in ``_at``,
``_time`` or ``_ts`` also count), so
detection never picks CSV for other formats. Without a message column the
message is built from the other columns as ``name=value`` pairs, which keeps
every field searchable.

Timestamps are ISO 8601, epoch seconds/milliseconds or day-first
``d/m/yyyy [H:MM[:SS]]`` (as exported in Brazil and Europe). Levels accept
the usual names plus priority scales like ``1 - Critical``/``3 - Low``. An
empty or missing level comes from the status code, or is INFO without one; an
unknown level rejects the row, as do a column count different from the
header's and malformed quoting. Values such as ``?`` or ``N/A`` count as empty.

The HTTP status code comes from a ``status``/``status_code``/``statusCode``/
``http_status``/``response_code`` column (``404`` or ``404.0``); other values
in it (``Closed``) leave it empty. That column also stays in a built message.

The parser is stateful per file (use a fresh CsvParser for each one).
``is_header`` tells the importer which line was the header so it is not
counted as invalid. Reading is line-based: quoted fields may contain
delimiters and doubled quotes, but not line breaks (a field left open at the
end of the line rejects the row).
"""

import csv
import re
from datetime import UTC, datetime

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

name = "csv"

_DELIMITERS = (",", ";", "\t")
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": (
        "timestamp",
        "time",
        "@timestamp",
        "ts",
        "@t",
        "epoch",
        "date",
        "datetime",
        "event_time",
        "updated_at",
        "sys_updated_at",
        "created_at",
        "sys_created_at",
        "opened_at",
    ),
    "level": ("level", "severity", "priority", "urgency", "impact"),
    "service": ("service", "logger", "app", "source", "component", "host", "assignment_group", "category"),
    "message": ("message", "msg", "description", "short_description", "summary"),
    "status": ("status", "status_code", "statuscode", "http_status", "response_code"),
}
# Columns whose value is part of a built message even though they are mapped (see _describe).
_DESCRIBED_FIELDS = ("status",)
_REQUIRED = ("timestamp",)
# Without a known timestamp name, the first column named like "login_time" or "closed_at" is used.
_TIMESTAMP_SUFFIXES = ("_at", "_time", "_ts", "_timestamp", "_date")
_EPOCH = re.compile(r"^\d+(?:\.\d+)?$")
_DAY_FIRST = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$")
# Priority/impact scales ("1 - Critical", "3 - Moderate"): the number is dropped, the word mapped.
_SCALE_PREFIX = re.compile(r"^\d+\s*-\s*")
_SCALE_LEVELS: dict[str, LogLevel] = {
    "CRITICAL": LogLevel.CRITICAL,
    "HIGH": LogLevel.ERROR,
    "MODERATE": LogLevel.WARNING,
    "MEDIUM": LogLevel.WARNING,
    "LOW": LogLevel.INFO,
    "PLANNING": LogLevel.DEBUG,
}
_MISSING = frozenset({"", "?", "-", "n/a", "na", "null", "none"})


def _value(raw: str | None) -> str | None:
    """The stripped value, or None for empty cells and placeholders like '?' or 'N/A'."""
    if raw is None:
        return None
    value = raw.strip()
    return None if value.lower() in _MISSING else value


def _split(line: str, delimiter: str) -> list[str] | None:
    try:
        return next(csv.reader([line], delimiter=delimiter, strict=True), None)
    except csv.Error:  # bad quoting, unterminated quote, field above csv.field_size_limit()
        return None


def _columns(names: list[str]) -> dict[str, int] | None:
    """Map each field to its column index, or None if a required field is missing."""
    positions: dict[str, int] = {}
    for index, header in enumerate(names):
        positions.setdefault(header.strip().lower(), index)
    columns = {
        field: next(positions[alias] for alias in aliases if alias in positions)
        for field, aliases in _COLUMN_ALIASES.items()
        if any(alias in positions for alias in aliases)
    }
    if "timestamp" not in columns:
        suffixed = (index for name, index in positions.items() if name.endswith(_TIMESTAMP_SUFFIXES))
        if (index := next(suffixed, None)) is not None:
            columns["timestamp"] = index
    return columns if all(field in columns for field in _REQUIRED) else None


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    if _EPOCH.match(value):
        return parse_epoch(float(value))
    if match := _DAY_FIRST.match(value):
        day, month, year, hour, minute, second = (int(part or 0) for part in match.groups())
        try:
            return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
        except ValueError:
            return None
    return parse_iso_timestamp(value)


def _level(value: str | None, status_code: int | None) -> LogLevel | None:
    if value is None:
        return LogLevel.INFO if status_code is None else level_from_status_code(status_code)
    return normalize_level(value) or _SCALE_LEVELS.get(_SCALE_PREFIX.sub("", value).upper())


class CsvParser:
    """CSV parser that learns the delimiter and columns from the first line it sees."""

    name = name

    def __init__(self) -> None:
        self._header: str | None = None
        self._delimiter = ","
        self._width = 0
        self._columns: dict[str, int] | None = None
        self._names: list[str] = []

    def is_header(self, line: str) -> bool:
        """True for the header line (also if it repeats, e.g. concatenated CSV files)."""
        return self._header is not None and line.strip().removeprefix("﻿") == self._header

    def parse(self, line: str) -> ParsedLine | None:
        line = line.strip().removeprefix("﻿")
        if not line:
            return None
        if self._header is None:
            self._read_header(line)
            return None
        if self._columns is None or line == self._header:
            return None

        row = _split(line, self._delimiter)
        if row is None or len(row) != self._width:
            return None
        get = {field: _value(row[index]) for field, index in self._columns.items()}
        timestamp = _timestamp(get["timestamp"])
        status_code = parse_status_code(get.get("status"))
        level = _level(get.get("level"), status_code)
        message = get["message"] if "message" in self._columns else self._describe(row)
        if timestamp is None or level is None or not message:
            return None
        return build(timestamp, level, message, get.get("service"), status_code=status_code)

    def _describe(self, row: list[str]) -> str:
        """Message for files without a message column: the unmapped columns as name=value pairs."""
        columns = self._columns or {}
        used = {index for field, index in columns.items() if field not in _DESCRIBED_FIELDS}
        pairs = (
            f"{name.strip()}={value}"
            for index, (name, raw) in enumerate(zip(self._names, row, strict=True))
            if index not in used and (value := _value(raw)) is not None
        )
        return " ".join(pairs)

    def _read_header(self, line: str) -> None:
        self._header = line
        for delimiter in _DELIMITERS:
            names = _split(line, delimiter) or []
            columns = _columns(names)
            if columns is not None and len(names) > self._width:
                self._delimiter, self._width, self._columns = delimiter, len(names), columns
                self._names = names
