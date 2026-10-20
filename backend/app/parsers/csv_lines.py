"""CSV with a header row::

    timestamp,level,service,message
    2026-10-05T14:03:22Z,ERROR,payments,"timeout calling catalog, after 15023ms"

The first non-blank line is the header. Its delimiter is ``,``, ``;`` or tab
(whichever splits it into the most columns and still yields a valid header).
Column names are matched case-insensitively, first alias wins:
timestamp/time/@timestamp/date/datetime, level/severity,
service/logger/app/source, message/msg. A header without a timestamp and a
message column is rejected and then every line returns None, so detection
never picks CSV for other formats. Other columns are ignored.

Timestamps are ISO 8601 or epoch seconds/milliseconds. An empty or missing
level defaults to INFO; an unknown one rejects the row, as do a column count
different from the header's and malformed quoting.

The parser is stateful per file (use a fresh CsvParser for each one).
``is_header`` tells the importer which line was the header so it is not
counted as invalid. Reading is line-based: quoted fields may contain
delimiters and doubled quotes, but not line breaks (a field left open at the
end of the line rejects the row).
"""

import csv
import re
from datetime import datetime

from app.models.log import LogLevel
from app.parsers.base import ParsedLine
from app.parsers.normalize import build, normalize_level, parse_epoch, parse_iso_timestamp

name = "csv"

_DELIMITERS = (",", ";", "\t")
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "time", "@timestamp", "date", "datetime"),
    "level": ("level", "severity"),
    "service": ("service", "logger", "app", "source"),
    "message": ("message", "msg"),
}
_REQUIRED = ("timestamp", "message")
_EPOCH = re.compile(r"^\d+(?:\.\d+)?$")


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
    return columns if all(field in columns for field in _REQUIRED) else None


def _timestamp(value: str) -> datetime | None:
    value = value.strip()
    if _EPOCH.match(value):
        return parse_epoch(float(value))
    return parse_iso_timestamp(value) if value else None


def _level(value: str | None) -> LogLevel | None:
    if value is None or not value.strip():
        return LogLevel.INFO
    return normalize_level(value)


class CsvParser:
    """CSV parser that learns the delimiter and columns from the first line it sees."""

    name = name

    def __init__(self) -> None:
        self._header: str | None = None
        self._delimiter = ","
        self._width = 0
        self._columns: dict[str, int] | None = None

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
        get = {field: row[index] for field, index in self._columns.items()}
        timestamp = _timestamp(get["timestamp"])
        level = _level(get.get("level"))
        message = get["message"]
        if timestamp is None or level is None or not message.strip():
            return None
        return build(timestamp, level, message, get.get("service"))

    def _read_header(self, line: str) -> None:
        self._header = line
        for delimiter in _DELIMITERS:
            names = _split(line, delimiter) or []
            columns = _columns(names)
            if columns is not None and len(names) > self._width:
                self._delimiter, self._width, self._columns = delimiter, len(names), columns
