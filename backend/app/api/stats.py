from typing import Annotated

from fastapi import APIRouter, Query

from app.api.schemas import LogFiltersDep, StatsOut
from app.core.database import DbSession
from app.services import stats
from app.services.stats import Bucket

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(
    filters: LogFiltersDep, db: DbSession, bucket: Annotated[Bucket | None, Query()] = None
) -> StatsOut:
    return StatsOut(**stats.compute_stats(db, filters, bucket))
