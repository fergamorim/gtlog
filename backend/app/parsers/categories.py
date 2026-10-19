"""Keyword table that maps a log message to a category.

Rules are checked top to bottom and the first match wins, so more specific
symptoms (a timeout) come before the subsystem they happened in (payments).
Keywords are whole words or phrases, case-insensitive; a trailing ``*``
also accepts longer words ("timeout*" matches "timeouts", "auth" does not
match "author").
"""

import re

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("timeout", ("timeout*", "timed out", "deadline exceeded")),
    ("memory", ("out of memory", "outofmemory*", "oom", "oomkill*", "memory", "heap")),
    ("disk", ("disk*", "no space left", "filesystem*", "inode*", "i/o error")),
    ("database", (
        "database*", "db", "sql", "sqlalchemy", "sqlstate", "mysql", "postgres*",
        "query", "queries", "deadlock*",
    )),
    ("auth", (
        "auth", "authenticat*", "authoriz*", "unauthori*", "forbidden", "login*", "logged in",
        "logout", "logged out", "token", "tokens", "password*", "credential*", "jwt",
        "session expired", "permission denied",
    )),
    ("payment", ("payment*", "charge", "charged", "chargeback*", "refund*", "invoice*", "billing",
                 "card declined")),
    ("network", (
        "connection reset", "connection refused", "network*", "unreachable", "dns",
        "socket*", "tls", "ssl", "econnrefused", "econnreset",
    )),
]


def _keyword_pattern(keyword: str) -> str:
    if keyword.endswith("*"):
        return re.escape(keyword[:-1]) + r"\w*"
    return re.escape(keyword)


_COMPILED: list[tuple[str, re.Pattern[str]]] = [
    (category, re.compile(r"\b(?:" + "|".join(map(_keyword_pattern, keywords)) + r")\b", re.IGNORECASE))
    for category, keywords in CATEGORY_RULES
]


def classify_category(message: str) -> str | None:
    """Return the first category whose keywords appear in the message, or None."""
    for category, pattern in _COMPILED:
        if pattern.search(message):
            return category
    return None
