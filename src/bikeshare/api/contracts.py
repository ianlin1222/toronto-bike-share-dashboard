from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def within_toronto_envelope(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and 43.45 <= lat <= 43.95 and -79.80 <= lon <= -79.00


class Destination(StrictModel):
    lat: float = Field(ge=-90, le=90, examples=[43.6532])
    lon: float = Field(ge=-180, le=180, examples=[-79.3832])

    @model_validator(mode="after")
    def inside_service_envelope(self) -> Destination:
        if not within_toronto_envelope(self.lat, self.lon):
            raise ValueError("destination is outside the configured Toronto service envelope")
        return self


class RecommendationRequest(StrictModel):
    destination: Destination
    horizon_minutes: int = Field(default=15, examples=[15])
    radius_m: int = Field(default=750, ge=100, le=2000, examples=[750])

    @field_validator("horizon_minutes")
    @classmethod
    def exact_supported_horizon(cls, value: int) -> int:
        if value not in {5, 10, 15, 30}:
            raise ValueError("horizon_minutes must be exactly one of 5, 10, 15, or 30")
        return value


class PredictionRequest(StrictModel):
    horizon_minutes: int = Field(default=15)

    @field_validator("horizon_minutes")
    @classmethod
    def exact_supported_horizon(cls, value: int) -> int:
        if value not in {5, 10, 15, 30}:
            raise ValueError("horizon_minutes must be exactly one of 5, 10, 15, or 30")
        return value


class ModelDescriptor(BaseModel):
    run_id: UUID
    algorithm: str
    artifact_sha256: str
    calibrated: bool


class FallbackDescriptor(BaseModel):
    used: bool
    reason: str | None = None


class RecommendedStation(BaseModel):
    station_id: str
    name: str | None
    lat: float
    lon: float
    distance_m: int
    available_docks_now: int | None
    forecast_probability: float | None
    source_last_reported: datetime | None
    data_age_seconds: int | None
    explanation: list[str]


class RecommendationResponse(BaseModel):
    request_id: UUID
    mode: Literal["fixture_demo", "live_baseline", "validated_model"]
    generated_at: datetime
    input: dict[str, int]
    distance_kind: Literal["haversine_straight_line"] = "haversine_straight_line"
    compatibility_assumption: Literal["generic_bicycle_total_reported_docks"] = (
        "generic_bicycle_total_reported_docks"
    )
    primary: RecommendedStation | None
    alternative: RecommendedStation | None
    model: ModelDescriptor | None
    feature_version: str
    policy_version: str
    fallback: FallbackDescriptor
    partial_feed: bool
    exclusion_counts: dict[str, int]
    notice: str = "Forecasts are uncertain and do not reserve a dock."


class StationStatusResponse(BaseModel):
    station_id: str
    name: str | None
    lat: float
    lon: float
    capacity: int | None
    available_docks: int | None
    available_bikes: int | None
    disabled_docks: int | None
    disabled_bikes: int | None
    is_installed: bool | None
    is_renting: bool | None
    is_returning: bool | None
    source_last_reported: datetime | None
    feed_last_updated: datetime | None
    retrieved_at: datetime
    ingested_at: datetime
    data_age_seconds: int | None
    fresh: bool
    quality_flags: list[str]
    compatibility_assumption: str = "generic_bicycle_total_reported_docks"


class ReadinessResponse(BaseModel):
    ready: bool
    mode: Literal["fixture_demo", "live_baseline", "validated_model"]
    database: Literal["not_required", "healthy", "unavailable"]
    latest_complete_poll: datetime | None
    latest_poll: datetime | None
    stale: bool
    partial_feed: bool
    active_model_run_id: str | None
    feature_version: str
    reason: str | None = None


class StationLocation(BaseModel):
    station_id: str
    name: str
    lat: float
    lon: float


class StationCatalogue(BaseModel):
    mode: str
    stations: list[StationLocation]
