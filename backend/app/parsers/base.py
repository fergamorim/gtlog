from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.log import LogLevel


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """A log line normalized into the fields stored in log_entries."""

    timestamp: datetime  # timezone-aware, UTC
    level: LogLevel
    message: str
    service: str | None = None
    category: str | None = None
    status_code: int | None = None  # HTTP status (100..599) when the line carries one


class LineParser(Protocol):
    """A log format: turns one raw line into a ParsedLine, or None if the line isn't in this format.

    Implementations must never raise on bad input.
    """

    name: str

    def parse(self, line: str) -> ParsedLine | None: ...
