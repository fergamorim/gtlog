from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models.log import LogLevel
from app.parsers import CATEGORY_RULES, classify_category, normalize_level
from app.parsers.normalize import (
    clean_text,
    find_status_code,
    level_from_status_code,
    month_number,
    parse_epoch,
    parse_iso_timestamp,
    parse_status_code,
    to_utc,
)


@pytest.mark.parametrize(
    ("raw", "level"),
    [
        ("DEBUG", LogLevel.DEBUG),
        ("trace", LogLevel.DEBUG),
        ("Info", LogLevel.INFO),
        ("NOTICE", LogLevel.INFO),
        ("warn", LogLevel.WARNING),
        ("WARNING", LogLevel.WARNING),
        ("err", LogLevel.ERROR),
        ("ERROR", LogLevel.ERROR),
        ("crit", LogLevel.CRITICAL),
        ("CRITICAL", LogLevel.CRITICAL),
        ("Fatal", LogLevel.CRITICAL),
        ("EMERG", LogLevel.CRITICAL),
        ("alert", LogLevel.CRITICAL),
        (" info ", LogLevel.INFO),
    ],
)
def test_normalize_level(raw, level):
    assert normalize_level(raw) is level


@pytest.mark.parametrize("raw", ["", "LOUD", "INFOO", "5"])
def test_normalize_level_unknown(raw):
    assert normalize_level(raw) is None


@pytest.mark.parametrize(
    ("code", "level"),
    [
        (100, LogLevel.DEBUG),
        (101, LogLevel.DEBUG),
        (199, LogLevel.DEBUG),
        (200, LogLevel.INFO),
        (201, LogLevel.INFO),
        (204, LogLevel.INFO),
        (301, LogLevel.INFO),
        (304, LogLevel.INFO),
        (400, LogLevel.WARNING),
        (401, LogLevel.WARNING),
        (403, LogLevel.WARNING),
        (404, LogLevel.WARNING),
        (429, LogLevel.WARNING),
        (499, LogLevel.WARNING),
        (500, LogLevel.ERROR),
        (501, LogLevel.ERROR),
        (502, LogLevel.CRITICAL),
        (503, LogLevel.CRITICAL),
        (504, LogLevel.CRITICAL),
        (505, LogLevel.ERROR),
        (599, LogLevel.ERROR),
    ],
)
def test_level_from_status_code_follows_the_documented_table(code, level):
    assert level_from_status_code(code) is level


@pytest.mark.parametrize(
    ("value", "code"),
    [
        (404, 404),
        (100, 100),
        (599, 599),
        (404.0, 404),
        ("404", 404),
        (" 503 ", 503),
        ("404.0", 404),
        ("200.00", 200),
        (99, None),
        (600, None),
        (0, None),
        (-404, None),
        (404.5, None),
        (float("nan"), None),
        ("404.5", None),
        ("4041", None),
        ("abc", None),
        ("ok", None),
        ("", None),
        ("1e2", None),
        ("+404", None),
        (True, None),
        (None, None),
        ([404], None),
    ],
)
def test_parse_status_code(value, code):
    assert parse_status_code(value) == code


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("GET /api/orders status=404 in 12ms", 404),
        ("upstream responded status: 503", 503),
        ("STATUS=500 internal error", 500),
        ("request done status_code=200", 200),
        ("proxy http_status=502 from catalog", 502),
        ("statusCode=401 missing token", 401),
        ("response_code: 429 rate limited", 429),
        ('response {"status":"404"}', None),  # a JSON key in quotes is not a key=value pair
        ('status="404" path=/x', 404),
        ("status=999 then status=201", 201),
        ("upstream_status=502 from nginx", None),
        ("status=2000 items", None),
        ("status=20 ms", None),
        ("status=200ms", None),
        ("status ok after 404 retries", None),
        ("order status changed to shipped", None),
        ("", None),
    ],
)
def test_find_status_code(message, code):
    assert find_status_code(message) == code


def test_to_utc_assumes_naive_is_utc_and_converts_offsets():
    assert to_utc(datetime(2026, 10, 5, 14, 0)) == datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    brt = timezone(timedelta(hours=-3))
    converted = to_utc(datetime(2026, 10, 5, 11, 0, tzinfo=brt))
    assert converted == datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    assert converted.tzinfo is UTC


@pytest.mark.parametrize(
    "raw",
    [
        "2026-10-05T14:00:00Z",
        "2026-10-05T14:00:00+00:00",
        "2026-10-05 14:00:00",
        "2026-10-05T11:00:00-03:00",
        "2026-10-05T16:00:00+0200",
    ],
)
def test_parse_iso_timestamp_variants(raw):
    assert parse_iso_timestamp(raw) == datetime(2026, 10, 5, 14, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("timeout calling payments after 3000ms", "timeout"),
        ("upstream timed out while reading response header", "timeout"),
        ("database connection refused", "database"),
        ("slow query took 2304ms", "database"),
        ("user user42 logged in", "auth"),
        ("token near expiration for user7", "auth"),
        ("Failed password for root from 10.0.0.5", "auth"),
        ("payment 9c2e1f declined", "payment"),
        ("refund issued for order 812", "payment"),
        ("out of memory in worker 17", "memory"),
        ("java.lang.OutOfMemoryError: Java heap space", "memory"),
        ("disk usage above 95% on node-3", "disk"),
        ("write failed: No space left on device", "disk"),
        ("connection reset by peer", "network"),
        ("DNS lookup failed for api.internal", "network"),
        ("lost connection to db", "database"),
        ("db: pool exhausted", "database"),
        ("(psycopg.OperationalError) SQLSTATE 08006", "database"),
        ("Payment transaction declined", "payment"),
        ("auth failed for user7", "auth"),
        ("Unauthorized: missing bearer", "auth"),
        ("authentication required", "auth"),
        ("request timeouts increasing", "timeout"),
        ("author field updated", None),
        ("tokenizer loaded 32000 entries", None),
        ("mydb_backup_job started", None),
        ("job 3fa9c1 finished", None),
        ("", None),
    ],
)
def test_classify_category(message, category):
    assert classify_category(message) == category


def test_clean_text_removes_nul_and_lone_surrogates():
    assert clean_text("a\x00b\ud800c") == "ab?c"
    assert clean_text("ok ação") == "ok ação"


@pytest.mark.parametrize(("raw", "number"), [("Jan", 1), ("oct", 10), ("DEC", 12), ("Foo", None)])
def test_month_number(raw, number):
    assert month_number(raw) == number


def test_category_names_fit_column():
    assert all(len(name) <= 50 for name, _ in CATEGORY_RULES)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1791209003, datetime(2026, 10, 5, 14, 3, 23, tzinfo=UTC)),
        (1791209003.5, datetime(2026, 10, 5, 14, 3, 23, 500000, tzinfo=UTC)),
        (1791209003250, datetime(2026, 10, 5, 14, 3, 23, 250000, tzinfo=UTC)),  # milliseconds
        (1e300, None),
        (float("nan"), None),
        (float("inf"), None),
    ],
)
def test_parse_epoch(value, expected):
    assert parse_epoch(value) == expected
