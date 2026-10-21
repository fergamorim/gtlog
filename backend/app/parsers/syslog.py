"""Syslog, RFC 5424 and RFC 3164 (BSD).

RFC 5424::

    <165>1 2026-10-19T22:14:15.003Z web01 nginx 2112 ID47 [meta x="1"] upstream timed out

RFC 3164 (the ``<PRI>`` prefix is optional, as in /var/log/syslog)::

    <34>Oct 19 22:14:15 web01 sshd[4721]: Failed password for root from 10.0.0.5

The level comes from the PRI severity (PRI % 8). A ``status=404``-style pair in
the message sets the HTTP status code; without a PRI the level comes from that
code, or is INFO when there is none.
The service is the APP-NAME / TAG. RFC 3164 has no year or zone: the timestamp
is read as UTC in the reference year, or the previous one if that would put it
more than a day in the future (December logs read in January). The reference
time is captured once per SyslogParser, so a whole file uses the same year.
"""

import re
from datetime import UTC, datetime, timedelta

from app.models.log import LogLevel
from app.parsers.base import ParsedLine
from app.parsers.normalize import (
    SYSLOG_SEVERITY,
    build,
    find_status_code,
    level_from_status_code,
    month_number,
    parse_iso_timestamp,
)

name = "syslog"

_RFC5424 = re.compile(
    r"^<(?P<pri>\d{1,3})>1 (?P<ts>\S+) (?P<host>\S+) (?P<app>\S+) (?P<procid>\S+) (?P<msgid>\S+) "
    r"(?P<sd>-|(?:\[(?:[^\]\\]|\\.)*\])+)(?: (?P<msg>.*))?$"
)
_RFC3164 = re.compile(
    r"^(?:<(?P<pri>\d{1,3})>)?(?P<month>[A-Za-z]{3}) {1,2}(?P<day>\d{1,2}) "
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}) (?P<host>\S+) "
    r"(?:(?P<app>[^\s\[\]:]+)(?:\[[^\]]*\])?: ?)?(?P<msg>.*)$"
)


def _level(pri: str | None, status_code: int | None) -> LogLevel | None:
    if pri is None:
        return LogLevel.INFO if status_code is None else level_from_status_code(status_code)
    value = int(pri)
    return SYSLOG_SEVERITY[value % 8] if value <= 191 else None


def _parse_5424(line: str) -> ParsedLine | None:
    match = _RFC5424.match(line)
    if not match:
        return None
    timestamp = parse_iso_timestamp(match["ts"]) if match["ts"] != "-" else None
    message = (match["msg"] or "").removeprefix("﻿")
    status_code = find_status_code(message)
    level = _level(match["pri"], status_code)
    if level is None or timestamp is None or not message.strip():
        return None
    app = match["app"] if match["app"] != "-" else None
    return build(timestamp, level, message, app, status_code=status_code)


def _parse_3164(line: str, now: datetime) -> ParsedLine | None:
    match = _RFC3164.match(line)
    month = month_number(match["month"]) if match else None
    if not match or month is None:
        return None
    status_code = find_status_code(match["msg"])
    level = _level(match["pri"], status_code)
    if level is None or not match["msg"].strip():
        return None

    try:
        timestamp = datetime(
            now.year,
            month,
            int(match["day"]),
            int(match["h"]),
            int(match["m"]),
            int(match["s"]),
            tzinfo=UTC,
        )
        if timestamp > now + timedelta(days=1):
            timestamp = timestamp.replace(year=now.year - 1)
    except ValueError:  # bad day/hour, or Feb 29 outside a leap year
        return None
    return build(timestamp, level, match["msg"], match["app"], status_code=status_code)


class SyslogParser:
    """Syslog parser bound to a reference time (default: now, UTC) for RFC 3164 years."""

    name = name

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)

    def parse(self, line: str) -> ParsedLine | None:
        line = line.strip()
        return _parse_5424(line) or _parse_3164(line, self.now)


def parse(line: str) -> ParsedLine | None:
    """Parse one line against the current time; use SyslogParser for a whole file."""
    return SyslogParser().parse(line)
