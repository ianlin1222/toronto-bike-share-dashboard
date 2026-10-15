from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from bikeshare.features.schema import FEATURE_NAMES
from bikeshare.ranking import haversine_metres

TORONTO = ZoneInfo("America/Toronto")


@dataclass(frozen=True, slots=True)
class FeatureObservation:
    station_id: str
    retrieved_at: datetime
    ingested_at: datetime
    source_last_reported: datetime | None
    docks: int | None
    bikes: int | None
    docks_disabled: int | None
    bikes_disabled: int | None
    is_installed: bool | None
    is_renting: bool | None
    is_returning: bool | None


@dataclass(frozen=True, slots=True)
class StationMetadata:
    station_id: str
    lat: float
    lon: float
    capacity: int | None
    known_from_at: datetime
    known_to_at: datetime | None = None


def temporal_features(decision_time: datetime, horizon_minutes: int) -> dict[str, float | int]:
    if decision_time.tzinfo is None:
        raise ValueError("decision_time must be timezone-aware")
    local = decision_time.astimezone(TORONTO)
    minute_of_day = local.hour * 60 + local.minute + local.second / 60
    minute_of_week = local.weekday() * 1440 + minute_of_day
    offset = local.utcoffset()
    dst = local.dst()
    return {
        "local_hour": local.hour,
        "local_weekday": local.weekday(),
        "is_weekend": int(local.weekday() >= 5),
        "hour_sin": math.sin(2 * math.pi * minute_of_day / 1440),
        "hour_cos": math.cos(2 * math.pi * minute_of_day / 1440),
        "week_sin": math.sin(2 * math.pi * minute_of_week / (7 * 1440)),
        "week_cos": math.cos(2 * math.pi * minute_of_week / (7 * 1440)),
        "horizon_minutes": horizon_minutes,
        "utc_offset_minutes": int(offset.total_seconds() / 60) if offset else 0,
        "dst_flag": int(bool(dst and dst.total_seconds())),
    }


def rolling_dock_features(
    observations: list[FeatureObservation],
    *,
    decision_time: datetime,
    window_minutes: int,
    max_carry_minutes: int = 5,
    min_coverage: float = 0.80,
) -> dict[str, float | int | None]:
    window_start = decision_time - timedelta(minutes=window_minutes)
    usable = sorted(
        (
            observation
            for observation in observations
            if observation.docks is not None
            and observation.retrieved_at <= decision_time
            and observation.ingested_at <= decision_time
            and observation.retrieved_at >= window_start - timedelta(minutes=max_carry_minutes)
        ),
        key=lambda item: (item.retrieved_at, item.ingested_at),
    )
    # A repeated source report is still one distinct observed state for trend/volatility.
    distinct: list[FeatureObservation] = []
    seen_report_times: set[datetime] = set()
    for observation in usable:
        report_time = observation.source_last_reported or observation.retrieved_at
        if report_time in seen_report_times:
            continue
        seen_report_times.add(report_time)
        distinct.append(observation)

    covered_seconds = 0.0
    weighted_sum = 0.0
    max_carry = timedelta(minutes=max_carry_minutes)
    for index, observation in enumerate(usable):
        start = max(observation.retrieved_at, window_start)
        next_time = usable[index + 1].retrieved_at if index + 1 < len(usable) else decision_time
        end = min(next_time, observation.retrieved_at + max_carry, decision_time)
        seconds = max((end - start).total_seconds(), 0)
        if seconds:
            docks = observation.docks
            assert docks is not None
            covered_seconds += seconds
            weighted_sum += float(docks) * seconds
    window_seconds = window_minutes * 60
    coverage = min(covered_seconds / window_seconds, 1.0) if window_seconds else 0.0
    sufficient = coverage >= min_coverage and len(distinct) >= 3
    prefix = f"{window_minutes}m"
    if not sufficient:
        return {
            f"docks_avg_{prefix}": None,
            f"docks_change_{prefix}": None,
            f"docks_slope_{prefix}": None,
            f"docks_volatility_{prefix}": None,
            f"coverage_{prefix}": coverage,
        }

    first, last = distinct[0], distinct[-1]
    elapsed_minutes = (last.retrieved_at - first.retrieved_at).total_seconds() / 60
    change = float(last.docks - first.docks)  # type: ignore[operator]
    changes_per_minute: list[float] = []
    for previous, current in pairwise(distinct):
        elapsed = (current.retrieved_at - previous.retrieved_at).total_seconds() / 60
        if elapsed > 0:
            changes_per_minute.append((current.docks - previous.docks) / elapsed)  # type: ignore[operator]
    return {
        f"docks_avg_{prefix}": weighted_sum / covered_seconds,
        f"docks_change_{prefix}": change,
        f"docks_slope_{prefix}": change / elapsed_minutes if elapsed_minutes > 0 else None,
        f"docks_volatility_{prefix}": (
            statistics.pstdev(changes_per_minute) if len(changes_per_minute) >= 2 else 0.0
        ),
        f"coverage_{prefix}": coverage,
    }


def rolling_bike_features(
    observations: list[FeatureObservation],
    *,
    decision_time: datetime,
    window_minutes: int,
    max_carry_minutes: int = 5,
    min_coverage: float = 0.80,
) -> dict[str, float | int | None]:
    window_start = decision_time - timedelta(minutes=window_minutes)
    usable = sorted(
        (
            observation
            for observation in observations
            if observation.bikes is not None
            and observation.retrieved_at <= decision_time
            and observation.ingested_at <= decision_time
            and observation.retrieved_at >= window_start - timedelta(minutes=max_carry_minutes)
        ),
        key=lambda item: (item.retrieved_at, item.ingested_at),
    )
    distinct: list[FeatureObservation] = []
    seen_report_times: set[datetime] = set()
    for observation in usable:
        report_time = observation.source_last_reported or observation.retrieved_at
        if report_time in seen_report_times:
            continue
        seen_report_times.add(report_time)
        distinct.append(observation)

    covered_seconds = 0.0
    weighted_sum = 0.0
    max_carry = timedelta(minutes=max_carry_minutes)
    for index, observation in enumerate(usable):
        start = max(observation.retrieved_at, window_start)
        next_time = usable[index + 1].retrieved_at if index + 1 < len(usable) else decision_time
        end = min(next_time, observation.retrieved_at + max_carry, decision_time)
        seconds = max((end - start).total_seconds(), 0)
        if seconds:
            bikes = observation.bikes
            assert bikes is not None
            covered_seconds += seconds
            weighted_sum += float(bikes) * seconds
    window_seconds = window_minutes * 60
    coverage = min(covered_seconds / window_seconds, 1.0) if window_seconds else 0.0
    sufficient = coverage >= min_coverage and len(distinct) >= 3
    prefix = f"{window_minutes}m"
    if not sufficient:
        return {
            f"bikes_avg_{prefix}": None,
            f"bikes_change_{prefix}": None,
            f"bikes_slope_{prefix}": None,
            f"bikes_volatility_{prefix}": None,
            f"bikes_coverage_{prefix}": coverage,
        }

    first, last = distinct[0], distinct[-1]
    elapsed_minutes = (last.retrieved_at - first.retrieved_at).total_seconds() / 60
    change = float(last.bikes - first.bikes)  # type: ignore[operator]
    changes_per_minute: list[float] = []
    for previous, current in pairwise(distinct):
        elapsed = (current.retrieved_at - previous.retrieved_at).total_seconds() / 60
        if elapsed > 0:
            changes_per_minute.append((current.bikes - previous.bikes) / elapsed)  # type: ignore[operator]
    return {
        f"bikes_avg_{prefix}": weighted_sum / covered_seconds,
        f"bikes_change_{prefix}": change,
        f"bikes_slope_{prefix}": change / elapsed_minutes if elapsed_minutes > 0 else None,
        f"bikes_volatility_{prefix}": (
            statistics.pstdev(changes_per_minute) if len(changes_per_minute) >= 2 else 0.0
        ),
        f"bikes_coverage_{prefix}": coverage,
    }


def build_station_features(
    *,
    station_id: str,
    decision_time: datetime,
    horizon_minutes: int,
    histories: dict[str, list[FeatureObservation]],
    metadata: dict[str, StationMetadata],
    station_max_age_seconds: int = 300,
) -> dict[str, float | int | None]:
    if horizon_minutes not in {5, 10, 15, 30}:
        raise ValueError("unsupported horizon")
    target_metadata = metadata[station_id]
    target_history = _point_in_time_history(histories.get(station_id, []), decision_time)
    if not target_history:
        raise ValueError("target station has no observation available at decision time")
    current = target_history[-1]
    features: dict[str, float | int | None] = dict(
        temporal_features(decision_time, horizon_minutes)
    )
    features.update(
        {
            "lat": target_metadata.lat,
            "lon": target_metadata.lon,
            "docks_now": current.docks,
            "bikes_now": current.bikes,
            "docks_disabled_now": current.docks_disabled,
            "bikes_disabled_now": current.bikes_disabled,
            "capacity": target_metadata.capacity,
            "dock_ratio": _safe_ratio(current.docks, target_metadata.capacity),
            "bike_ratio": _safe_ratio(current.bikes, target_metadata.capacity),
            "is_installed": _bool_number(current.is_installed),
            "is_renting": _bool_number(current.is_renting),
            "is_returning": _bool_number(current.is_returning),
            "capacity_missing": int(not target_metadata.capacity),
            "docks_missing": int(current.docks is None),
        }
    )
    coverages: list[float] = []
    for window in (5, 15, 30):
        rolling = rolling_dock_features(
            target_history,
            decision_time=decision_time,
            window_minutes=window,
        )
        features.update(rolling)
        coverages.append(float(rolling[f"coverage_{window}m"] or 0))
        rolling_bikes = rolling_bike_features(
            target_history,
            decision_time=decision_time,
            window_minutes=window,
        )
        features.update(rolling_bikes)
        coverages.append(float(rolling_bikes[f"bikes_coverage_{window}m"] or 0))
    features["history_missing"] = int(not all(coverage >= 0.80 for coverage in coverages))

    neighbour_metadata = sorted(
        (
            (
                haversine_metres(
                    target_metadata.lat,
                    target_metadata.lon,
                    item.lat,
                    item.lon,
                ),
                item,
            )
            for item in metadata.values()
            if item.station_id != station_id and _metadata_known(item, decision_time)
        ),
        key=lambda item: (item[0], item[1].station_id),
    )
    distances = [distance for distance, _ in neighbour_metadata]
    features.update(
        {
            "nearest_neighbor_m": distances[0] if distances else None,
            "station_density_250m": sum(distance <= 250 for distance in distances),
            "station_density_500m": sum(distance <= 500 for distance in distances),
            "station_density_750m": sum(distance <= 750 for distance in distances),
        }
    )
    expected = [(distance, item) for distance, item in neighbour_metadata if distance <= 1000][:5]
    fresh: list[tuple[float, StationMetadata, FeatureObservation]] = []
    for distance, item in expected:
        history = _point_in_time_history(histories.get(item.station_id, []), decision_time)
        if not history:
            continue
        observation = history[-1]
        source_time = observation.source_last_reported
        if source_time is None:
            continue
        age = (decision_time - source_time).total_seconds()
        if -30 <= age <= station_max_age_seconds:
            fresh.append((distance, item, observation))
    features.update(_neighbor_features(expected, fresh, histories, decision_time))
    return {name: features.get(name) for name in FEATURE_NAMES}


def _neighbor_features(
    expected: list[tuple[float, StationMetadata]],
    fresh: list[tuple[float, StationMetadata, FeatureObservation]],
    histories: dict[str, list[FeatureObservation]],
    decision_time: datetime,
) -> dict[str, float | int | None]:
    if not fresh:
        return {
            "neighbor_expected_count": len(expected),
            "neighbor_fresh_count": 0,
            "neighbor_mean_distance_m": None,
            "neighbor_total_docks": None,
            "neighbor_capacity_weighted_dock_ratio": None,
            "neighbor_full_proportion": None,
            "neighbor_mean_15m_dock_trend": None,
        }
    distances = [item[0] for item in fresh]
    known_docks = [item[2].docks for item in fresh if item[2].docks is not None]
    ratio_numerator = sum(
        item[2].docks or 0
        for item in fresh
        if item[2].docks is not None and item[1].capacity and item[1].capacity > 0
    )
    ratio_denominator = sum(
        item[1].capacity or 0
        for item in fresh
        if item[2].docks is not None and item[1].capacity and item[1].capacity > 0
    )
    trends: list[float] = []
    for _, item, _ in fresh:
        rolling = rolling_dock_features(
            _point_in_time_history(histories.get(item.station_id, []), decision_time),
            decision_time=decision_time,
            window_minutes=15,
        )
        trend = rolling["docks_slope_15m"]
        if trend is not None:
            trends.append(float(trend))
    return {
        "neighbor_expected_count": len(expected),
        "neighbor_fresh_count": len(fresh),
        "neighbor_mean_distance_m": statistics.fmean(distances),
        "neighbor_total_docks": sum(known_docks) if known_docks else None,
        "neighbor_capacity_weighted_dock_ratio": (
            ratio_numerator / ratio_denominator if ratio_denominator else None
        ),
        "neighbor_full_proportion": (
            sum(docks == 0 for docks in known_docks) / len(known_docks) if known_docks else None
        ),
        "neighbor_mean_15m_dock_trend": statistics.fmean(trends) if trends else None,
    }


def _point_in_time_history(
    observations: list[FeatureObservation], decision_time: datetime
) -> list[FeatureObservation]:
    return sorted(
        (
            item
            for item in observations
            if item.ingested_at <= decision_time and item.retrieved_at <= decision_time
        ),
        key=lambda item: (item.retrieved_at, item.ingested_at),
    )


def _metadata_known(metadata: StationMetadata, decision_time: datetime) -> bool:
    return metadata.known_from_at <= decision_time and (
        metadata.known_to_at is None or metadata.known_to_at > decision_time
    )


def _safe_ratio(value: int | None, capacity: int | None) -> float | None:
    return value / capacity if value is not None and capacity and capacity > 0 else None


def _bool_number(value: bool | None) -> int | None:
    return int(value) if value is not None else None
