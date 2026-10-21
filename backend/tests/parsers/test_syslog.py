from datetime import UTC, datetime

import pytest

from app.models.log import LogLevel
from app.parsers import syslog


@pytest.fixture
def parser():
    return syslog.SyslogParser(now=datetime(2026, 10, 19, 12, 0, tzinfo=UTC))


def test_rfc3164_with_pri(fixture_lines, parser):
    parsed = parser.parse(fixture_lines("syslog.log")[0])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 22, tzinfo=UTC)
    assert parsed.level is LogLevel.CRITICAL  # <34> = auth.crit
    assert parsed.service == "sshd"
    assert parsed.message == "Failed password for root from 10.0.0.5 port 52144 ssh2"
    assert parsed.category == "auth"


def test_rfc5424_with_structured_data(fixture_lines):
    parsed = syslog.parse(fixture_lines("syslog.log")[1])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 22, 3000, tzinfo=UTC)
    assert parsed.level is LogLevel.INFO  # <165> = local4.notice
    assert parsed.service == "nginx"
    assert parsed.message == "upstream timed out while reading response header"
    assert parsed.category == "timeout"


def test_rfc5424_offset_and_error_severity(fixture_lines):
    parsed = syslog.parse(fixture_lines("syslog.log")[2])
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, tzinfo=UTC)
    assert parsed.level is LogLevel.ERROR  # <11> = user.err
    assert parsed.service == "postgres"
    assert parsed.category == "database"


def test_rfc3164_without_pri_defaults_to_info(fixture_lines, parser):
    parsed = parser.parse(fixture_lines("syslog.log")[3])
    assert parsed is not None
    assert parsed.level is LogLevel.INFO
    assert parsed.service == "kernel"
    assert parsed.category == "memory"


def test_rfc3164_debug_severity(fixture_lines, parser):
    parsed = parser.parse(fixture_lines("syslog.log")[4])
    assert parsed is not None
    assert parsed.level is LogLevel.DEBUG  # <191> = local7.debug
    assert parsed.service == "CRON"
    assert parsed.timestamp == datetime(2026, 10, 15, 14, 3, 25, tzinfo=UTC)


def test_rfc3164_assumes_current_year():
    parsed = syslog.parse("<13>Jan  2 03:04:05 host app: hello")
    assert parsed is not None
    assert parsed.timestamp.year in (datetime.now(UTC).year, datetime.now(UTC).year - 1)
    assert parsed.timestamp.tzinfo is UTC


def test_rfc3164_future_date_rolls_back_a_year():
    parser = syslog.SyslogParser(now=datetime(2027, 1, 2, 8, 0, tzinfo=UTC))
    parsed = parser.parse("<30>Dec 31 23:59:59 host backup[77]: nightly backup finished")
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)


def test_reference_time_is_fixed_per_parser_instance():
    parser = syslog.SyslogParser()
    first = parser.parse("<13>Oct  5 14:03:22 host app: one")
    reference = parser.now
    second = parser.parse("<13>Oct  5 14:03:23 host app: two")
    assert parser.now is reference
    assert first is not None and second is not None
    assert first.timestamp.year == second.timestamp.year


def test_month_is_case_insensitive(parser):
    parsed = parser.parse("<13>OCT  5 14:03:22 host app: shouting month")
    assert parsed is not None
    assert parsed.timestamp.month == 10


def test_parser_satisfies_protocol_name():
    assert syslog.SyslogParser().name == "syslog"


@pytest.mark.parametrize(
    ("pri", "level"),
    [
        (0, LogLevel.CRITICAL),
        (1, LogLevel.CRITICAL),
        (2, LogLevel.CRITICAL),
        (3, LogLevel.ERROR),
        (4, LogLevel.WARNING),
        (5, LogLevel.INFO),
        (6, LogLevel.INFO),
        (7, LogLevel.DEBUG),
        (86, LogLevel.INFO),  # authpriv.info
    ],
)
def test_severity_mapping(pri, level):
    parsed = syslog.parse(f"<{pri}>1 2026-10-05T14:03:22Z host app - - - message")
    assert parsed is not None
    assert parsed.level is level


def test_rfc5424_nil_app_name_and_bom():
    parsed = syslog.parse("<14>1 2026-10-05T14:03:22Z host - - - - \ufeffhello")
    assert parsed is not None
    assert parsed.service is None
    assert parsed.message == "hello"


@pytest.mark.parametrize(
    "line",
    [
        "@@ corrupted line without structure @@",
        "<999>1 2026-10-05T14:03:22Z host app - - - pri out of range",
        "<14>1 - host app - - - nil timestamp",
        "<14>1 not-a-date host app - - - bad timestamp",
        "<14>1 2026-10-05T14:03:22Z host app - - -",
        "<13>Foo  5 14:03:22 host app: bad month",
        "<13>Oct 45 14:03:22 host app: bad day",
        "<13>Feb 30 14:03:22 host app: impossible date",
        "2026-10-05T14:03:23Z INFO [api] text line",
    ],
)
def test_rejects_malformed_lines(line):
    assert syslog.parse(line) is None


@pytest.mark.parametrize(
    ("index", "code", "level"),
    [
        (0, 500, LogLevel.INFO),  # PRI severity wins over the code
        (1, 503, LogLevel.CRITICAL),  # no PRI: the level comes from the code
        (2, 503, LogLevel.INFO),
        (3, None, LogLevel.INFO),  # no PRI and no code
    ],
)
def test_status_code_from_message(parser, fixture_lines, index, code, level):
    parsed = parser.parse(fixture_lines("status_syslog.log")[index])
    assert parsed is not None
    assert parsed.status_code == code
    assert parsed.level is level
