import pytest

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
    assert stats["timeseries"] == [point("2026-10-05T10:00:00Z", ERROR=2)]
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
    stats = get_stats(client, start="2026-10-01T00:00:00Z", end="2026-10-08T00:00:00Z")
    assert stats["bucket"] == "day"
    assert stats["timeseries"] == [
        point("2026-10-05T00:00:00Z", DEBUG=1, INFO=2, WARNING=1, ERROR=3, CRITICAL=1)
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
