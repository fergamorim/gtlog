from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gtlog:gtlog@localhost:5432/gtlog"
    upload_max_mb: int = 1024
    cors_origins: str = "http://localhost:5173"
    # Folder whose files can be watched; in Docker it is a host folder mounted read-only.
    watch_root: str = "/watch"
    # The same folder as seen on the host (GTLOG_WATCH_DIR), so a full host path can be typed too.
    watch_host_root: str = ""
    # Off in tests, which run polls by hand instead of through the background scheduler.
    watch_scheduler: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
