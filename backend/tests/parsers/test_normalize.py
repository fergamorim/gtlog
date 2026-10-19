from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models.log import LogLevel
from app.parsers import CATEGORY_RULES, classify_category, normalize_level
from app.parsers.normalize import (
    clean_text,
    level_from_http_status,
    month_number,
    parse_iso_timestamp,
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
    ("status", "level"),
    [(200, LogLevel.INFO), (301, LogLevel.INFO), (404, LogLevel.WARNING), (499, LogLevel.WARNING),
     (500, LogLevel.ERROR), (503, LogLevel.ERROR)],
)
def test_level_from_http_status(status, level):
    assert level_from_http_status(status) is level


def test_to_utc_assumes_naive_is_utc_and_converts_offsets():
    assert to_utc(datetime(2026, 10, 5, 14, 0)) == datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    brt = timezone(timedelta(hours=-3))
    converted = to_utc(datetime(2026, 10, 5, 11, 0, tzinfo=brt))
    assert converted == datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    assert converted.tzinfo is UTC


@pytest.mark.parametrize(
    "raw",
    ["2026-10-05T14:00:00Z", "2026-10-05T14:00:00+00:00", "2026-10-05 14:00:00", "2026-10-05T11:00:00-03:00",
     "2026-10-05T16:00:00+0200"],
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
