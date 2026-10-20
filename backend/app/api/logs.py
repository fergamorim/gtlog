from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import Facets, LogCount, LogEntryOut, LogFiltersDep, LogPage
from app.core.database import DbSession
from app.services import log_query

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=LogPage)
def list_logs(
    filters: LogFiltersDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> LogPage:
    try:
        items, next_cursor = log_query.list_logs(db, filters, limit, cursor)
    except log_query.InvalidCursor:
        raise HTTPException(status_code=422, detail="Cursor de paginação inválido.") from None
    return LogPage(items=[LogEntryOut.model_validate(e) for e in items], next_cursor=next_cursor)


# Declared before /{entry_id} so "count" and "facets" are not parsed as ids.
@router.get("/count", response_model=LogCount)
def count_logs(filters: LogFiltersDep, db: DbSession) -> LogCount:
    return LogCount(total=log_query.count_logs(db, filters))


@router.get("/facets", response_model=Facets)
def get_facets(db: DbSession) -> Facets:
    return Facets(**log_query.facets(db))


@router.get("/{entry_id}", response_model=LogEntryOut)
def get_log(entry_id: int, db: DbSession) -> LogEntryOut:
    entry = log_query.get_log(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Registro de log não encontrado.")
    return LogEntryOut.model_validate(entry)
