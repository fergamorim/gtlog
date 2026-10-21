"""Point the test run at a dedicated database so it never wipes dev data.

This runs before any test module imports `app`, so the engine is created
against TEST_DATABASE_URL (default: the `gtlog_test` database on the dev server).
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://gtlog:gtlog@localhost:5432/gtlog_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Tests run polls by hand; the background scheduler would race with them.
os.environ["WATCH_SCHEDULER"] = "false"


def _ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


_ensure_test_database()

# Imported only after DATABASE_URL is set; rebuild the schema so model changes always apply.
from app import models  # noqa: E402, F401
from app.core.database import Base, engine  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ImportJob, ImportStatus, LogEntry  # noqa: E402


@pytest.fixture
def client():
    """API client over an empty database (modules may override this fixture)."""
    with TestClient(app) as c:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE log_watches, log_entries, import_jobs RESTART IDENTITY CASCADE"))
        yield c


@pytest.fixture
def seed():
    """Insert log rows in the given order (ids follow it); rows are dicts of LogEntry fields."""

    def _seed(rows: list[dict], filename: str = "seed.log") -> tuple[int, list[int]]:
        with SessionLocal() as db:
            job = ImportJob(filename=filename, status=ImportStatus.DONE)
            db.add(job)
            db.flush()
            entries = [LogEntry(import_id=job.id, raw=row["message"], **row) for row in rows]
            for entry in entries:
                db.add(entry)
                db.flush()
            db.commit()
            return job.id, [e.id for e in entries]

    return _seed
