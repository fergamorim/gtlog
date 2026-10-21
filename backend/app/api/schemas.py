from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import ImportStatus, LogLevel
from app.services.log_query import LogFilters

MAX_INT = 2**31 - 1
# Cap on repeated values per filter (level=...&level=...); each value is bounded by its column size.
MAX_FILTER_VALUES = 20
ServiceValue = Annotated[str, StringConstraints(max_length=100)]
CategoryValue = Annotated[str, StringConstraints(max_length=50)]
# An exact HTTP status code (100..599) or a class from 1xx to 5xx (case-insensitive).
StatusValue = Annotated[str, StringConstraints(pattern=r"^(?:[1-5][0-9]{2}|[1-5][xX]{2})$")]


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: ImportStatus
    format: str | None
    total_lines: int
    parsed_lines: int
    invalid_lines: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class LogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_id: int
    timestamp: datetime
    level: LogLevel
    service: str | None
    category: str | None
    status_code: int | None
    message: str
    raw: str


class LogPage(BaseModel):
    items: list[LogEntryOut]
    next_cursor: str | None


class LogCount(BaseModel):
    total: int


class Facets(BaseModel):
    services: list[str]
    categories: list[str]
    status_codes: list[int]


class TimeseriesPoint(BaseModel):
    bucket: datetime
    DEBUG: int
    INFO: int
    WARNING: int
    ERROR: int
    CRITICAL: int


class ServiceCount(BaseModel):
    service: str
    total: int
    errors: int


class CategoryCount(BaseModel):
    category: str
    total: int


class TopError(BaseModel):
    message: str
    count: int
    last_seen: datetime


class StatsOut(BaseModel):
    total: int
    by_level: dict[LogLevel, int]
    error_rate: float
    first_timestamp: datetime | None
    last_timestamp: datetime | None
    bucket: Literal["hour", "day"]
    timeseries: list[TimeseriesPoint]
    by_service: list[ServiceCount]
    by_category: list[CategoryCount]
    top_errors: list[TopError]


def _as_utc(value: datetime | None) -> datetime | None:
    """Query datetimes without an offset are taken as UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _split_status(values: list[str]) -> tuple[list[int], list[int]]:
    """Validated status values -> (exact codes, class digits), deduplicated and sorted."""
    classes = {int(v[0]) for v in values if v[1:].lower() == "xx"}
    codes = {int(v) for v in values if v[1:].lower() != "xx"}
    return sorted(codes), sorted(classes)


def log_filters(
    level: Annotated[list[LogLevel] | None, Query(max_length=MAX_FILTER_VALUES)] = None,
    service: Annotated[list[ServiceValue] | None, Query(max_length=MAX_FILTER_VALUES)] = None,
    category: Annotated[list[CategoryValue] | None, Query(max_length=MAX_FILTER_VALUES)] = None,
    status: Annotated[list[StatusValue] | None, Query(max_length=MAX_FILTER_VALUES)] = None,
    import_id: Annotated[int | None, Query(ge=1, le=MAX_INT)] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> LogFilters:
    """Query-string filters shared by /logs, /logs/count and /stats."""
    start, end = _as_utc(start), _as_utc(end)
    if start is not None and end is not None and start >= end:
        raise HTTPException(status_code=422, detail="A data inicial deve ser anterior à data final.")
    status_codes, status_classes = _split_status(status or [])
    return LogFilters(
        levels=level or [],
        services=service or [],
        categories=category or [],
        status_codes=status_codes,
        status_classes=status_classes,
        import_id=import_id,
        start=start,
        end=end,
        q=(q or "").strip() or None,
    )


LogFiltersDep = Annotated[LogFilters, Depends(log_filters)]
