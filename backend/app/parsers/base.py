from dataclasses import dataclass
from datetime import datetime

from app.models.log import LogLevel


@dataclass(frozen=True, slots=True)
class ParsedLine:
    """A log line normalized into the fields stored in log_entries."""

    timestamp: datetime  # timezone-aware, UTC
    level: LogLevel
    message: str
    service: str | None = None
    category: str | None = None
