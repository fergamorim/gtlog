from datetime import UTC, datetime

import pytest

from app.models.log import LogLevel
from app.parsers import http_access


def test_combined_line_with_offset(fixture_lines):
    parsed = http_access.parse(fixture_lines("access.log")[0])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 22, tzinfo=UTC)
    assert parsed.level is LogLevel.INFO
    assert parsed.service == "http"
    assert parsed.message == "GET /api/catalog?page=2 200 5123B"
    assert parsed.category is None
    assert parsed.status_code == 200


def test_successful_request_gets_no_category():
    parsed = http_access.parse(
        '10.0.0.2 - - [05/Oct/2026:14:03:22 +0000] "POST /api/payments HTTP/1.1" 201 88 "-" "-"'
    )
    assert parsed is not None
    assert parsed.category is None


def test_category_ignores_query_string():
    parsed = http_access.parse(
        '10.0.0.2 - - [05/Oct/2026:14:03:22 +0000] "GET /api/catalog?q=disk+timeout HTTP/1.1" 500 12 "-" "-"'
    )
    assert parsed is not None
    assert parsed.message == "GET /api/catalog?q=disk+timeout 500 12B"
    assert parsed.category is None


def test_lowercase_month_is_accepted():
    parsed = http_access.parse('10.0.0.2 - - [05/oct/2026:14:03:22 +0000] "GET / HTTP/1.1" 200 1 "-" "-"')
    assert parsed is not None
    assert parsed.timestamp.month == 10


def test_bad_gateway_is_critical(fixture_lines):
    parsed = http_access.parse(fixture_lines("access.log")[1])
    assert parsed is not None
    assert parsed.level is LogLevel.CRITICAL
    assert parsed.status_code == 502
    assert parsed.message == "POST /api/payments 502 157B"
    assert parsed.category == "payment"


@pytest.mark.parametrize(
    ("code", "level"),
    [
        (101, LogLevel.DEBUG),
        (204, LogLevel.INFO),
        (401, LogLevel.WARNING),
        (500, LogLevel.ERROR),
        (503, LogLevel.CRITICAL),
        (504, LogLevel.CRITICAL),
    ],
)
def test_level_always_comes_from_the_status_code(code, level):
    parsed = http_access.parse(
        f'10.0.0.2 - - [05/Oct/2026:14:03:22 +0000] "GET /x HTTP/1.1" {code} 1 "-" "-"'
    )
    assert parsed is not None
    assert parsed.status_code == code
    assert parsed.level is level


def test_code_outside_http_range_is_not_stored():
    parsed = http_access.parse('10.0.0.2 - - [05/Oct/2026:14:03:22 +0000] "GET /x HTTP/1.1" 000 0 "-" "-"')
    assert parsed is not None
    assert parsed.status_code is None
    assert parsed.level is LogLevel.INFO


def test_4xx_is_warning_and_dash_size(fixture_lines):
    parsed = http_access.parse(fixture_lines("access.log")[2])
    assert parsed is not None
    assert parsed.level is LogLevel.WARNING
    assert parsed.status_code == 404
    assert parsed.message == "GET /favicon.ico 404 0B"


def test_common_log_format_without_referer_and_agent(fixture_lines):
    parsed = http_access.parse(fixture_lines("access.log")[3])
    assert parsed is not None
    assert parsed.level is LogLevel.INFO
    assert parsed.message == "HEAD / 304 0B"


def test_garbage_request_line_is_kept():
    parsed = http_access.parse('10.0.0.9 - - [05/Oct/2026:14:03:25 +0000] "\\x16\\x03\\x01" 400 157 "-" "-"')
    assert parsed is not None
    assert parsed.level is LogLevel.WARNING
    assert parsed.message == "\\x16\\x03\\x01 400 157B"


@pytest.mark.parametrize(
    "line",
    [
        "@@ corrupted line without structure @@",
        '203.0.113.7 - - [05/Foo/2026:11:03:22 -0300] "GET / HTTP/1.1" 200 5 "-" "-"',
        '203.0.113.7 - - [31/Feb/2026:11:03:22 -0300] "GET / HTTP/1.1" 200 5 "-" "-"',
        '203.0.113.7 - - [05/Oct/2026:11:03:22] "GET / HTTP/1.1" 200 5 "-" "-"',
        '203.0.113.7 - - [05/Oct/2026:11:03:22 -0300] "GET / HTTP/1.1" OK 5 "-" "-"',
        "2026-10-05T14:03:23Z INFO [api] text line",
    ],
)
def test_rejects_malformed_lines(line):
    assert http_access.parse(line) is None
