from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from bikeshare.db.repository import IngestionRepository, station_rows_from_json
from bikeshare.db.types import CurrentStation
from bikeshare.ranking import RankedCandidate


class StationStore(Protocol):
    def all(self, *, decision_time: datetime) -> list[CurrentStation]: ...

    def one(self, station_id: str, *, decision_time: datetime) -> CurrentStation | None: ...

    def health(self) -> dict[str, object]: ...

    def record_recommendation(
        self,
        *,
        request_id: uuid.UUID,
        requested_at: datetime,
        destination_lat: float,
        destination_lon: float,
        destination_decimals: int,
        horizon_minutes: int,
        radius_m: int,
        mode: str,
        policy_version: str,
        feature_version: str,
        fallback_reason: str | None,
        ranked: tuple[RankedCandidate, ...],
    ) -> None: ...


class DatabaseStationStore:
    def __init__(self, repository: IngestionRepository, *, cache_seconds: float = 0) -> None:
        self.repository = repository
        self.cache_seconds = cache_seconds
        self._cache_lock = threading.Lock()
        self._cached_at: datetime | None = None
        self._cache_until = 0.0
        self._cached_stations: tuple[CurrentStation, ...] = ()

    def all(self, *, decision_time: datetime) -> list[CurrentStation]:
        if self.cache_seconds <= 0:
            return self.repository.get_current_stations(decision_time=decision_time)
        # One short-lived, immutable serving snapshot prevents concurrent requests
        # from repeating the same city-wide query. Historical extraction opts out.
        # Never reuse a snapshot that was obtained for a later decision time.
        with self._cache_lock:
            if self._cached_at is not None and decision_time < self._cached_at:
                return self.repository.get_current_stations(decision_time=decision_time)
            if self._cached_at is None or time.monotonic() >= self._cache_until:
                self._cached_stations = tuple(
                    self.repository.get_current_stations(decision_time=decision_time)
                )
                self._cached_at = decision_time
                self._cache_until = time.monotonic() + self.cache_seconds
            return list(self._cached_stations)

    def one(self, station_id: str, *, decision_time: datetime) -> CurrentStation | None:
        return self.repository.get_current_station(station_id, decision_time=decision_time)

    def health(self) -> dict[str, object]:
        return self.repository.readiness()

    def record_recommendation(
        self,
        *,
        request_id: uuid.UUID,
        requested_at: datetime,
        destination_lat: float,
        destination_lon: float,
        destination_decimals: int,
        horizon_minutes: int,
        radius_m: int,
        mode: str,
        policy_version: str,
        feature_version: str,
        fallback_reason: str | None,
        ranked: tuple[RankedCandidate, ...],
    ) -> None:
        self.repository.persist_recommendation(
            request_id=request_id,
            requested_at=requested_at,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            destination_decimals=destination_decimals,
            horizon_minutes=horizon_minutes,
            radius_m=radius_m,
            mode=mode,
            policy_version=policy_version,
            feature_version=feature_version,
            fallback_reason=fallback_reason,
            ranked=ranked,
        )


class FixtureStationStore:
    def __init__(self, path: Path) -> None:
        with path.open(encoding="utf-8") as file:
            loaded = json.load(file)
        if not isinstance(loaded, list):
            raise ValueError("fixture station root must be an array")
        self._stations = station_rows_from_json(loaded)

    def _freshened(self, station: CurrentStation, decision_time: datetime) -> CurrentStation:
        source_time = decision_time - timedelta(seconds=30)
        return CurrentStation(
            station_id=station.station_id,
            lifecycle_state=station.lifecycle_state,
            name=station.name,
            lat=station.lat,
            lon=station.lon,
            capacity=station.capacity,
            num_docks_available=station.num_docks_available,
            num_bikes_available=station.num_bikes_available,
            num_docks_disabled=station.num_docks_disabled,
            num_bikes_disabled=station.num_bikes_disabled,
            is_installed=station.is_installed,
            is_renting=station.is_renting,
            is_returning=station.is_returning,
            source_last_reported=source_time,
            retrieved_at=decision_time - timedelta(seconds=20),
            ingested_at=decision_time - timedelta(seconds=19),
            feed_last_updated=source_time,
            quality_flags=tuple((*station.quality_flags, "fixture_timestamp_rebased")),
            vehicle_docks_available=station.vehicle_docks_available,
        )

    def all(self, *, decision_time: datetime) -> list[CurrentStation]:
        return [self._freshened(station, decision_time) for station in self._stations]

    def one(self, station_id: str, *, decision_time: datetime) -> CurrentStation | None:
        return next(
            (
                self._freshened(station, decision_time)
                for station in self._stations
                if station.station_id == station_id
            ),
            None,
        )

    def health(self) -> dict[str, object]:
        now = datetime.now(tz=UTC)
        return {
            "scheduled_at": now,
            "latest_complete_at": now,
            "status": "fixture",
        }

    def record_recommendation(
        self,
        *,
        request_id: uuid.UUID,
        requested_at: datetime,
        destination_lat: float,
        destination_lon: float,
        destination_decimals: int,
        horizon_minutes: int,
        radius_m: int,
        mode: str,
        policy_version: str,
        feature_version: str,
        fallback_reason: str | None,
        ranked: tuple[RankedCandidate, ...],
    ) -> None:
        # Fixture mode is deliberately database-independent and does not create
        # request records that could be mistaken for live or replay evidence.
        return None
