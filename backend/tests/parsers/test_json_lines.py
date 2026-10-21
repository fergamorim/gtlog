import json
from datetime import UTC, datetime

import pytest

from app.models.log import LogLevel
from app.parsers import json_lines


def test_parses_generator_line(fixture_lines):
    parsed = json_lines.parse(fixture_lines("app.jsonl")[1])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 22, 950113, tzinfo=UTC)
    assert parsed.level is LogLevel.ERROR
    assert parsed.service == "payments"
    assert parsed.message == "payment 9c2e1f declined"
    assert parsed.category == "payment"


def test_alternative_keys_and_offset(fixture_lines):
    parsed = json_lines.parse(fixture_lines("app.jsonl")[2])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, tzinfo=UTC)
    assert parsed.level is LogLevel.WARNING
    assert parsed.service == "catalog.repo"
    assert parsed.message == "slow query took 2304ms"


def test_epoch_seconds_and_crit_alias(fixture_lines):
    parsed = json_lines.parse(fixture_lines("app.jsonl")[3])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, tzinfo=UTC)
    assert parsed.level is LogLevel.CRITICAL
    assert parsed.service == "player"
    assert parsed.category == "disk"


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (10, LogLevel.DEBUG),
        (20, LogLevel.DEBUG),
        (30, LogLevel.INFO),
        (40, LogLevel.WARNING),
        (50, LogLevel.ERROR),
        (60, LogLevel.CRITICAL),
    ],
)
def test_pino_numeric_levels(level, expected):
    line = json.dumps(
        {
            "level": level,
            "time": 1791209003250,
            "pid": 41,
            "hostname": "api-7d9f",
            "name": "checkout",
            "msg": "request completed",
        }
    )
    parsed = json_lines.parse(line)
    assert parsed is not None
    assert parsed.level is expected


def test_nul_and_lone_surrogate_are_cleaned():
    line = '{"timestamp": "2026-10-05T14:03:23Z", "level": "error", "service": "pay\\u0000ments",'
    line += ' "message": "bad byte \\ud800 in\\u0000 payload"}'
    parsed = json_lines.parse(line)
    assert parsed is not None
    assert parsed.service == "payments"
    assert parsed.message == "bad byte ? in payload"
    parsed.message.encode("utf-8")  # must not raise


def test_epoch_milliseconds():
    parsed = json_lines.parse('{"time": 1791209003250, "level": "info", "msg": "ok"}')
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, 250000, tzinfo=UTC)


def test_missing_level_defaults_to_info_and_nested_service(fixture_lines):
    parsed = json_lines.parse(fixture_lines("app.jsonl")[5])
    assert parsed is not None
    assert parsed.level is LogLevel.INFO
    assert parsed.service == "search"


@pytest.mark.parametrize(
    "line",
    [
        "@@ corrupted line without structure @@",
        '{"timestamp": "2026-10-05T14:03:23Z", "level": "INFO"',
        '["2026-10-05T14:03:23Z", "INFO", "array"]',
        '{"level": "INFO", "message": "no timestamp"}',
        '{"timestamp": "yesterday", "level": "INFO", "message": "bad timestamp"}',
        '{"timestamp": "2026-10-05T14:03:23Z", "level": "LOUD", "message": "bad level"}',
        '{"timestamp": "2026-10-05T14:03:23Z", "level": 35, "message": "unknown numeric level"}',
        '{"timestamp": "2026-10-05T14:03:23Z", "level": true, "message": "boolean level"}',
        '{"timestamp": "2026-10-05T14:03:23Z", "level": "INFO"}',
        '{"timestamp": "2026-10-05T14:03:23Z", "level": "INFO", "message": {"nested": true}}',
        '{"timestamp": 1e300, "level": "INFO", "message": "overflow"}',
        '{"timestamp": NaN, "level": "INFO", "message": "nan"}',
        "[" * 100_000,
        "{" + '"a":' * 1 + "[" * 100_000,
    ],
)
def test_rejects_malformed_lines(line):
    assert json_lines.parse(line) is None


def test_deeply_nested_object_does_not_raise():
    line = '{"a": ' + "[" * 100_000 + "]" * 100_000 + "}"
    assert json_lines.parse(line) is None


def test_generator_output_round_trips():
    ts = datetime(2026, 10, 5, 14, 3, 22, tzinfo=UTC)
    line = json.dumps(
        {
            "timestamp": ts.isoformat(),
            "level": "CRITICAL",
            "service": "player",
            "message": "out of memory in worker 7",
        }
    )
    parsed = json_lines.parse(line)
    assert parsed is not None
    assert parsed.timestamp == ts
    assert parsed.category == "memory"


@pytest.mark.parametrize(
    ("index", "code", "level"),
    [
        (0, 503, LogLevel.CRITICAL),  # no level: it comes from the code
        (1, 503, LogLevel.INFO),  # an explicit level wins over the code
        (2, 401, LogLevel.WARNING),  # statusCode as a string
        (3, 404, LogLevel.WARNING),  # "status": "shipped" is skipped, http_status 404.0 is used
        (4, None, LogLevel.INFO),  # only a non-HTTP status: no code, default level
        (5, 101, LogLevel.DEBUG),  # response_code
        (6, None, LogLevel.INFO),  # 1000 is not an HTTP code
    ],
)
def test_status_code_keys_and_level_fallback(fixture_lines, index, code, level):
    parsed = json_lines.parse(fixture_lines("status.jsonl")[index])
    assert parsed is not None
    assert parsed.status_code == code
    assert parsed.level is level


def test_line_without_status_has_no_code(fixture_lines):
    parsed = json_lines.parse(fixture_lines("app.jsonl")[0])
    assert parsed is not None
    assert parsed.status_code is None


@pytest.mark.parametrize("value", [True, "4o4", 404.5, -1, [404], {"code": 404}])
def test_non_http_status_values_are_ignored(value):
    line = json.dumps({"timestamp": "2026-10-05T14:03:22Z", "status": value, "message": "m"})
    parsed = json_lines.parse(line)
    assert parsed is not None
    assert parsed.status_code is None
    assert parsed.level is LogLevel.INFO
