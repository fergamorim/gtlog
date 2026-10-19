"""Dashboard aggregates over the same filters as the log table."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.models import LogEntry, LogLevel
from app.services.log_query import ERROR_LEVELS, LogFilters, build_conditions

Bucket = Literal["hour", "day"]

TOP_N = 10
AUTO_HOUR_MAX_RANGE = timedelta(days=3)
BUCKET_STEP: dict[str, timedelta] = {"hour": timedelta(hours=1), "day": timedelta(days=1)}
# Gap filling is skipped beyond this many buckets so a huge span cannot blow up the response.
MAX_FILLED_BUCKETS = 10_000


def compute_stats(db: Session, filters: LogFilters, bucket: Bucket | None = None) -> dict:
    conditions = build_conditions(filters)
    # Hourly rows can always be rolled up into days, so the auto bucket can be picked after one scan.
    query_bucket: Bucket = bucket or "hour"

    by_level = {level.value: 0 for level in LogLevel}
    series: dict[datetime, dict[str, int]] = {}
    first: datetime | None = None
    last: datetime | None = None
    for row in _timeseries(db, conditions, query_bucket):
        by_level[row.level.value] += row.total
        series.setdefault(row.bucket, dict.fromkeys(by_level, 0))[row.level.value] += row.total
        first = row.first if first is None else min(first, row.first)
        last = row.last if last is None else max(last, row.last)

    if bucket is None:
        span_start = filters.start or first
        span_end = filters.end or last
        auto_hour = span_start is None or span_end is None or span_end - span_start <= AUTO_HOUR_MAX_RANGE
        bucket = "hour" if auto_hour else "day"
    if bucket != query_bucket:
        series = _roll_up_to_days(series)

    total = sum(by_level.values())
    errors = sum(by_level[level.value] for level in ERROR_LEVELS)
    return {
        "total": total,
        "by_level": by_level,
        "error_rate": round(errors / total, 4) if total else 0.0,
        "first_timestamp": first,
        "last_timestamp": last,
        "bucket": bucket,
        "timeseries": _fill_gaps(series, bucket),
        "by_service": _by_service(db, conditions),
        "by_category": _by_category(db, conditions),
        "top_errors": _top_errors(db, conditions),
    }


def _timeseries(db: Session, conditions: list, bucket: Bucket):
    # date_bin is plain arithmetic on the epoch (much cheaper than date_trunc with a time zone) and,
    # with a UTC-midnight origin, gives the same UTC hour/day boundaries. Literal SQL keeps the
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


def _roll_up_to_days(series: dict[datetime, dict[str, int]]) -> dict[datetime, dict[str, int]]:
    days: dict[datetime, dict[str, int]] = {}
    for hour, counts in series.items():
        day = days.setdefault(hour.astimezone(UTC).replace(hour=0), dict.fromkeys(counts, 0))
        for level, count in counts.items():
            day[level] += count
    return days


def _fill_gaps(series: dict[datetime, dict[str, int]], bucket: Bucket) -> list[dict]:
    """One object per bucket from the first to the last, with every level key (zeros included)."""
    if not series:
        return []
    start, end = min(series), max(series)
    step = BUCKET_STEP[bucket]
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
