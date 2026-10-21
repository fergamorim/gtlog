"""Live file watching: every interval, import only the lines appended to a file since the last read.

A watch remembers the byte offset it consumed and the file's inode. A new inode (the file was rotated
and recreated) or a size below the offset (truncated) restarts from the beginning and detects the
format again. Only complete lines are read: a last line without its line break waits for the next
poll. Each poll writes its rows and the new offset in one transaction, so a line is imported once.

Files are only accepted inside settings.watch_root, checked again on every poll after resolving
symlinks, so the API cannot be used to read arbitrary files of its host.
"""

import hashlib
import logging
import os
import threading
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import ImportJob, ImportStatus, LogWatch
from app.parsers import LineParser, detect_parser, parser_by_name
from app.services.importer import (
    BATCH_SIZE,
    DETECT_SAMPLE_LINES,
    MAX_FILENAME_CHARS,
    SNIFF_SIZE,
    clean_lines,
    copy_rows,
    to_row,
)

logger = logging.getLogger(__name__)

MIN_INTERVAL_SECONDS = 1
MAX_INTERVAL_SECONDS = 24 * 60 * 60
# A poll reads at most this much; a bigger backlog is drained by the next polls, right after.
MAX_POLL_BYTES = 16 * 1024 * 1024
# Format detection reads at most this much from the start of the file.
DETECT_SAMPLE_BYTES = 1024 * 1024
# Bytes from the start of the file fingerprinted to detect rotation (see _same_head).
HEAD_BYTES = 1024
TICK_SECONDS = 1.0
DUE_LIMIT = 20


class WatchRejected(Exception):
    """The watch cannot be created; carries the HTTP status and a user-facing message."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def watch_root() -> str:
    return os.path.realpath(get_settings().watch_root)


def resolve_path(path: str) -> tuple[str, str]:
    """User path -> (path relative to the root, as stored; resolved absolute path).

    Raises WatchRejected when the path leaves the root or is not a readable regular file.
    """
    root = watch_root()
    candidate = path.strip()
    joined = os.path.normpath(os.path.join(root, candidate))
    resolved = os.path.realpath(joined)
    if os.path.commonpath([root, resolved]) != root or os.path.commonpath([root, joined]) != root:
        raise WatchRejected(422, f"O arquivo precisa estar dentro da pasta observável ({root}).")
    if not os.path.isfile(resolved):
        raise WatchRejected(404, f"Arquivo não encontrado: {candidate}.")
    if not os.access(resolved, os.R_OK):
        raise WatchRejected(422, f"Sem permissão para ler o arquivo: {candidate}.")
    return os.path.relpath(joined, root), resolved


def create_watch(db: Session, path: str, interval_seconds: int, start_at_end: bool = False) -> LogWatch:
    relative, resolved = resolve_path(path)
    duplicate = db.scalar(select(LogWatch.id).where(LogWatch.path == relative, LogWatch.active.is_(True)))
    if duplicate is not None:
        raise WatchRejected(409, "Este arquivo já está sendo observado.")
    with open(resolved, "rb") as fh:
        if b"\x00" in fh.read(SNIFF_SIZE):
            raise WatchRejected(415, "O arquivo parece ser binário. Indique um log em texto.")
        stat = os.fstat(fh.fileno())
        offset = _end_of_last_line(fh, stat.st_size) if start_at_end else 0
        fh.seek(0)
        head = fh.read(min(offset, HEAD_BYTES))

    job = ImportJob(
        filename=os.path.basename(relative)[:MAX_FILENAME_CHARS],
        status=ImportStatus.DONE,
        finished_at=datetime.now(UTC),
    )
    db.add(job)
    db.flush()
    watch = LogWatch(
        path=relative,
        interval_seconds=interval_seconds,
        active=True,
        import_id=job.id,
        offset=offset,
        inode=stat.st_ino,
        head_size=len(head),
        head_digest=hashlib.sha256(head).hexdigest() if head else None,
        next_check_at=datetime.now(UTC),
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return watch


def list_watches(db: Session) -> list[LogWatch]:
    return list(db.scalars(select(LogWatch).order_by(LogWatch.created_at.desc(), LogWatch.id.desc())))


def get_watch(db: Session, watch_id: int) -> LogWatch | None:
    return db.get(LogWatch, watch_id)


def update_watch(db: Session, watch: LogWatch, active: bool | None, interval_seconds: int | None) -> LogWatch:
    if active is not None and active != watch.active:
        if active:
            duplicate = db.scalar(
                select(LogWatch.id).where(
                    LogWatch.path == watch.path, LogWatch.active.is_(True), LogWatch.id != watch.id
                )
            )
            if duplicate is not None:
                raise WatchRejected(409, "Este arquivo já está sendo observado.")
            # Resuming reads right away what was appended while paused.
            watch.next_check_at = datetime.now(UTC)
        watch.active = active
    if interval_seconds is not None and interval_seconds != watch.interval_seconds:
        watch.interval_seconds = interval_seconds
        # Reschedule from the last read, so a shorter interval applies now instead of after the old one.
        base = watch.last_checked_at or datetime.now(UTC)
        watch.next_check_at = min(watch.next_check_at, base + timedelta(seconds=interval_seconds))
    db.commit()
    db.refresh(watch)
    return watch


def delete_watch(db: Session, watch: LogWatch) -> None:
    """Stop watching; the lines already imported stay in their import."""
    db.delete(watch)
    db.commit()


def due_watch_ids(db: Session, now: datetime, limit: int = DUE_LIMIT) -> list[int]:
    stmt = (
        select(LogWatch.id)
        .where(LogWatch.active.is_(True), LogWatch.next_check_at <= now)
        .order_by(LogWatch.next_check_at)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def poll_watch(watch_id: int) -> None:
    """Read what was appended to the watched file and import it. Owns its session."""
    db = SessionLocal()
    try:
        _poll(db, watch_id)
    except Exception:
        logger.exception("Watch %s failed", watch_id)
        db.rollback()
        interval = db.scalar(select(LogWatch.interval_seconds).where(LogWatch.id == watch_id))
        if interval is None:
            return
        now = datetime.now(UTC)
        db.execute(
            update(LogWatch)
            .where(LogWatch.id == watch_id)
            .values(
                last_error="Erro inesperado ao ler o arquivo.",
                last_checked_at=now,
                next_check_at=now + timedelta(seconds=interval),
            )
        )
        db.commit()
    finally:
        db.close()


def _poll(db: Session, watch_id: int) -> None:
    # SKIP LOCKED: a poll already running elsewhere (another worker) owns this watch for now.
    watch = db.scalar(select(LogWatch).where(LogWatch.id == watch_id).with_for_update(skip_locked=True))
    if watch is None or not watch.active:
        db.rollback()
        return
    now = datetime.now(UTC)
    watch.last_checked_at = now
    watch.next_check_at = now + timedelta(seconds=watch.interval_seconds)
    try:
        drained = _read_new_lines(db, watch)
    except WatchRejected as exc:
        watch.last_error = exc.detail
    except OSError:
        # Removed or unreadable between the checks and the read (e.g. mid-rotation): retry next interval.
        watch.last_error = "Não foi possível ler o arquivo."
    else:
        if not drained:
            # More than one poll's worth is waiting: come back on the next tick instead of next interval.
            watch.next_check_at = now
    db.commit()


def _read_new_lines(db: Session, watch: LogWatch) -> bool:
    """Import the complete lines after watch.offset. Returns False when bytes are still left to read."""
    _, resolved = resolve_path(watch.path)
    with open(resolved, "rb") as fh:
        stat = os.fstat(fh.fileno())
        if stat.st_ino != watch.inode or stat.st_size < watch.offset or not _same_head(watch, fh):
            # Rotated (new file at the same path) or truncated: start over, the format may have changed.
            watch.inode, watch.offset, watch.format, watch.header = stat.st_ino, 0, None, None
            watch.head_size, watch.head_digest = 0, None
        if stat.st_size == watch.offset:
            watch.last_error = None
            return True

        parser = _parser_for(watch, fh)
        if parser is None:
            # Keep the offset: once the file has recognizable lines, they are imported from the start.
            watch.last_error = "Formato de log não reconhecido."
            return True

        fh.seek(watch.offset)
        data = fh.read(MAX_POLL_BYTES)
    consumed = _complete_lines(data)
    if consumed == 0:
        watch.last_error = None
        return True
    text = data[:consumed].decode("utf-8", errors="replace")
    if watch.offset == 0:
        text = text.removeprefix("﻿")

    is_header = getattr(parser, "is_header", None)
    total = parsed = invalid = 0
    batch: list[tuple] = []
    for line in clean_lines(text.split("\n")):
        entry = parser.parse(line)
        if entry is None and is_header is not None and is_header(line):
            continue
        total += 1
        if entry is None:
            invalid += 1
        else:
            parsed += 1
            batch.append(to_row(watch.import_id, entry, line))
        if len(batch) >= BATCH_SIZE:
            copy_rows(db, batch)
            batch = []
    copy_rows(db, batch)
    db.execute(
        update(ImportJob)
        .where(ImportJob.id == watch.import_id)
        .values(
            format=watch.format,
            total_lines=ImportJob.total_lines + total,
            parsed_lines=ImportJob.parsed_lines + parsed,
            invalid_lines=ImportJob.invalid_lines + invalid,
            finished_at=datetime.now(UTC),
        )
    )
    watch.offset += consumed
    watch.last_error = None
    if watch.head_size < HEAD_BYTES:
        with open(resolved, "rb") as fh:
            _remember_head(watch, fh)
    return watch.offset >= stat.st_size


def _same_head(watch: LogWatch, fh: BinaryIO) -> bool:
    """False when the first bytes already read changed, i.e. another file now sits at the path."""
    if not watch.head_size:
        return True
    fh.seek(0)
    return hashlib.sha256(fh.read(watch.head_size)).hexdigest() == watch.head_digest


def _remember_head(watch: LogWatch, fh: BinaryIO) -> None:
    head = fh.read(min(watch.offset, HEAD_BYTES))
    watch.head_size, watch.head_digest = len(head), hashlib.sha256(head).hexdigest()


def _end_of_last_line(fh: BinaryIO, size: int) -> int:
    """Offset just after the file's last line break (0 without one): a partial last line is read later."""
    end = size
    while end > 0:
        start = max(0, end - SNIFF_SIZE)
        fh.seek(start)
        found = fh.read(end - start).rfind(b"\n")
        if found != -1:
            return start + found + 1
        end = start
    return 0


def _complete_lines(data: bytes) -> int:
    """Bytes of data that form complete lines (up to the last line break)."""
    end = data.rfind(b"\n") + 1
    if end == 0 and len(data) >= MAX_POLL_BYTES:
        # A single line longer than a whole poll: take it as is rather than stall forever.
        return len(data)
    return end


def _parser_for(watch: LogWatch, fh: BinaryIO) -> LineParser | None:
    """The watch's parser, detecting the format from the start of the file the first time."""
    if watch.format is None:
        fh.seek(0)
        head = fh.read(DETECT_SAMPLE_BYTES).decode("utf-8", errors="replace").removeprefix("﻿")
        # The last line of the sample may be cut in half: leave it out unless it is the only one.
        lines = head.split("\n")
        if len(lines) > 1:
            lines = lines[:-1]
        sample = list(clean_lines(lines))[:DETECT_SAMPLE_LINES]
        detected = detect_parser(sample)
        if detected is None:
            return None
        watch.format = detected.name[:30]
        # Parsers with a header (CSV) learn their columns from the first line of the file.
        watch.header = sample[0] if hasattr(detected, "is_header") else None
    parser = parser_by_name(watch.format)
    if parser is not None and watch.header is not None:
        parser.parse(watch.header)
    return parser


class WatchScheduler:
    """Background thread that polls due watches every TICK_SECONDS."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="log-watch", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            try:
                with SessionLocal() as db:
                    ids = due_watch_ids(db, datetime.now(UTC))
                for watch_id in ids:
                    if self._stop.is_set():
                        return
                    poll_watch(watch_id)
            except Exception:
                # The database may be briefly unavailable; try again on the next tick.
                logger.exception("Watch scheduler tick failed")
