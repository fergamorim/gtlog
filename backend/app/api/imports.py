from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from app.api.schemas import ImportJobOut
from app.core.database import DbSession
from app.services import importer

router = APIRouter(prefix="/imports", tags=["imports"])


# Sync handlers run in the threadpool, so the chunked disk copy never blocks the event loop.
@router.post("", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_import(file: UploadFile, background: BackgroundTasks, db: DbSession) -> ImportJobOut:
    try:
        path = importer.save_upload(file.file)
    except importer.UploadRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    finally:
        file.file.close()
    try:
        job = importer.create_job(db, file.filename)
    except BaseException:
        importer.discard_upload(path)
        raise
    background.add_task(importer.process_import, job.id, path)
    return ImportJobOut.model_validate(job)


@router.get("", response_model=list[ImportJobOut])
def list_imports(db: DbSession) -> list[ImportJobOut]:
    return [ImportJobOut.model_validate(job) for job in importer.list_jobs(db)]


@router.get("/{job_id}", response_model=ImportJobOut)
def get_import(job_id: int, db: DbSession) -> ImportJobOut:
    job = importer.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    return ImportJobOut.model_validate(job)
