from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.logs import router as logs_router
from app.api.stats import router as stats_router
from app.core.config import get_settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    # create_all skips existing tables; add indexes introduced after the table was first created.
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)
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
