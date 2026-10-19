from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.models import ImportStatus, LogLevel
from app.services.log_query import LogFilters

MAX_INT = 2**31 - 1


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
    message: str
    raw: str


class LogPage(BaseModel):
    items: list[LogEntryOut]
    next_cursor: str | None


class Facets(BaseModel):
    services: list[str]
    categories: list[str]


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


def log_filters(
    level: Annotated[list[LogLevel] | None, Query()] = None,
    service: Annotated[list[str] | None, Query(max_length=100)] = None,
    category: Annotated[list[str] | None, Query(max_length=50)] = None,
    import_id: Annotated[int | None, Query(ge=1, le=MAX_INT)] = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> LogFilters:
    """Query-string filters shared by /logs and /stats."""
    start, end = _as_utc(start), _as_utc(end)
    if start is not None and end is not None and start >= end:
        raise HTTPException(status_code=422, detail="A data inicial deve ser anterior à data final.")
    return LogFilters(
        levels=level or [],
        services=service or [],
        categories=category or [],
        import_id=import_id,
        start=start,
        end=end,
        q=(q or "").strip() or None,
    )


LogFiltersDep = Annotated[LogFilters, Depends(log_filters)]
