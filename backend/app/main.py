from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.schema import CreateIndex

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.logs import router as logs_router
from app.api.stats import router as stats_router
from app.core.config import get_settings
from app.core.database import Base, engine

# Columns added after the first release. create_all skips existing tables, so a database created by an
# older version (a kept `pgdata` volume) would otherwise fail every query that selects them.
_ADDED_COLUMNS = (
    "ALTER TABLE import_jobs ADD COLUMN IF NOT EXISTS format VARCHAR(30)",
    "ALTER TABLE log_entries ADD COLUMN IF NOT EXISTS status_code SMALLINT",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Demo bootstrap; a real deployment would manage schema and indexes with migrations (Alembic).
    Base.metadata.create_all(bind=engine)
    # create_all skips existing tables, so add indexes introduced later. IF NOT EXISTS (instead of
    # check-then-create) keeps concurrent workers from failing with DuplicateTable.
    with engine.begin() as conn:
        for statement in _ADDED_COLUMNS:
            conn.execute(text(statement))
        for table in Base.metadata.sorted_tables:
            for index in table.indexes:
                conn.execute(CreateIndex(index, if_not_exists=True))
    yield


app = FastAPI(title="GTLog API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Replace FastAPI's English error list with a single Portuguese message naming the field."""
    error = exc.errors()[0] if exc.errors() else {}
    # loc looks like ("query", "level", 0): report the parameter name, not the list index.
    field = next((part for part in reversed(error.get("loc", ())) if isinstance(part, str)), "?")
    if error.get("type") == "missing":
        detail = f"Parâmetro obrigatório ausente: '{field}'."
    else:
        detail = f"Valor inválido para o parâmetro '{field}'."
    return JSONResponse(status_code=422, content={"detail": detail})


app.include_router(health_router)
app.include_router(imports_router)
app.include_router(logs_router)
app.include_router(stats_router)
