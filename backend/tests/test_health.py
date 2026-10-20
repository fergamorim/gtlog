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
    """A pgdata volume from an earlier version lacks import_jobs.format; startup must add it."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE import_jobs DROP COLUMN format"))
    with TestClient(app) as restarted:
        response = restarted.get("/imports")
    assert response.status_code == 200
    assert "format" in {c["name"] for c in inspect(engine).get_columns("import_jobs")}
