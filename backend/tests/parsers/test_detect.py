import subprocess
import sys
from datetime import UTC
from pathlib import Path

import pytest

from app.parsers import all_parsers, detect_parser
from app.parsers.syslog import SyslogParser


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [("app.log", "text"), ("app.jsonl", "json"), ("access.log", "http"), ("syslog.log", "syslog"),
     ("app.csv", "csv"), ("app_semicolon.csv", "csv")],
)
def test_detects_fixture_format(fixture_lines, fixture, expected):
    parser = detect_parser(fixture_lines(fixture))
    assert parser is not None
    assert parser.name == expected


def test_majority_wins_over_minority_format(fixture_lines):
    sample = fixture_lines("app.log") + fixture_lines("app.jsonl")[:2]
    parser = detect_parser(sample)
    assert parser is not None
    assert parser.name == "text"


@pytest.mark.parametrize("sample", [[], ["", "   "], ["@@ corrupted line without structure @@", "hello"]])
def test_returns_none_when_nothing_parses(sample):
    assert detect_parser(sample) is None


def test_each_detection_gets_a_fresh_syslog_parser(fixture_lines):
    first = detect_parser(fixture_lines("syslog.log"))
    second = detect_parser(fixture_lines("syslog.log"))
    assert isinstance(first, SyslogParser) and isinstance(second, SyslogParser)
    assert first is not second


def test_parser_names_are_unique():
    names = [p.name for p in all_parsers()]
    assert len(names) == len(set(names))


GENERATOR = Path(__file__).resolve().parents[3] / "scripts" / "generate_logs.py"


@pytest.mark.parametrize("fmt", ["text", "json", "csv"])
def test_generator_output_is_detected_and_parsed(tmp_path, fmt):
    out = tmp_path / f"sample.{fmt}"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--lines", "2000", "--format", fmt, "--invalid-ratio", "0.01",
         "--out", str(out)],
        check=True, capture_output=True,
    )
    lines = out.read_text(encoding="utf-8").splitlines()
    parser = detect_parser(lines[:200])
    assert parser is not None
    assert parser.name == fmt

    results = [parser.parse(line) for line in lines]
    is_header = getattr(parser, "is_header", None)
    headers = [i for i, line in enumerate(lines) if is_header and is_header(line)]
    assert headers == ([0] if fmt == "csv" else [])
    results = [r for i, r in enumerate(results) if i not in headers]
    corrupted = sum(line.startswith("@@") for line in lines)
    assert corrupted > 0
    assert sum(r is None for r in results) == corrupted
    assert all(r.timestamp.tzinfo is UTC for r in results if r is not None)
    categories = {r.category for r in results if r is not None}
    assert categories >= {"timeout", "database", "auth", "payment", "memory", "disk"}
