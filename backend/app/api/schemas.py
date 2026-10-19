from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ImportStatus


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: ImportStatus
    format: str | None
    total_lines: int
    parsed_lines: int
    invalid_lines: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None
