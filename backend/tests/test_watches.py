import hashlib
import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import LogEntry, LogWatch
from app.services import watcher

LINES = [
    "2026-10-05T17:46:57+00:00 DEBUG [catalog] cache lookup key=7248ad",
    "2026-10-05T18:07:06+00:00 INFO [search] request GET /api/payments completed in 7169ms",
    "2026-10-05T18:27:16+00:00 ERROR [payments] database connection timeout after 30s",
    "2026-10-05T18:47:26+00:00 WARNING [player] memory usage at 91%",
]


@pytest.fixture
def root(tmp_path, monkeypatch):
    folder = tmp_path / "watch"
    folder.mkdir()
    monkeypatch.setattr(get_settings(), "watch_root", str(folder))
    return folder


def write(path, lines, mode="a"):
    with open(path, mode, encoding="utf-8") as fh:
        fh.write("".join(line + "\n" for line in lines))


def create(client, path="app.log", interval=5, **extra):
    return client.post("/watches", json={"path": path, "interval_seconds": interval, **extra})


def poll(watch_id):
    watcher.poll_watch(watch_id)
    with SessionLocal() as db:
        return db.get(LogWatch, watch_id)


def raws(import_id):
    with SessionLocal() as db:
        stmt = select(LogEntry.raw).where(LogEntry.import_id == import_id).order_by(LogEntry.id)
        return list(db.scalars(stmt))


def test_first_poll_imports_the_file_and_later_polls_only_new_lines(client, root):
    write(root / "app.log", LINES[:2], "w")
    created = create(client)
    assert created.status_code == 201
    body = created.json()
    assert body["path"] == "app.log"
    assert body["active"] is True

    watch = poll(body["id"])
    assert raws(body["import_id"]) == LINES[:2]
    assert watch.format == "text"
    assert watch.offset == os.path.getsize(root / "app.log")
    assert watch.last_checked_at is not None
    assert watch.next_check_at > watch.last_checked_at

    poll(body["id"])  # nothing new
    write(root / "app.log", LINES[2:])
    poll(body["id"])
    assert raws(body["import_id"]) == LINES

    job = client.get(f"/imports/{body['import_id']}").json()
    assert job["status"] == "DONE"
    assert job["parsed_lines"] == 4
    assert job["format"] == "text"
    listed = client.get("/watches").json()
    assert listed[0]["parsed_lines"] == 4
    assert client.get(f"/logs?import_id={body['import_id']}").json()["items"]


def test_critical_lines_are_counted_with_the_latest_message(client, root):
    write(root / "app.log", LINES, "w")
    body = create(client).json()
    assert body["critical_lines"] == 0
    assert body["last_critical_message"] is None

    poll(body["id"])
    assert client.get(f"/watches/{body['id']}").json()["critical_lines"] == 0

    write(root / "app.log", [
        "2026-10-05T19:00:00+00:00 CRITICAL [payments] disk full on /var/lib/db",
        "2026-10-05T19:00:01+00:00 INFO [search] request ok",
        "2026-10-05T19:00:02+00:00 CRITICAL [auth] token signing key missing",
    ])
    poll(body["id"])
    out = client.get(f"/watches/{body['id']}").json()
    assert out["critical_lines"] == 2
    assert out["last_critical_message"] == "token signing key missing"
    assert out["last_critical_at"] == "2026-10-05T19:00:02Z"

    write(root / "app.log", ["2026-10-05T19:01:00+00:00 ERROR [auth] retry failed"])
    poll(body["id"])
    out = client.get("/watches").json()[0]
    assert out["critical_lines"] == 2
    assert out["last_critical_message"] == "token signing key missing"


def test_partial_last_line_waits_for_its_line_break(client, root):
    path = root / "app.log"
    write(path, LINES[:1], "w")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(LINES[1][:20])
    watch_id = create(client).json()["id"]

    watch = poll(watch_id)
    assert raws(watch.import_id) == LINES[:1]

    with open(path, "a", encoding="utf-8") as fh:
        fh.write(LINES[1][20:] + "\n")
    poll(watch_id)
    assert raws(watch.import_id) == LINES[:2]


def test_truncated_file_is_read_from_the_start(client, root):
    path = root / "app.log"
    write(path, LINES, "w")
    watch_id = create(client).json()["id"]
    watch = poll(watch_id)

    write(path, LINES[3:], "w")  # smaller than the offset
    poll(watch_id)
    assert raws(watch.import_id) == LINES + LINES[3:]


def test_rotated_file_is_read_from_the_start(client, root):
    path = root / "app.log"
    write(path, LINES[:2], "w")
    watch_id = create(client).json()["id"]
    watch = poll(watch_id)

    os.rename(path, root / "app.log.1")
    write(path, LINES[1:], "w")  # new inode, bigger than the old offset
    poll(watch_id)
    assert raws(watch.import_id) == LINES[:2] + LINES[1:]


def test_missing_file_is_reported_and_picked_up_again(client, root):
    path = root / "app.log"
    write(path, LINES[:1], "w")
    watch_id = create(client).json()["id"]
    poll(watch_id)

    os.remove(path)
    watch = poll(watch_id)
    assert watch.last_error == "Arquivo não encontrado: app.log."
    assert watch.active is True

    write(path, LINES[1:2], "w")
    watch = poll(watch_id)
    assert watch.last_error is None
    assert raws(watch.import_id) == LINES[:2]


def test_start_at_end_skips_existing_content(client, root):
    write(root / "app.log", LINES[:2], "w")
    watch_id = create(client, start_at_end=True).json()["id"]
    watch = poll(watch_id)
    assert raws(watch.import_id) == []

    write(root / "app.log", LINES[2:])
    poll(watch_id)
    assert raws(watch.import_id) == LINES[2:]


def test_start_at_end_keeps_a_partial_last_line_for_later(client, root):
    path = root / "app.log"
    write(path, LINES[:1], "w")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(LINES[1][:20])
    watch_id = create(client, start_at_end=True).json()["id"]

    with open(path, "a", encoding="utf-8") as fh:
        fh.write(LINES[1][20:] + "\n")
    watch = poll(watch_id)
    assert raws(watch.import_id) == LINES[1:2]


def test_shorter_interval_is_applied_from_the_last_read(client, root):
    write(root / "app.log", LINES[:1], "w")
    watch_id = create(client, interval=86_400).json()["id"]
    watch = poll(watch_id)
    response = client.patch(f"/watches/{watch_id}", json={"interval_seconds": 5})
    assert response.status_code == 200
    with SessionLocal() as db:
        assert db.get(LogWatch, watch_id).next_check_at == watch.last_checked_at + timedelta(seconds=5)


def test_csv_header_applies_to_every_poll(client, root):
    path = root / "app.csv"
    path.write_text("timestamp,level,service,message\n2026-10-05T14:03:22Z,ERROR,payments,timeout\n")
    watch_id = create(client, path="app.csv").json()["id"]
    watch = poll(watch_id)
    assert watch.format == "csv"

    with open(path, "a") as fh:
        fh.write("2026-10-05T14:04:00Z,INFO,auth,login ok\n")
    poll(watch_id)
    job = client.get(f"/imports/{watch.import_id}").json()
    assert job["parsed_lines"] == 2
    assert job["invalid_lines"] == 0


def test_format_waits_for_a_complete_first_line(client, root):
    # A CSV header still being written must not be learned half cut.
    path = root / "app.csv"
    path.write_text("timestamp,level,serv")
    watch_id = create(client, path="app.csv").json()["id"]
    watch = poll(watch_id)
    assert watch.format is None
    assert watch.header is None
    assert watch.offset == 0

    with open(path, "a") as fh:
        fh.write("ice,message\n2026-10-05T14:03:22Z,ERROR,payments,timeout\n")
    watch = poll(watch_id)
    assert watch.format == "csv"
    assert watch.header == "timestamp,level,service,message"
    with SessionLocal() as db:
        entry = db.scalar(select(LogEntry).where(LogEntry.import_id == watch.import_id))
    assert (entry.service, entry.message) == ("payments", "timeout")


def test_head_fingerprint_matches_the_imported_bytes(client, root):
    write(root / "app.log", LINES[:2], "w")
    watch = poll(create(client).json()["id"])
    content = (root / "app.log").read_bytes()
    assert watch.head_size == len(content)
    assert watch.head_digest == hashlib.sha256(content).hexdigest()


def test_unrecognized_format_keeps_the_offset(client, root):
    write(root / "app.log", ["%%% garbage %%%"], "w")
    watch_id = create(client).json()["id"]
    watch = poll(watch_id)
    assert watch.last_error == "Formato de log não reconhecido."
    assert watch.offset == 0


def test_backlog_bigger_than_one_poll_is_due_again_right_away(client, root, monkeypatch):
    monkeypatch.setattr(watcher, "MAX_POLL_BYTES", len(LINES[0]) + 1)
    write(root / "app.log", LINES, "w")
    watch_id = create(client, interval=600).json()["id"]
    watch = poll(watch_id)
    assert raws(watch.import_id) == LINES[:1]
    assert watch.next_check_at <= datetime.now(UTC)


def test_paused_watch_is_not_polled_or_due(client, root):
    write(root / "app.log", LINES[:1], "w")
    watch_id = create(client).json()["id"]
    response = client.patch(f"/watches/{watch_id}", json={"active": False, "interval_seconds": 60})
    assert response.status_code == 200
    assert response.json()["active"] is False
    assert response.json()["interval_seconds"] == 60

    watch = poll(watch_id)
    assert raws(watch.import_id) == []
    with SessionLocal() as db:
        assert watcher.due_watch_ids(db, datetime.now(UTC) + timedelta(days=2)) == []


def test_due_watch_ids_follow_next_check_at(client, root):
    write(root / "app.log", LINES[:1], "w")
    watch_id = create(client, interval=30).json()["id"]
    now = datetime.now(UTC)
    with SessionLocal() as db:
        assert watcher.due_watch_ids(db, now) == [watch_id]
    poll(watch_id)
    with SessionLocal() as db:
        assert watcher.due_watch_ids(db, now + timedelta(seconds=5)) == []
        assert watcher.due_watch_ids(db, now + timedelta(seconds=31)) == [watch_id]


@pytest.mark.parametrize("path", ["../secret.log", "/etc/passwd", "sub/../../secret.log"])
def test_paths_outside_the_root_are_rejected(client, root, path):
    (root.parent / "secret.log").write_text(LINES[0] + "\n")
    response = create(client, path=path)
    assert response.status_code == 422
    assert "pasta observável" in response.json()["detail"]


def test_symlink_leaving_the_root_is_rejected(client, root):
    (root.parent / "secret.log").write_text(LINES[0] + "\n")
    os.symlink(root.parent / "secret.log", root / "link.log")
    assert create(client, path="link.log").status_code == 422


def test_absolute_path_inside_the_root_is_accepted(client, root):
    write(root / "app.log", LINES[:1], "w")
    response = create(client, path=str(root / "app.log"))
    assert response.status_code == 201
    assert response.json()["path"] == "app.log"


def test_create_rejects_missing_binary_and_duplicate(client, root):
    assert create(client, path="nope.log").status_code == 404
    (root / "bin.log").write_bytes(b"\x00\x01\x02")
    assert create(client, path="bin.log").status_code == 415
    write(root / "app.log", LINES[:1], "w")
    assert create(client).status_code == 201
    duplicate = create(client)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Este arquivo já está sendo observado."


def test_database_refuses_a_second_active_watch_of_a_file(client, root):
    # Two simultaneous requests both pass the SELECT check; the unique index stops the second commit.
    write(root / "app.log", LINES[:1], "w")
    first = create(client).json()
    with SessionLocal() as db:
        db.add(LogWatch(path="app.log", interval_seconds=5, active=True, import_id=first["import_id"]))
        with pytest.raises(watcher.WatchRejected) as rejected:
            watcher._commit_unique(db)
    assert rejected.value.status_code == 409
    assert len(client.get("/watches").json()) == 1

    # A paused watch does not count: the same file can be watched again, but not resumed twice.
    assert client.patch(f"/watches/{first['id']}", json={"active": False}).status_code == 200
    second = create(client)
    assert second.status_code == 201
    assert client.patch(f"/watches/{first['id']}", json={"active": True}).status_code == 409


@pytest.mark.parametrize("interval", [0, 86_401])
def test_interval_bounds(client, root, interval):
    write(root / "app.log", LINES[:1], "w")
    response = create(client, interval=interval)
    assert response.status_code == 422
    assert "interval_seconds" in response.json()["detail"]


def test_delete_stops_watching_and_keeps_logs(client, root):
    write(root / "app.log", LINES[:2], "w")
    body = create(client).json()
    poll(body["id"])
    assert client.delete(f"/watches/{body['id']}").status_code == 204
    assert client.get(f"/watches/{body['id']}").status_code == 404
    assert raws(body["import_id"]) == LINES[:2]


def test_settings_expose_the_root_and_bounds(client, root):
    body = client.get("/watches/settings").json()
    assert body == {
        "root": os.path.realpath(root),
        "host_root": None,
        "min_interval_seconds": 1,
        "max_interval_seconds": 86_400,
    }


def test_full_host_path_is_translated_to_the_root(client, root, monkeypatch):
    monkeypatch.setattr(get_settings(), "watch_host_root", "/Users/ana/kaggle/")
    (root / "sub").mkdir()
    write(root / "sub" / "data.log", LINES[:1], "w")
    response = create(client, path="/Users/ana/kaggle/sub/data.log")
    assert response.status_code == 201
    assert response.json()["path"] == "sub/data.log"
    assert client.get("/watches/settings").json()["host_root"] == "/Users/ana/kaggle"
    outside = create(client, path="/Users/ana/other/data.log")
    assert outside.status_code == 422
    assert "/Users/ana/kaggle" in outside.json()["detail"]


def test_files_lists_folders_first_and_hides_dotfiles(client, root):
    (root / "logs").mkdir()
    write(root / "logs" / "api.log", LINES[:1], "w")
    write(root / "b.log", LINES[:2], "w")
    write(root / "A.csv", LINES[:1], "w")
    (root / ".hidden").write_text("x")

    body = client.get("/watches/files").json()
    assert body["path"] == ""
    assert body["parent"] is None
    listed = [(e["name"], e["is_dir"]) for e in body["entries"]]
    assert listed == [("logs", True), ("A.csv", False), ("b.log", False)]
    assert body["entries"][2]["size"] == os.path.getsize(root / "b.log")

    inner = client.get("/watches/files", params={"path": "logs"}).json()
    assert inner["parent"] == ""
    assert [e["path"] for e in inner["entries"]] == ["logs/api.log"]
    assert create(client, path=inner["entries"][0]["path"]).status_code == 201


def test_files_stops_at_the_limit_after_sorting(client, root, monkeypatch):
    monkeypatch.setattr(watcher, "LIST_FOLDER_LIMIT", 2)
    for name in ("c.log", "a.log", "b.log"):
        write(root / name, LINES[:1], "w")
    (root / "zz").mkdir()
    body = client.get("/watches/files").json()
    assert [e["name"] for e in body["entries"]] == ["zz", "a.log"]
    assert body["entries"][1]["size"] == os.path.getsize(root / "a.log")


@pytest.mark.parametrize(("path", "status"), [("..", 422), ("/etc", 422), ("nope", 404), ("b.log", 404)])
def test_files_rejects_folders_outside_or_missing(client, root, path, status):
    write(root / "b.log", LINES[:1], "w")
    assert client.get("/watches/files", params={"path": path}).status_code == status
