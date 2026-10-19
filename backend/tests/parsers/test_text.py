from datetime import UTC, datetime

import pytest

from app.models.log import LogLevel
from app.parsers import text


def test_parses_generator_line(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[0])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 22, 418529, tzinfo=UTC)
    assert parsed.level is LogLevel.INFO
    assert parsed.service == "auth"
    assert parsed.message == "user user42 logged in"
    assert parsed.category == "auth"


def test_space_separated_timestamp_with_comma_millis_and_warn_alias(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[2])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, 117000, tzinfo=UTC)
    assert parsed.level is LogLevel.WARNING
    assert parsed.category == "database"


def test_offset_is_converted_to_utc(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[3])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 24, tzinfo=UTC)
    assert parsed.timestamp.utcoffset().total_seconds() == 0
    assert parsed.level is LogLevel.CRITICAL
    assert parsed.category == "memory"


def test_service_is_optional_and_level_case_insensitive(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[6])
    assert parsed is not None
    assert parsed.service is None
    assert parsed.level is LogLevel.DEBUG
    assert parsed.message == "cache lookup key=3fa9c1"


def test_bracketed_level(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[7])
    assert parsed is not None
    assert parsed.level is LogLevel.ERROR
    assert parsed.service == "payments"
    assert parsed.message == "payment 9c2e1f declined by issuer"


def test_level_with_colon(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[8])
    assert parsed is not None
    assert parsed.level is LogLevel.ERROR
    assert parsed.service is None
    assert parsed.message == "could not connect to db: connection refused"
    assert parsed.category == "database"


def test_python_logging_format(fixture_lines):
    parsed = text.parse(fixture_lines("app.log")[9])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 19, 10, 0, 0, 123000, tzinfo=UTC)
    assert parsed.level is LogLevel.ERROR
    assert parsed.service == "app.billing"
    assert parsed.message == "Payment transaction declined for order 8812"
    assert parsed.category == "payment"


def test_nul_character_is_removed():
    parsed = text.parse("2026-10-05T14:03:23Z INFO [api] hello\x00world")
    assert parsed is not None
    assert parsed.message == "helloworld"


def test_naive_timestamp_is_assumed_utc():
    parsed = text.parse("2026-10-05 14:03:23 INFO [api] started")
    assert parsed is not None
    assert parsed.timestamp.tzinfo is UTC


def test_long_service_is_truncated():
    parsed = text.parse(f"2026-10-05T14:03:23Z INFO [{'s' * 150}] started")
    assert parsed is not None
    assert parsed.service == "s" * 100


@pytest.mark.parametrize(
    "line",
    [
        "",
        "@@ corrupted line without structure @@",
        "2026-10-05T14:03:23Z LOUD [api] unknown level",
        "2026-13-45T14:03:23Z INFO [api] impossible date",
        "2026-10-05T14:03:23Z INFO",
        "INFO [api] no timestamp",
        "2026-10-05T14:03:23Z [LOUD] [api] unknown bracketed level",
        "2026-10-05T14:03:23Z [INFO [api] unbalanced bracket",
        "2026-10-05 10:00:00,123 - app - LOUD - unknown python level",
        '{"timestamp": "2026-10-05T14:03:23Z", "level": "INFO", "message": "json"}',
    ],
)
def test_rejects_non_matching_lines(line):
    assert text.parse(line) is None
