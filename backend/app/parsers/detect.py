"""Pick the parser that understands most of a file's first lines."""

from collections.abc import Iterable

from app.parsers import csv_lines, http_access, json_lines, syslog, text
from app.parsers.base import LineParser


def all_parsers() -> tuple[LineParser, ...]:
    """Fresh parser instances, most specific first (an earlier format wins a tie).

    Fresh because some parsers hold per-file state (syslog's reference year, the CSV header).
    """
    return (json_lines, syslog.SyslogParser(), http_access, csv_lines.CsvParser(), text)


def detect_parser(sample_lines: Iterable[str]) -> LineParser | None:
    """Return the parser with the most successful parses over the non-blank sample lines.

    Returns None when no parser accepts a single line. The returned parser is
    meant to be used for the rest of that file.
    """
    lines = [line for line in sample_lines if line.strip()]
    best: LineParser | None = None
    best_hits = 0
    for parser in all_parsers():
        hits = sum(1 for line in lines if parser.parse(line) is not None)
        if hits > best_hits:
            best, best_hits = parser, hits
    return best
