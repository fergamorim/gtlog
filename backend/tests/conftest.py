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
