from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class AppMode(StrEnum):
    FIXTURE_DEMO = "fixture_demo"
    LIVE_BASELINE = "live_baseline"
    VALIDATED_MODEL = "validated_model"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BIKESHARE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://bikeshare:bikeshare@localhost:5432/bikeshare"
    app_mode: AppMode = AppMode.FIXTURE_DEMO
    log_level: str = "INFO"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000

    gbfs_discovery_url: str = (
        "https://toronto.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json"
    )
    source_contact: str = "unset-local-project-contact"
    status_poll_seconds: int = Field(default=60, ge=30, le=900)
    metadata_poll_seconds: int = Field(default=900, ge=60, le=86400)
    complete_batch_max_age_seconds: int = Field(default=120, ge=30, le=3600)
    station_max_age_seconds: int = Field(default=300, ge=60, le=3600)
    partial_batch_min_coverage: float = Field(default=0.95, ge=0.5, le=1.0)
    destination_retention_decimals: int = Field(default=3, ge=0, le=5)
    active_model_run_id: str | None = None
    model_root: Path = Path("var/models")
    fixture_path: Path = PACKAGE_ROOT / "api/static/normalized_stations.json"
    toronto_timezone: str = "America/Toronto"
    default_radius_m: int = 750
    min_radius_m: int = 100
    max_radius_m: int = 2000
    supported_horizons: tuple[int, ...] = (5, 10, 15, 30)

    @field_validator("source_contact")
    @classmethod
    def strip_contact(cls, value: str) -> str:
        return value.strip()

    @property
    def user_agent(self) -> str:
        return f"BikeShareDockAvailability/0.1 ({self.source_contact})"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
