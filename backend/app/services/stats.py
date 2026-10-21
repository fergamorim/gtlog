"""Dashboard aggregates over the same filters as the log table."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.models import LogEntry, LogLevel
from app.services.log_query import ERROR_LEVELS, LogFilters, build_conditions

Bucket = Literal["second", "minute", "hour", "day"]

TOP_N = 10
BUCKET_STEP: dict[str, timedelta] = {
    "second": timedelta(seconds=1),
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
}
# Automatic bucket: the finest one whose span limit covers the period (at most 300, 180 or 72 points,
# except days, which grow with the period).
AUTO_BUCKETS: tuple[tuple[Bucket, timedelta], ...] = (
    ("second", timedelta(minutes=5)),
    ("minute", timedelta(hours=3)),
    ("hour", timedelta(days=3)),
)
# Gap filling is skipped beyond this many buckets so a huge span cannot blow up the response.
MAX_FILLED_BUCKETS = 10_000
BUCKET_ORIGIN = datetime(2000, 1, 1, tzinfo=UTC)


def pick_bucket(span: timedelta | None) -> Bucket:
    """Finest bucket for a period length (None: no data, hourly)."""
    if span is None:
        return "hour"
    return next((bucket for bucket, limit in AUTO_BUCKETS if span <= limit), "day")


def fit_bucket(bucket: Bucket, span: timedelta | None) -> Bucket:
    """The requested bucket, or the finest coarser one keeping the period under MAX_FILLED_BUCKETS points."""
    buckets = list(BUCKET_STEP)
    for candidate in buckets[buckets.index(bucket) :]:
        if span is None or span // BUCKET_STEP[candidate] < MAX_FILLED_BUCKETS:
            return candidate
    return "day"


def _span(db: Session, filters: LogFilters, conditions: list) -> timedelta | None:
    """Length of the period: the filter bounds, completed by the data when one is open."""
    span_start, span_end = filters.start, filters.end
    if span_start is None or span_end is None:
        # Open-ended period: measure the data it holds (both ends come from the timestamp index).
        first_ts, last_ts = db.execute(
            select(func.min(LogEntry.timestamp), func.max(LogEntry.timestamp)).where(*conditions)
        ).one()
        span_start, span_end = span_start or first_ts, span_end or last_ts
    return span_end - span_start if span_start and span_end else None


def compute_stats(db: Session, filters: LogFilters, bucket: Bucket | None = None) -> dict:
    conditions = build_conditions(filters)
    if bucket is None:
        bucket = pick_bucket(_span(db, filters, conditions))
    elif bucket != "day":
        # A forced fine bucket over a long period would return one point per second: coarsen it instead.
        bucket = fit_bucket(bucket, _span(db, filters, conditions))

    by_level = {level.value: 0 for level in LogLevel}
    series: dict[datetime, dict[str, int]] = {}
    first: datetime | None = None
    last: datetime | None = None
    for row in _timeseries(db, conditions, bucket):
        by_level[row.level.value] += row.total
        series.setdefault(row.bucket, dict.fromkeys(by_level, 0))[row.level.value] += row.total
        first = row.first if first is None else min(first, row.first)
        last = row.last if last is None else max(last, row.last)

    total = sum(by_level.values())
    errors = sum(by_level[level.value] for level in ERROR_LEVELS)
    return {
        "total": total,
        "by_level": by_level,
        "error_rate": round(errors / total, 4) if total else 0.0,
        "first_timestamp": first,
        "last_timestamp": last,
        "bucket": bucket,
        "timeseries": _fill_gaps(series, bucket, filters.start, filters.end),
        "by_service": _by_service(db, conditions),
        "by_category": _by_category(db, conditions),
        "top_errors": _top_errors(db, conditions),
    }


def _timeseries(db: Session, conditions: list, bucket: Bucket):
    # date_bin is plain arithmetic on the epoch (much cheaper than date_trunc with a time zone) and,
    # with a UTC-midnight origin, gives the same UTC second/minute/hour/day boundaries. Literal SQL keeps the
    # GROUP BY expression identical to the SELECT one.
    bucket_col = func.date_bin(
        literal_column(f"interval '1 {bucket}'"),
        LogEntry.timestamp,
        literal_column("timestamptz '2000-01-01 00:00:00+00'"),
    ).label("bucket")
    stmt = (
        select(
            bucket_col,
            LogEntry.level,
            func.count().label("total"),
            func.min(LogEntry.timestamp).label("first"),
            func.max(LogEntry.timestamp).label("last"),
        )
        .where(*conditions)
        .group_by(bucket_col, LogEntry.level)
    )
    return db.execute(stmt)


def _by_service(db: Session, conditions: list) -> list[dict]:
    total = func.count().label("total")
    stmt = (
        select(LogEntry.service, total, func.count().filter(LogEntry.level.in_(ERROR_LEVELS)).label("errors"))
        .where(*conditions, LogEntry.service.is_not(None))
        .group_by(LogEntry.service)
        .order_by(total.desc(), LogEntry.service)
        .limit(TOP_N)
    )
    return [{"service": r.service, "total": r.total, "errors": r.errors} for r in db.execute(stmt)]


def _by_category(db: Session, conditions: list) -> list[dict]:
    total = func.count().label("total")
    stmt = (
        select(LogEntry.category, total)
        .where(*conditions, LogEntry.category.is_not(None))
        .group_by(LogEntry.category)
        .order_by(total.desc(), LogEntry.category)
        .limit(TOP_N)
    )
    return [{"category": r.category, "total": r.total} for r in db.execute(stmt)]


def _floor(value: datetime, step: timedelta) -> datetime:
    """Start of the UTC bucket holding value (same boundaries as date_bin in _timeseries)."""
    return BUCKET_ORIGIN + (value - BUCKET_ORIGIN) // step * step


def _fill_gaps(
    series: dict[datetime, dict[str, int]],
    bucket: Bucket,
    span_start: datetime | None = None,
    span_end: datetime | None = None,
) -> list[dict]:
    """One object per bucket, with every level key (zeros included).

    Covers the filtered period when it has bounds (a day by hour gives all 24 hours), otherwise
    the first to the last bucket with data.
    """
    if not series:
        return []
    step = BUCKET_STEP[bucket]
    start, end = min(series), max(series)
    if span_start is not None:
        start = min(start, _floor(span_start, step))
    if span_end is not None:
        # end is exclusive: the last bucket is the one holding the instant just before it.
        end = max(end, _floor(span_end - timedelta(microseconds=1), step))
    steps = (end - start) // step
    keys = sorted(series) if steps >= MAX_FILLED_BUCKETS else [start + i * step for i in range(steps + 1)]
    zeros = {level.value: 0 for level in LogLevel}
    return [{"bucket": key, **series.get(key, zeros)} for key in keys]


def _top_errors(db: Session, conditions: list) -> list[dict]:
    # Numbers vary between otherwise identical messages (ids, durations); fold them into '#'.
    pattern = func.regexp_replace(
        LogEntry.message, literal_column("'[0-9]+'"), literal_column("'#'"), literal_column("'g'")
    ).label("message")
    count = func.count().label("count")
    stmt = (
        select(pattern, count, func.max(LogEntry.timestamp).label("last_seen"))
        .where(*conditions, LogEntry.level.in_(ERROR_LEVELS))
        .group_by(pattern)
        .order_by(count.desc(), pattern)
        .limit(TOP_N)
    )
    return [{"message": r.message, "count": r.count, "last_seen": r.last_seen} for r in db.execute(stmt)]
