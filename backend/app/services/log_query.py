"""Log queries: the filter builder shared by /logs and /stats, keyset pagination and facets."""

import base64
import binascii
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, cast, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import REGCONFIG
from sqlalchemy.orm import Session, defer

from app.models import LogEntry, LogLevel

ERROR_LEVELS = (LogLevel.ERROR, LogLevel.CRITICAL)
MAX_BIGINT = 2**63 - 1

# Runs of Unicode letters/digits: they never contain tsquery operators, so a query can be built from them.
_TOKEN = re.compile(r"[^\W_]+")
# Quotes, " or " and a leading "-" are websearch syntax (phrase, alternative, exclusion).
_WEBSEARCH_SYNTAX = re.compile(r'"|\sor\s|(?:^|\s)-\S', re.IGNORECASE)


_SIMPLE = cast("simple", REGCONFIG)


class InvalidCursor(Exception):
    """The pagination cursor could not be decoded."""


@dataclass(frozen=True)
class LogFilters:
    levels: list[LogLevel] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    import_id: int | None = None
    start: datetime | None = None  # inclusive
    end: datetime | None = None  # exclusive
    q: str | None = None


def build_conditions(filters: LogFilters) -> list[ColumnElement[bool]]:
    """WHERE clauses for the given filters; empty list when nothing is filtered."""
    conditions: list[ColumnElement[bool]] = []
    if filters.levels:
        conditions.append(LogEntry.level.in_(filters.levels))
    if filters.services:
        conditions.append(LogEntry.service.in_(filters.services))
    if filters.categories:
        conditions.append(LogEntry.category.in_(filters.categories))
    if filters.import_id is not None:
        conditions.append(LogEntry.import_id == filters.import_id)
    if filters.start is not None:
        conditions.append(LogEntry.timestamp >= filters.start)
    if filters.end is not None:
        conditions.append(LogEntry.timestamp < filters.end)
    if filters.q:
        conditions.append(_text_condition(filters.q))
    return conditions


def _text_condition(q: str) -> ColumnElement[bool]:
    tokens = _TOKEN.findall(q)
    if not tokens:
        # No letters or digits: the tsquery would be empty and match nothing, so search literally.
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return or_(LogEntry.message.ilike(pattern, escape="\\"), LogEntry.service.ilike(pattern, escape="\\"))
    if _WEBSEARCH_SYNTAX.search(q):
        query = func.websearch_to_tsquery(_SIMPLE, q)
    else:
        # Plain words match as prefixes ("pay" finds "payments"). Tokens are letters/digits only,
        # so they cannot inject tsquery operators; the string is still sent as a bound parameter.
        query = func.to_tsquery(_SIMPLE, " & ".join(f"{token}:*" for token in tokens))
    return LogEntry.search_vector.op("@@")(query)


def encode_cursor(entry: LogEntry) -> str:
    raw = f"{entry.timestamp.isoformat()}|{entry.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts_text, id_text = raw.rsplit("|", 1)
        ts = datetime.fromisoformat(ts_text)
        entry_id = int(id_text)
        if ts.tzinfo is None or not 1 <= entry_id <= MAX_BIGINT:
            raise ValueError
        return ts.astimezone(UTC), entry_id
    except (ValueError, OverflowError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursor from None


def list_logs(
    db: Session, filters: LogFilters, limit: int, cursor: str | None = None
) -> tuple[list[LogEntry], str | None]:
    """One page ordered by (timestamp DESC, id DESC) and the cursor for the next one (None at the end)."""
    conditions = build_conditions(filters)
    if cursor:
        ts, entry_id = decode_cursor(cursor)
        # Row-value comparison matches the ix_log_ts_id order, so the scan starts right at the cursor.
        conditions.append(tuple_(LogEntry.timestamp, LogEntry.id) < tuple_(ts, entry_id))
    stmt = (
        select(LogEntry)
        .options(defer(LogEntry.search_vector))
        .where(*conditions)
        .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
        .limit(limit + 1)
    )
    rows = list(db.scalars(stmt))
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    return page, encode_cursor(page[-1])


def count_logs(db: Session, filters: LogFilters) -> int:
    stmt = select(func.count()).select_from(LogEntry).where(*build_conditions(filters))
    return db.scalar(stmt) or 0


def get_log(db: Session, entry_id: int) -> LogEntry | None:
    if not 1 <= entry_id <= MAX_BIGINT:
        return None
    return db.get(LogEntry, entry_id)


def facets(db: Session) -> dict[str, list[str]]:
    """Distinct non-null services and categories, sorted."""
    return {
        "services": _distinct(db, LogEntry.service),
        "categories": _distinct(db, LogEntry.category),
    }


def _distinct(db: Session, column) -> list[str]:
    stmt = select(column).where(column.is_not(None)).distinct().order_by(column)
    return list(db.scalars(stmt))
