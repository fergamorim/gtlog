import base64
from datetime import UTC, datetime, timedelta

import pytest

from app.models import LogLevel

BASE = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
INVALID_CURSOR = "Cursor de paginação inválido."


def entry(minutes: int, level: str, service: str | None, category: str | None, message: str) -> dict:
    return {
        "timestamp": BASE + timedelta(minutes=minutes),
        "level": LogLevel(level),
        "service": service,
        "category": category,
        "message": message,
    }


ROWS_A = [
    entry(0, "INFO", "auth", "auth", "user login ok id=1"),
    entry(10, "ERROR", "payments", "timeout", "timeout calling auth after 1234ms"),
    entry(20, "ERROR", "payments", "timeout", "timeout calling auth after 99ms"),
    entry(30, "CRITICAL", "payments", "database", "database connection lost"),
    entry(60, "WARNING", "search", None, "slow query took 800ms"),
    entry(120, "DEBUG", "catalog", None, "memory usage at 91%"),
]
ROWS_B = [
    entry(120, "ERROR", "auth", "timeout", "timeout calling auth after 5ms"),
    entry(300, "INFO", "search", None, "request GET /api completed"),
]


@pytest.fixture
def dataset(client, seed):
    import_a, ids_a = seed(ROWS_A, "a.log")
    import_b, ids_b = seed(ROWS_B, "b.log")
    return {"import_a": import_a, "import_b": import_b, "ids": ids_a + ids_b}


def ids_of(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def make_cursor(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def test_lists_all_newest_first_with_full_items(client, dataset):
    ids = dataset["ids"]
    response = client.get("/logs")
    # Rows 6 and 7 share a timestamp: the higher id comes first.
    assert ids_of(response) == [ids[7], ids[6], ids[5], ids[4], ids[3], ids[2], ids[1], ids[0]]
    body = response.json()
    assert body["next_cursor"] is None
    first = body["items"][0]
    assert first == {
        "id": ids[7],
        "import_id": dataset["import_b"],
        "timestamp": "2026-10-05T15:00:00Z",
        "level": "INFO",
        "service": "search",
        "category": None,
        "message": "request GET /api completed",
        "raw": "request GET /api completed",
    }


def test_combined_filters(client, dataset):
    ids = dataset["ids"]
    params = {"level": ["ERROR", "CRITICAL"], "service": ["payments", "auth"], "category": "timeout"}
    assert ids_of(client.get("/logs", params=params)) == [ids[6], ids[2], ids[1]]

    params["import_id"] = dataset["import_a"]
    assert ids_of(client.get("/logs", params=params)) == [ids[2], ids[1]]

    assert ids_of(client.get("/logs", params={"service": "nope"})) == []


def test_time_range_start_inclusive_end_exclusive(client, dataset):
    ids = dataset["ids"]
    params = {"start": "2026-10-05T10:10:00Z", "end": "2026-10-05T10:30:00Z"}
    assert ids_of(client.get("/logs", params=params)) == [ids[2], ids[1]]
    # Offsets are honoured and a missing offset means UTC.
    params = {"start": "2026-10-05T07:10:00-03:00", "end": "2026-10-05T10:30:00"}
    assert ids_of(client.get("/logs", params=params)) == [ids[2], ids[1]]


def test_start_must_be_before_end(client, dataset):
    response = client.get("/logs", params={"start": "2026-10-05T12:00:00Z", "end": "2026-10-05T12:00:00Z"})
    assert response.status_code == 422
    assert response.json()["detail"] == "A data inicial deve ser anterior à data final."


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"level": "FOO"}, "Valor inválido para o parâmetro 'level'."),
        ({"limit": 0}, "Valor inválido para o parâmetro 'limit'."),
        ({"limit": 501}, "Valor inválido para o parâmetro 'limit'."),
        ({"start": "ontem"}, "Valor inválido para o parâmetro 'start'."),
        ({"import_id": 2**40}, "Valor inválido para o parâmetro 'import_id'."),
        ({"service": "x" * 101}, "Valor inválido para o parâmetro 'service'."),
        ({"service": ["auth", "x" * 101]}, "Valor inválido para o parâmetro 'service'."),
        ({"category": "x" * 51}, "Valor inválido para o parâmetro 'category'."),
        ({"service": [f"s{i}" for i in range(21)]}, "Valor inválido para o parâmetro 'service'."),
        ({"level": ["INFO"] * 21}, "Valor inválido para o parâmetro 'level'."),
        ({"q": "x" * 201}, "Valor inválido para o parâmetro 'q'."),
    ],
)
def test_invalid_params_get_portuguese_detail(client, params, detail):
    response = client.get("/logs", params=params)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}


def test_full_text_search(client, dataset):
    ids = dataset["ids"]
    assert ids_of(client.get("/logs", params={"q": "timeout"})) == [ids[6], ids[2], ids[1]]
    # Service is part of the search vector.
    assert ids_of(client.get("/logs", params={"q": "payments"})) == [ids[3], ids[2], ids[1]]
    # websearch syntax: exclusion and phrases.
    assert ids_of(client.get("/logs", params={"q": "timeout -payments"})) == [ids[6]]
    assert ids_of(client.get("/logs", params={"q": '"connection lost"'})) == [ids[3]]
    assert ids_of(client.get("/logs", params={"q": '"lost connection"'})) == []
    # Combined with a filter.
    assert ids_of(client.get("/logs", params={"q": "timeout", "import_id": dataset["import_b"]})) == [ids[6]]


def test_filter_values_at_the_limits_are_accepted(client, dataset):
    params = {"service": ["x" * 100] * 19 + ["payments"], "category": "y" * 50}
    assert ids_of(client.get("/logs", params=params)) == []
    assert ids_of(client.get("/logs", params={"service": ["x" * 100] * 19 + ["catalog"]})) == [
        dataset["ids"][5]
    ]


def test_plain_words_match_as_prefixes(client, dataset):
    ids = dataset["ids"]
    assert ids_of(client.get("/logs", params={"q": "pay"})) == [ids[3], ids[2], ids[1]]
    assert ids_of(client.get("/logs", params={"q": "TIMEO"})) == [ids[6], ids[2], ids[1]]
    # Every word must match (AND), each as a prefix.
    assert ids_of(client.get("/logs", params={"q": "time call pay"})) == [ids[2], ids[1]]
    assert ids_of(client.get("/logs", params={"q": "time nothinglikethis"})) == []
    # tsquery operators typed by the user are dropped, not interpreted.
    assert ids_of(client.get("/logs", params={"q": "pay & ! | ( :* '"})) == [ids[3], ids[2], ids[1]]


def test_websearch_syntax_is_kept(client, dataset):
    ids = dataset["ids"]
    # A quoted phrase is an exact phrase, so no prefix matching inside it.
    assert ids_of(client.get("/logs", params={"q": '"connection lost"'})) == [ids[3]]
    assert ids_of(client.get("/logs", params={"q": '"connection los"'})) == []
    assert ids_of(client.get("/logs", params={"q": "timeout or database"})) == [
        ids[6],
        ids[3],
        ids[2],
        ids[1],
    ]
    assert ids_of(client.get("/logs", params={"q": "timeout -payments"})) == [ids[6]]


def test_search_without_words_matches_literally(client, dataset):
    ids = dataset["ids"]
    assert ids_of(client.get("/logs", params={"q": "%"})) == [ids[5]]
    assert ids_of(client.get("/logs", params={"q": "/"})) == [ids[7]]
    assert ids_of(client.get("/logs", params={"q": "_"})) == []  # escaped, not a LIKE wildcard
    assert ids_of(client.get("/logs", params={"q": "   "})) == ids_of(client.get("/logs"))


def test_count(client, dataset):
    assert client.get("/logs/count").json() == {"total": 8}
    params = {"level": ["ERROR", "CRITICAL"], "q": "pay", "import_id": dataset["import_a"]}
    assert client.get("/logs/count", params=params).json() == {"total": 3}
    params = {"start": "2026-10-05T10:10:00Z", "end": "2026-10-05T10:30:00Z"}
    assert client.get("/logs/count", params=params).json() == {"total": 2}
    response = client.get(
        "/logs/count", params={"start": "2026-10-06T00:00:00Z", "end": "2026-10-05T00:00:00Z"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "A data inicial deve ser anterior à data final."


def test_cursor_pages_have_no_gaps_or_duplicates_across_ties(client, seed):
    # 23 rows on one timestamp plus neighbours on both sides, so pages split inside the tie.
    rows = [entry(5, "INFO", "auth", None, f"tie {i}") for i in range(23)]
    rows += [entry(0, "INFO", "auth", None, "older"), entry(9, "ERROR", "auth", None, "newer")]
    rows += [entry(5, "ERROR", "auth", None, "tie error")]
    _, ids = seed(rows)
    expected = [ids[24], ids[25], *reversed(ids[:23]), ids[23]]

    for limit in (1, 4, 7, 26, 100):
        seen, cursor, pages = [], None, 0
        while True:
            params = {"limit": limit} | ({"cursor": cursor} if cursor else {})
            response = client.get("/logs", params=params)
            page = ids_of(response)
            assert len(page) <= limit
            seen += page
            pages += 1
            cursor = response.json()["next_cursor"]
            if cursor is None:
                break
        assert seen == expected, limit
        assert pages == -(-len(expected) // limit)

    # Cursor keeps working with filters applied.
    seen, cursor = [], None
    while True:
        response = client.get(
            "/logs", params={"level": "INFO", "limit": 5} | ({"cursor": cursor} if cursor else {})
        )
        seen += ids_of(response)
        cursor = response.json()["next_cursor"]
        if cursor is None:
            break
    assert seen == [*reversed(ids[:23]), ids[23]]


def test_last_full_page_has_no_cursor(client, dataset):
    response = client.get("/logs", params={"limit": 8})
    assert len(ids_of(response)) == 8
    assert response.json()["next_cursor"] is None


@pytest.mark.parametrize(
    "cursor",
    [
        "garbage!!",
        "@@@",
        make_cursor("no separator"),
        make_cursor("not-a-date|5"),
        make_cursor("2026-10-05T10:00:00|5"),  # no offset
        make_cursor("2026-10-05T10:00:00+00:00|0"),
        make_cursor("2026-10-05T10:00:00+00:00|abc"),
        make_cursor(f"2026-10-05T10:00:00+00:00|{2**63}"),
        base64.urlsafe_b64encode(b"\xff\xfe|1").decode(),
    ],
)
def test_invalid_cursor(client, dataset, cursor):
    response = client.get("/logs", params={"cursor": cursor})
    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_CURSOR}


def test_get_one_log(client, dataset):
    entry_id = dataset["ids"][3]
    response = client.get(f"/logs/{entry_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "database connection lost"
    assert response.json()["level"] == "CRITICAL"


@pytest.mark.parametrize("entry_id", [999999, 0, 2**70])
def test_get_missing_log_returns_404(client, dataset, entry_id):
    response = client.get(f"/logs/{entry_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Registro de log não encontrado."}


def test_facets(client, dataset):
    response = client.get("/logs/facets")
    assert response.status_code == 200
    assert response.json() == {
        "services": ["auth", "catalog", "payments", "search"],
        "categories": ["auth", "database", "timeout"],
    }


def test_empty_dataset(client):
    assert client.get("/logs").json() == {"items": [], "next_cursor": None}
    assert client.get("/logs/facets").json() == {"services": [], "categories": []}
    assert client.get("/logs/count").json() == {"total": 0}
