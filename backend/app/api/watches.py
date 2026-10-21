from fastapi import APIRouter, HTTPException, Response, status

from app.api.schemas import LogWatchIn, LogWatchOut, LogWatchUpdate, WatchSettingsOut
from app.core.database import DbSession
from app.models import ImportJob, LogWatch
from app.services import watcher

router = APIRouter(prefix="/watches", tags=["watches"])


def _out(db: DbSession, watch: LogWatch) -> LogWatchOut:
    job = db.get(ImportJob, watch.import_id)
    return LogWatchOut(
        id=watch.id,
        path=watch.path,
        interval_seconds=watch.interval_seconds,
        active=watch.active,
        import_id=watch.import_id,
        format=watch.format,
        offset=watch.offset,
        parsed_lines=job.parsed_lines if job else 0,
        invalid_lines=job.invalid_lines if job else 0,
        last_error=watch.last_error,
        created_at=watch.created_at,
        last_checked_at=watch.last_checked_at,
        next_check_at=watch.next_check_at,
    )


def _get_or_404(db: DbSession, watch_id: int) -> LogWatch:
    watch = watcher.get_watch(db, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Observação não encontrada.")
    return watch


@router.get("/settings", response_model=WatchSettingsOut)
def watch_settings() -> WatchSettingsOut:
    return WatchSettingsOut(
        root=watcher.watch_root(),
        min_interval_seconds=watcher.MIN_INTERVAL_SECONDS,
        max_interval_seconds=watcher.MAX_INTERVAL_SECONDS,
    )


@router.post("", response_model=LogWatchOut, status_code=status.HTTP_201_CREATED)
def create_watch(body: LogWatchIn, db: DbSession) -> LogWatchOut:
    try:
        watch = watcher.create_watch(db, body.path, body.interval_seconds, body.start_at_end)
    except watcher.WatchRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return _out(db, watch)


@router.get("", response_model=list[LogWatchOut])
def list_watches(db: DbSession) -> list[LogWatchOut]:
    return [_out(db, watch) for watch in watcher.list_watches(db)]


@router.get("/{watch_id}", response_model=LogWatchOut)
def get_watch(watch_id: int, db: DbSession) -> LogWatchOut:
    return _out(db, _get_or_404(db, watch_id))


@router.patch("/{watch_id}", response_model=LogWatchOut)
def update_watch(watch_id: int, body: LogWatchUpdate, db: DbSession) -> LogWatchOut:
    watch = _get_or_404(db, watch_id)
    try:
        watch = watcher.update_watch(db, watch, body.active, body.interval_seconds)
    except watcher.WatchRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return _out(db, watch)


@router.delete("/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(watch_id: int, db: DbSession) -> Response:
    watcher.delete_watch(db, _get_or_404(db, watch_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
