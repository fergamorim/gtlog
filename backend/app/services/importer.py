"""File import: receive the upload, then parse and bulk insert it in the background."""

import logging
import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import BinaryIO

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import ImportJob, ImportStatus, LogEntry
from app.parsers import detect_parser

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024
SNIFF_SIZE = 1024
BATCH_SIZE = 5000
DETECT_SAMPLE_LINES = 200
MAX_TEXT_CHARS = 10_000
MAX_FILENAME_CHARS = 255
LIST_LIMIT = 50


class UploadRejected(Exception):
    """The upload cannot be accepted; carries the HTTP status and a user-facing message."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def save_upload(source: BinaryIO) -> str:
    """Copy the upload to a temp file in chunks, validating size and content. Returns the path."""
    max_mb = get_settings().upload_max_mb
    max_bytes = max_mb * 1024 * 1024
    fd, path = tempfile.mkstemp(prefix="gtlog-import-", suffix=".log")
    try:
        written = 0
        with os.fdopen(fd, "wb") as out:
            while chunk := source.read(CHUNK_SIZE):
                if written == 0 and b"\x00" in chunk[:SNIFF_SIZE]:
                    raise UploadRejected(415, "O arquivo parece ser binário. Envie um log em texto.")
                written += len(chunk)
                if written > max_bytes:
                    raise UploadRejected(413, f"O arquivo excede o tamanho máximo permitido de {max_mb} MB.")
                out.write(chunk)
        if written == 0:
            raise UploadRejected(422, "O arquivo enviado está vazio.")
    except BaseException:
        discard_upload(path)
        raise
    return path


def create_job(db: Session, filename: str | None) -> ImportJob:
    name = os.path.basename(filename or "").strip() or "upload.log"
    job = ImportJob(filename=name[:MAX_FILENAME_CHARS], status=ImportStatus.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> ImportJob | None:
    return db.get(ImportJob, job_id)


def list_jobs(db: Session, limit: int = LIST_LIMIT) -> list[ImportJob]:
    stmt = select(ImportJob).order_by(ImportJob.created_at.desc(), ImportJob.id.desc()).limit(limit)
    return list(db.scalars(stmt))


def process_import(job_id: int, path: str) -> None:
    """Background task: detect the format, parse every line and insert in batches. Owns its session."""
    db = SessionLocal()
    try:
        _run(db, job_id, path)
    except Exception:
        logger.exception("Import %s failed", job_id)
        db.rollback()
        db.execute(delete(LogEntry).where(LogEntry.import_id == job_id))
        _finish(db, job_id, ImportStatus.FAILED, error="Erro inesperado ao processar o arquivo.")
    finally:
        db.close()
        discard_upload(path)


def _run(db: Session, job_id: int, path: str) -> None:
    _set(db, job_id, status=ImportStatus.PROCESSING)

    sample = []
    for line in _read_lines(path):
        sample.append(line)
        if len(sample) >= DETECT_SAMPLE_LINES:
            break
    parser = detect_parser(sample)
    if parser is None:
        _finish(db, job_id, ImportStatus.FAILED, error="Formato de log não reconhecido.")
        return
    _set(db, job_id, format=parser.name[:30])

    total = parsed = invalid = 0
    batch: list[tuple] = []
    for line in _read_lines(path):
        total += 1
        entry = parser.parse(line)
        if entry is None:
            invalid += 1
        else:
            parsed += 1
            # Parsers already bound service/category to their column sizes (normalize.build).
            batch.append(
                (
                    job_id,
                    entry.timestamp,
                    entry.level.name,
                    entry.message[:MAX_TEXT_CHARS],
                    entry.service,
                    entry.category,
                    line[:MAX_TEXT_CHARS],
                )
            )
        if total % BATCH_SIZE == 0:
            _flush(db, job_id, batch, total, parsed, invalid)
            batch = []
    _flush(db, job_id, batch, total, parsed, invalid)
    _finish(db, job_id, ImportStatus.DONE)


def _read_lines(path: str) -> Iterator[str]:
    """Yield non-blank lines without the line break. Undecodable bytes become U+FFFD."""
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            # Postgres text columns reject NUL; the sniff only covers the first KB.
            line = line.rstrip("\r\n").replace("\x00", "")
            if line.strip():
                yield line


_COPY_COLUMNS = ("import_id", "timestamp", "level", "message", "service", "category", "raw")
_COPY_SQL = f"COPY {LogEntry.__tablename__} ({', '.join(_COPY_COLUMNS)}) FROM STDIN"


def _flush(db: Session, job_id: int, rows: list[tuple], total: int, parsed: int, invalid: int) -> None:
    """Write one batch and the job counters in a single commit. Rows follow _COPY_COLUMNS order."""
    if rows:
        # COPY is ~10x faster than multi-row INSERT here; it runs in the session's transaction.
        conn = db.connection().connection.driver_connection
        with conn.cursor() as cursor, cursor.copy(_COPY_SQL) as copy:
            for row in rows:
                copy.write_row(row)
    db.execute(
        update(ImportJob)
        .where(ImportJob.id == job_id)
        .values(total_lines=total, parsed_lines=parsed, invalid_lines=invalid)
    )
    db.commit()


def _set(db: Session, job_id: int, **values) -> None:
    db.execute(update(ImportJob).where(ImportJob.id == job_id).values(**values))
    db.commit()


def _finish(db: Session, job_id: int, status: ImportStatus, error: str | None = None) -> None:
    _set(db, job_id, status=status, error=error, finished_at=datetime.now(UTC))


def discard_upload(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
