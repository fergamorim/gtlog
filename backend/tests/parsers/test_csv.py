from datetime import UTC, datetime

import pytest

from app.models.log import LogLevel
from app.parsers import detect_parser
from app.parsers.csv_lines import CsvParser


def parse_all(lines: list[str]):
    parser = CsvParser()
    return parser, [parser.parse(line) for line in lines]


def test_comma_header_is_consumed_and_rows_parse(fixture_lines):
    lines = fixture_lines("app.csv")
    parser, results = parse_all(lines)
    assert results[0] is None
    assert parser.is_header(lines[0])
    assert not parser.is_header(lines[1])

    parsed = results[1]
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 22, 418529, tzinfo=UTC)
    assert parsed.level is LogLevel.INFO
    assert parsed.service == "auth"
    assert parsed.message == "user user42 logged in"
    assert parsed.category == "auth"


def test_quoted_message_with_delimiter_inside(fixture_lines):
    _, results = parse_all(fixture_lines("app.csv"))
    parsed = results[2]
    assert parsed is not None
    assert parsed.level is LogLevel.ERROR
    assert parsed.service == "payments"
    assert parsed.message == "timeout calling catalog, after 15023ms"
    assert parsed.category == "timeout"


def test_doubled_quotes_level_alias_and_offset(fixture_lines):
    _, results = parse_all(fixture_lines("app.csv"))
    parsed = results[3]
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, tzinfo=UTC)
    assert parsed.level is LogLevel.WARNING
    assert parsed.message == 'slow query "orders_by_user" took 2304ms'


def test_epoch_seconds_timestamp(fixture_lines):
    _, results = parse_all(fixture_lines("app.csv"))
    parsed = results[4]
    assert parsed is not None
    assert parsed.timestamp == datetime(2026, 10, 5, 14, 3, 23, tzinfo=UTC)
    assert parsed.level is LogLevel.CRITICAL
    assert parsed.category == "disk"


def test_empty_level_defaults_to_info(fixture_lines):
    _, results = parse_all(fixture_lines("app.csv"))
    parsed = results[5]
    assert parsed is not None
    assert parsed.level is LogLevel.INFO
    assert parsed.category == "database"


def test_bad_rows_are_rejected(fixture_lines):
    _, results = parse_all(fixture_lines("app.csv"))
    assert results[6] is None  # missing column
    assert results[7] is None  # not CSV
    assert results[8] is None  # unknown level


def test_semicolon_delimiter_header_aliases_and_epoch_ms(fixture_lines):
    _, results = parse_all(fixture_lines("app_semicolon.csv"))
    assert results[0] is None

    declined = results[1]
    assert declined is not None
    assert declined.level is LogLevel.ERROR
    assert declined.service == "checkout.api"
    assert declined.message == "card declined; payment 9c2e1f"
    assert declined.category == "payment"

    completed = results[2]
    assert completed is not None
    assert completed.timestamp == datetime(2026, 10, 5, 14, 3, 23, 250000, tzinfo=UTC)
    assert completed.level is LogLevel.INFO

    fatal = results[3]
    assert fatal is not None
    assert fatal.level is LogLevel.CRITICAL
    assert fatal.category == "memory"


def test_tab_delimiter_and_missing_level_column():
    _, results = parse_all(["DateTime\tSource\tMSG", "2026-10-05T14:03:22Z\tnginx\tupstream timed out"])
    parsed = results[1]
    assert parsed is not None
    assert parsed.level is LogLevel.INFO
    assert parsed.service == "nginx"
    assert parsed.message == "upstream timed out"


def test_first_alias_wins_over_later_ones():
    header = "msg,time,message,timestamp"
    _, results = parse_all([header, "short,1791209003,the message,2026-10-05T00:00:00Z"])
    parsed = results[1]
    assert parsed is not None
    assert parsed.message == "the message"
    assert parsed.timestamp == datetime(2026, 10, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    "header",
    [
        "level,service,message",  # no timestamp column
        "2026-10-05T14:03:22Z INFO [auth] user user42 logged in",
        '{"timestamp": "2026-10-05T14:03:22Z", "level": "INFO", "message": "json"}',
        "",
    ],
)
def test_invalid_header_rejects_every_line(header):
    _, results = parse_all([header, "2026-10-05T14:03:22Z,INFO,auth,user logged in"])
    assert results == [None, None]


@pytest.mark.parametrize(
    "row",
    [
        "yesterday,INFO,auth,bad timestamp",
        ",INFO,auth,empty timestamp",
        "2026-10-05T14:03:22Z,INFO,auth,   ",
        "99999999999999999999999,INFO,auth,epoch overflow",
        '2026-10-05T14:03:22Z,INFO,auth,"multi-line fields are not supported',
        '2026-10-05T14:03:22Z,INFO,auth,"quoted"trailing',
        "2026-10-05T14:03:22Z,INFO,auth,too,many,columns",
        "timestamp,level,service,message",  # header repeated
        "x" * 200_000,
    ],
)
def test_rejects_malformed_rows(row):
    _, results = parse_all(["timestamp,level,service,message", row])
    assert results[1] is None


def test_bom_on_header_is_ignored():
    parser, results = parse_all(["﻿timestamp,message", "2026-10-05T14:03:22Z,ok"])
    assert parser.is_header("﻿timestamp,message")
    assert results[1] is not None


def test_detected_parser_still_recognizes_the_header_on_reread(fixture_lines):
    """The importer re-reads the file from the top with the parser chosen by detection."""
    lines = fixture_lines("app.csv")
    parser = detect_parser(lines)
    assert isinstance(parser, CsvParser)
    assert parser.parse(lines[0]) is None
    assert parser.is_header(lines[0])
    assert parser.parse(lines[1]) is not None


def test_incident_export_without_message_column(fixture_lines):
    """ServiceNow-style export: day-first dates, priority scale, assignment group, no message column."""
    lines = fixture_lines("incidents.csv")
    parser, results = parse_all(lines)
    assert results[0] is None and parser.is_header(lines[0])
    parsed = results[1]
    assert parsed is not None
    # sys_updated_at wins over opened_at/sys_created_at: each row is one update of the incident.
    assert parsed.timestamp == datetime(2016, 2, 29, 1, 23, tzinfo=UTC)
    assert parsed.level is LogLevel.WARNING  # priority "3 - Moderate"
    assert parsed.service == "Group 56"
    assert parsed.message.startswith("number=INC0000045 incident_state=New active=true")
    words = parsed.message.split()
    assert not any(w.startswith(("sys_updated_at=", "priority=", "assignment_group=")) for w in words)
    assert "cmdb_ci=" not in parsed.message  # "?" placeholders are dropped
    assert all(result is not None for result in results[1:])


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("1 - Critical", LogLevel.CRITICAL),
        ("2 - High", LogLevel.ERROR),
        ("3 - Moderate", LogLevel.WARNING),
        ("2 - Medium", LogLevel.WARNING),
        ("4 - Low", LogLevel.INFO),
        ("5 - Planning", LogLevel.DEBUG),
        ("?", LogLevel.INFO),
        ("warn", LogLevel.WARNING),
    ],
)
def test_priority_scale_levels(value, level):
    _, results = parse_all(["opened_at,priority,description", f"2026-10-05T14:03:22Z,{value},disk full"])
    assert results[1] is not None
    assert results[1].level is level


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5/3/2016 12:00", datetime(2016, 3, 5, 12, 0, tzinfo=UTC)),
        ("29/2/2016 01:16:09", datetime(2016, 2, 29, 1, 16, 9, tzinfo=UTC)),
        ("05/10/2026", datetime(2026, 10, 5, tzinfo=UTC)),
    ],
)
def test_day_first_dates(value, expected):
    _, results = parse_all(["date,message", f"{value},ok"])
    assert results[1] is not None
    assert results[1].timestamp == expected


@pytest.mark.parametrize("value", ["31/2/2016 10:00", "1/13/2016", "?"])
def test_invalid_day_first_dates_reject_the_row(value):
    _, results = parse_all(["date,message", f"{value},ok"])
    assert results[1] is None


def test_message_built_from_other_columns_skips_empty_values():
    _, results = parse_all(["time,level,host,user,action", "2026-10-05T14:03:22Z,ERROR,web01,,login failed"])
    parsed = results[1]
    assert parsed is not None
    assert parsed.service == "web01"
    assert parsed.message == "action=login failed"


def test_row_with_only_mapped_columns_and_no_message_is_rejected():
    _, results = parse_all(["timestamp,level", "2026-10-05T14:03:22Z,INFO"])
    assert results[1] is None
