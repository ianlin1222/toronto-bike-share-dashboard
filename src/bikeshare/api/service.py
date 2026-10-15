from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from bikeshare.api.contracts import (
    FallbackDescriptor,
    RecommendationRequest,
    RecommendationResponse,
    RecommendedStation,
    StationStatusResponse,
)
from bikeshare.api.store import StationStore
from bikeshare.config import AppMode, Settings
from bikeshare.db.types import CurrentStation
from bikeshare.ranking import PolicyVersion, RankedCandidate, eligible_candidates, rank_candidates


class StaleDataError(RuntimeError):
    pass


class RecommendationService:
    def __init__(self, settings: Settings, store: StationStore) -> None:
        self.settings = settings
        self.store = store

    def station_status(self, station_id: str, *, now: datetime | None = None) -> StationStatusResponse | None:
        decision_time = now or datetime.now(tz=UTC)
        station = self.store.one(station_id, decision_time=decision_time)
        if station is None:
            return None
        age = _data_age(station, decision_time)
        return StationStatusResponse(
            station_id=station.station_id,
            name=station.name,
            lat=station.lat,
            lon=station.lon,
            capacity=station.capacity,
            available_docks=station.num_docks_available,
            available_bikes=station.num_bikes_available,
            disabled_docks=station.num_docks_disabled,
            disabled_bikes=station.num_bikes_disabled,
            is_installed=station.is_installed,
            is_renting=station.is_renting,
            is_returning=station.is_returning,
            source_last_reported=station.source_last_reported,
            feed_last_updated=station.feed_last_updated,
            retrieved_at=station.retrieved_at,
            ingested_at=station.ingested_at,
            data_age_seconds=round(age) if math.isfinite(age) else None,
            fresh=-30 <= age <= self.settings.station_max_age_seconds,
            quality_flags=list(station.quality_flags),
        )

    def recommend(
        self,
        request: RecommendationRequest,
        *,
        request_id: uuid.UUID,
        now: datetime | None = None,
        partial_feed: bool = False,
    ) -> RecommendationResponse:
        decision_time = now or datetime.now(tz=UTC)
        stations = self.store.all(decision_time=decision_time)
        if not stations and self.settings.app_mode is not AppMode.FIXTURE_DEMO:
            raise StaleDataError("no canonical station observations are available")

        enforce_freshness = self.settings.app_mode is not AppMode.FIXTURE_DEMO
        result = eligible_candidates(
            stations,
            destination_lat=request.destination.lat,
            destination_lon=request.destination.lon,
            radius_m=request.radius_m,
            decision_time=decision_time,
            station_max_age_seconds=self.settings.station_max_age_seconds,
            require_current_dock=True,
            enforce_freshness=enforce_freshness,
        )
        within_radius = sum(
            count for reason, count in result.exclusions.items() if reason != "outside_radius"
        ) + len(result.candidates)
        all_stale = (
            enforce_freshness
            and within_radius > 0
            and result.exclusions.get("stale_or_missing_report", 0) == within_radius
        )
        if all_stale:
            raise StaleDataError("all candidate station reports are stale or missing")

        policy = PolicyVersion.NEAREST_CURRENT_DOCK
        ranked = rank_candidates(result.candidates, policy=policy, radius_m=request.radius_m)
        primary = self._to_contract(ranked[0]) if ranked else None
        alternative = self._to_contract(ranked[1]) if len(ranked) > 1 else None
        mode = self.settings.app_mode
        fallback_reason = (
            "fixture demonstration; forecast probabilities are not measured"
            if mode is AppMode.FIXTURE_DEMO
            else "validated model unavailable; used fresh current availability and distance"
        )
        if mode is AppMode.VALIDATED_MODEL:
            # Loading is fail-closed. Until an approved run passes artifact/schema checks,
            # serving remains a transparent live-baseline fallback.
            mode = AppMode.LIVE_BASELINE
            fallback_reason = "active validated model failed availability or integrity checks"
        response = RecommendationResponse(
            request_id=request_id,
            mode=mode.value,
            generated_at=decision_time,
            input={"horizon_minutes": request.horizon_minutes, "radius_m": request.radius_m},
            primary=primary,
            alternative=alternative,
            model=None,
            feature_version="v1",
            policy_version=policy.value,
            fallback=FallbackDescriptor(used=True, reason=fallback_reason),
            partial_feed=partial_feed,
            exclusion_counts=result.exclusions,
        )
        self.store.record_recommendation(
            request_id=request_id,
            requested_at=decision_time,
            destination_lat=request.destination.lat,
            destination_lon=request.destination.lon,
            destination_decimals=self.settings.destination_retention_decimals,
            horizon_minutes=request.horizon_minutes,
            radius_m=request.radius_m,
            mode=response.mode,
            policy_version=policy.value,
            feature_version="v1",
            fallback_reason=fallback_reason,
            ranked=ranked[:2],
        )
        return response

    @staticmethod
    def _to_contract(ranked: RankedCandidate) -> RecommendedStation:
        station = ranked.candidate.station
        docks_phrase = (
            f"{station.num_docks_available} reported docks now"
            if station.num_docks_available is not None
            else "reported dock count unavailable"
        )
        return RecommendedStation(
            station_id=station.station_id,
            name=station.name,
            lat=station.lat,
            lon=station.lon,
            distance_m=round(ranked.candidate.distance_m),
            available_docks_now=station.num_docks_available,
            forecast_probability=ranked.probability,
            source_last_reported=station.source_last_reported,
            data_age_seconds=(
                round(ranked.candidate.data_age_seconds)
                if math.isfinite(ranked.candidate.data_age_seconds)
                else None
            ),
            explanation=[
                "fresh and accepting returns",
                docks_phrase,
                f"{round(ranked.candidate.distance_m)} m straight-line distance",
            ],
        )


def _data_age(station: CurrentStation, decision_time: datetime) -> float:
    return (
        (decision_time - station.source_last_reported).total_seconds()
        if station.source_last_reported
        else math.inf
    )
