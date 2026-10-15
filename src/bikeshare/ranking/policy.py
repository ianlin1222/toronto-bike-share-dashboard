from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from bikeshare.db.types import CurrentStation

EARTH_RADIUS_M = 6_371_008.8


class PolicyVersion(StrEnum):
    NEAREST_OPERATIONAL = "nearest_operational_v1"
    NEAREST_CURRENT_DOCK = "nearest_current_dock_v1"
    CURRENT_BUFFER_DISTANCE = "current_buffer_distance_v1"
    FORECAST_DISTANCE = "forecast_distance_v1"


@dataclass(frozen=True, slots=True)
class EligibleCandidate:
    station: CurrentStation
    distance_m: float
    data_age_seconds: float


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate: EligibleCandidate
    rank: int
    score: float
    probability: float | None


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    candidates: tuple[EligibleCandidate, ...]
    exclusions: dict[str, int]


def haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def eligible_candidates(
    stations: list[CurrentStation],
    *,
    destination_lat: float,
    destination_lon: float,
    radius_m: int,
    decision_time: datetime,
    station_max_age_seconds: int,
    require_current_dock: bool,
    enforce_freshness: bool = True,
) -> EligibilityResult:
    candidates: list[EligibleCandidate] = []
    exclusions: dict[str, int] = {}
    for station in stations:
        distance = haversine_metres(destination_lat, destination_lon, station.lat, station.lon)
        reason: str | None = None
        if distance > radius_m:
            reason = "outside_radius"
        reported_at = station.source_last_reported
        age = (decision_time - reported_at).total_seconds() if reported_at else math.inf
        if reason is None and enforce_freshness and (age < -30 or age > station_max_age_seconds):
            reason = "stale_or_missing_report"
        if reason is None and station.lifecycle_state != "active":
            reason = "inactive_metadata"
        if reason is None and station.is_installed is not True:
            reason = "not_installed"
        if reason is None and station.is_returning is not True:
            reason = "not_accepting_returns"
        if reason is None and require_current_dock:
            if station.num_docks_available is None:
                reason = "missing_dock_count"
            elif station.num_docks_available < 1:
                reason = "no_current_dock"
        if reason is not None:
            exclusions[reason] = exclusions.get(reason, 0) + 1
            continue
        candidates.append(
            EligibleCandidate(
                station=station,
                distance_m=distance,
                data_age_seconds=max(age, 0) if math.isfinite(age) else age,
            )
        )
    return EligibilityResult(tuple(candidates), exclusions)


def rank_candidates(
    candidates: tuple[EligibleCandidate, ...],
    *,
    policy: PolicyVersion,
    radius_m: int,
    probabilities: Mapping[str, float] | None = None,
    distance_penalty: float = 0.10,
) -> tuple[RankedCandidate, ...]:
    probabilities = probabilities or {}
    scored: list[tuple[float, EligibleCandidate, float | None]] = []
    for candidate in candidates:
        probability = probabilities.get(candidate.station.station_id)
        if policy in {PolicyVersion.NEAREST_OPERATIONAL, PolicyVersion.NEAREST_CURRENT_DOCK}:
            score = -candidate.distance_m
        elif policy is PolicyVersion.CURRENT_BUFFER_DISTANCE:
            docks = candidate.station.num_docks_available
            if docks is None:
                continue
            score = min(docks, 5) / 5 - distance_penalty * candidate.distance_m / radius_m
        elif policy is PolicyVersion.FORECAST_DISTANCE:
            if probability is None:
                continue
            score = probability - distance_penalty * candidate.distance_m / radius_m
        else:  # pragma: no cover - StrEnum constrains callers
            raise ValueError(f"unsupported policy {policy}")
        scored.append((score, candidate, probability))
    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].distance_m,
            item[1].station.station_id,
        )
    )
    return tuple(
        RankedCandidate(candidate=item[1], rank=index, score=item[0], probability=item[2])
        for index, item in enumerate(scored, start=1)
    )
