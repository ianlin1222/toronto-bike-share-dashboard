from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from bikeshare.api.contracts import RecommendationRequest
from bikeshare.api.service import RecommendationService, StaleDataError
from bikeshare.api.store import StationStore
from bikeshare.config import AppMode, Settings
from bikeshare.db.types import CurrentStation


class FakeStore(StationStore):
    def __init__(self, stations: list[CurrentStation]) -> None:
        self.stations = stations

    def all(self, *, decision_time: datetime) -> list[CurrentStation]:
        return self.stations

    def one(self, station_id: str, *, decision_time: datetime) -> CurrentStation | None:
        return next((item for item in self.stations if item.station_id == station_id), None)

    def health(self) -> dict[str, object]:
        return {"status": "success"}

    def record_recommendation(self, **_: object) -> None:
        return None


def current_station(*, reported_at: datetime) -> CurrentStation:
    return CurrentStation(
        station_id="one",
        lifecycle_state="active",
        name="One",
        lat=43.6532,
        lon=-79.3832,
        capacity=10,
        num_docks_available=2,
        num_bikes_available=8,
        num_docks_disabled=0,
        num_bikes_disabled=0,
        is_installed=True,
        is_renting=True,
        is_returning=True,
        source_last_reported=reported_at,
        retrieved_at=reported_at,
        ingested_at=reported_at,
        feed_last_updated=reported_at,
    )


def request() -> RecommendationRequest:
    return RecommendationRequest.model_validate(
        {
            "destination": {"lat": 43.6532, "lon": -79.3832},
            "horizon_minutes": 15,
            "radius_m": 750,
        }
    )


def test_all_stale_candidates_return_degraded_error() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    settings = Settings(app_mode=AppMode.LIVE_BASELINE)
    service = RecommendationService(
        settings,
        FakeStore([current_station(reported_at=now.replace(hour=11, minute=54))]),
    )
    with pytest.raises(StaleDataError, match="all candidate"):
        service.recommend(request(), request_id=uuid.uuid4(), now=now)


def test_one_candidate_has_no_alternative_and_validated_mode_fails_to_baseline() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    settings = Settings(app_mode=AppMode.VALIDATED_MODEL)
    response = RecommendationService(
        settings,
        FakeStore([current_station(reported_at=now)]),
    ).recommend(request(), request_id=uuid.uuid4(), now=now)
    assert response.primary is not None
    assert response.alternative is None
    assert response.mode == "live_baseline"
    assert response.primary.forecast_probability is None
    assert "integrity" in (response.fallback.reason or "")
