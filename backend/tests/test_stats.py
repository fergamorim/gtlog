from datetime import UTC, datetime, timedelta

import pytest

from app.models import LogLevel
from app.services.stats import pick_bucket
from tests.test_logs import ROWS_A, ROWS_B, STATUS_ROWS, entry

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def point(bucket: str, **counts: int) -> dict:
    return {"bucket": bucket} | {level: counts.get(level, 0) for level in LEVELS}


@pytest.fixture
def dataset(client, seed):
    import_a, _ = seed(ROWS_A, "a.log")
    import_b, _ = seed(ROWS_B, "b.log")
    return {"import_a": import_a, "import_b": import_b}


def get_stats(client, **params) -> dict:
    response = client.get("/stats", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_stats_over_all_data(client, dataset):
    stats = get_stats(client)
    assert stats["total"] == 8
    assert stats["by_level"] == {"DEBUG": 1, "INFO": 2, "WARNING": 1, "ERROR": 3, "CRITICAL": 1}
    assert stats["error_rate"] == 0.5
    assert stats["first_timestamp"] == "2026-10-05T10:00:00Z"
    assert stats["last_timestamp"] == "2026-10-05T15:00:00Z"
    # Data spans 5 hours, so the automatic bucket is hourly; empty hours are filled with zeros.
    assert stats["bucket"] == "hour"
    assert stats["timeseries"] == [
        point("2026-10-05T10:00:00Z", INFO=1, ERROR=2, CRITICAL=1),
        point("2026-10-05T11:00:00Z", WARNING=1),
        point("2026-10-05T12:00:00Z", DEBUG=1, ERROR=1),
        point("2026-10-05T13:00:00Z"),
        point("2026-10-05T14:00:00Z"),
        point("2026-10-05T15:00:00Z", INFO=1),
    ]
    # Ties on total are ordered by name; null category is left out.
    assert stats["by_service"] == [
        {"service": "payments", "total": 3, "errors": 3},
        {"service": "auth", "total": 2, "errors": 1},
        {"service": "search", "total": 2, "errors": 0},
        {"service": "catalog", "total": 1, "errors": 0},
    ]
    assert stats["by_category"] == [
        {"category": "timeout", "total": 3},
        {"category": "auth", "total": 1},
        {"category": "database", "total": 1},
    ]
    assert stats["top_errors"] == [
        {"message": "timeout calling auth after #ms", "count": 3, "last_seen": "2026-10-05T12:00:00Z"},
        {"message": "database connection lost", "count": 1, "last_seen": "2026-10-05T10:30:00Z"},
    ]


def test_stats_apply_filters(client, dataset):
    stats = get_stats(client, import_id=dataset["import_a"], q="timeout")
    assert stats["total"] == 2
    assert stats["by_level"]["ERROR"] == 2
    assert stats["error_rate"] == 1.0
    # The two matches are 10 minutes apart: one point per minute.
    assert stats["bucket"] == "minute"
    assert stats["timeseries"] == [
        point(f"2026-10-05T10:{minute}:00Z", ERROR=1 if minute in (10, 20) else 0) for minute in range(10, 21)
    ]
    assert stats["by_service"] == [{"service": "payments", "total": 2, "errors": 2}]
    assert stats["top_errors"] == [
        {"message": "timeout calling auth after #ms", "count": 2, "last_seen": "2026-10-05T10:20:00Z"}
    ]

    stats = get_stats(client, level=["INFO", "WARNING"], service=["search", "auth"])
    assert stats["total"] == 3
    assert stats["error_rate"] == 0.0
    assert stats["top_errors"] == []
    assert stats["by_category"] == [{"category": "auth", "total": 1}]


def test_bucket_follows_filter_range(client, dataset):
    # A range longer than 3 days switches to daily buckets even though the data spans hours.
    # The series covers the whole filtered period, empty days included.
    stats = get_stats(client, start="2026-10-01T00:00:00Z", end="2026-10-08T00:00:00Z")
    assert stats["bucket"] == "day"
    assert stats["timeseries"] == [
        point(f"2026-10-0{day}T00:00:00Z") if day != 5 else
        point("2026-10-05T00:00:00Z", DEBUG=1, INFO=2, WARNING=1, ERROR=3, CRITICAL=1)
        for day in range(1, 8)
    ]

    stats = get_stats(client, start="2026-10-05T00:00:00Z", end="2026-10-08T00:00:00Z")
    assert stats["bucket"] == "hour"


def test_auto_bucket_uses_data_span_without_range(client, seed):
    seed([entry(0, "INFO", "auth", None, "a"), entry(60 * 24 * 4, "ERROR", "auth", None, "b")])
    stats = get_stats(client)
    assert stats["bucket"] == "day"
    assert [p["bucket"] for p in stats["timeseries"]] == [f"2026-10-0{d}T00:00:00Z" for d in range(5, 10)]
    assert stats["timeseries"][-1]["ERROR"] == 1

    stats = get_stats(client, bucket="hour")
    assert stats["bucket"] == "hour"
    assert len(stats["timeseries"]) == 24 * 4 + 1


def test_one_day_by_hour_has_all_24_hours(client, dataset):
    stats = get_stats(client, start="2026-10-05T00:00:00Z", end="2026-10-06T00:00:00Z", bucket="hour")
    buckets = [p["bucket"] for p in stats["timeseries"]]
    assert buckets == [f"2026-10-05T{hour:02d}:00:00Z" for hour in range(24)]
    assert sum(sum(p[level] for level in LEVELS) for p in stats["timeseries"]) == stats["total"]


def test_filled_period_starts_at_the_bucket_holding_start(client, dataset):
    stats = get_stats(client, start="2026-10-05T03:30:00Z", end="2026-10-05T23:59:00Z", bucket="hour")
    buckets = [p["bucket"] for p in stats["timeseries"]]
    assert buckets[0] == "2026-10-05T03:00:00Z"
    assert buckets[-1] == "2026-10-05T23:00:00Z"


@pytest.mark.parametrize(
    ("span", "bucket"),
    [
        (timedelta(seconds=40), "second"),
        (timedelta(minutes=5), "second"),
        (timedelta(minutes=50), "minute"),
        (timedelta(hours=3), "minute"),
        (timedelta(hours=5), "hour"),
        (timedelta(days=3), "hour"),
        (timedelta(days=4), "day"),
        (None, "hour"),
    ],
)
def test_pick_bucket_is_the_finest_that_fits(span, bucket):
    assert pick_bucket(span) == bucket


def test_seconds_apart_logs_get_one_point_per_second(client, seed):
    base = datetime(2026, 10, 21, 14, 33, 15, tzinfo=UTC)
    rows = [
        {"timestamp": base + timedelta(seconds=s), "level": LogLevel.INFO, "service": "auth",
         "category": None, "message": f"m{s}"}
        for s in (0, 0, 2, 5)
    ]
    seed(rows)
    stats = get_stats(client)
    assert stats["bucket"] == "second"
    assert [(p["bucket"], p["INFO"]) for p in stats["timeseries"]] == [
        (f"2026-10-21T14:33:{15 + s}Z", {0: 2, 2: 1, 5: 1}.get(s, 0)) for s in range(6)
    ]

    stats = get_stats(client, start="2026-10-21T14:00:00Z", end="2026-10-21T15:00:00Z")
    assert stats["bucket"] == "minute"
    assert len(stats["timeseries"]) == 60


def test_explicit_bucket(client, dataset):
    stats = get_stats(client, bucket="day")
    assert stats["bucket"] == "day"
    assert stats["timeseries"] == [
        point("2026-10-05T00:00:00Z", DEBUG=1, INFO=2, WARNING=1, ERROR=3, CRITICAL=1)
    ]

    response = client.get("/stats", params={"bucket": "week"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Valor inválido para o parâmetro 'bucket'."}


def test_stats_validates_range(client):
    response = client.get("/stats", params={"start": "2026-10-06T00:00:00Z", "end": "2026-10-05T00:00:00Z"})
    assert response.status_code == 422
    assert response.json()["detail"] == "A data inicial deve ser anterior à data final."


def test_stats_on_empty_dataset(client):
    assert get_stats(client) == {
        "total": 0,
        "by_level": dict.fromkeys(LEVELS, 0),
        "error_rate": 0.0,
        "first_timestamp": None,
        "last_timestamp": None,
        "bucket": "hour",
        "timeseries": [],
        "by_service": [],
        "by_category": [],
        "top_errors": [],
    }


def test_stats_filter_by_status(client, seed):
    seed(STATUS_ROWS)
    stats = get_stats(client, status="5xx")
    assert stats["total"] == 2
    assert stats["by_level"] == {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 1, "CRITICAL": 1}
    assert stats["error_rate"] == 1.0

    stats = get_stats(client, status=["4xx", "200"], level="WARNING")
    assert stats["total"] == 2
    assert stats["by_service"] == [{"service": "gateway", "total": 2, "errors": 0}]

    response = client.get("/stats", params={"status": "abc"})
    assert response.status_code == 422
    assert response.json() == {"detail": "Valor inválido para o parâmetro 'status'."}
