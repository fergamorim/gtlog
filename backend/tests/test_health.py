from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.core.database import engine
from app.main import app


def test_health_reports_ok():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_adds_columns_missing_from_an_older_database(client):
    """A pgdata volume from an earlier version lacks import_jobs.format and log_entries.status_code
    (with its index); startup must add them."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE import_jobs DROP COLUMN format"))
        conn.execute(text("ALTER TABLE log_entries DROP COLUMN status_code"))  # also drops ix_log_status_ts
    assert "ix_log_status_ts" not in {i["name"] for i in inspect(engine).get_indexes("log_entries")}
    with TestClient(app) as restarted:
        assert restarted.get("/imports").status_code == 200
        assert restarted.get("/logs", params={"status": "4xx"}).status_code == 200
    db = inspect(engine)
    assert "format" in {c["name"] for c in db.get_columns("import_jobs")}
    assert "status_code" in {c["name"] for c in db.get_columns("log_entries")}
    assert "ix_log_status_ts" in {i["name"] for i in db.get_indexes("log_entries")}
