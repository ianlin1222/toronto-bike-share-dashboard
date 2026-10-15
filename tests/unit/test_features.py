from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from bikeshare.features import (
    FEATURE_NAMES,
    FeatureObservation,
    StationMetadata,
    build_station_features,
    feature_schema_hash,
    rolling_bike_features,
    rolling_dock_features,
    temporal_features,
)


def observation(
    station_id: str,
    retrieved_at: datetime,
    docks: int,
    *,
    ingested_at: datetime | None = None,
) -> FeatureObservation:
    return FeatureObservation(
        station_id=station_id,
        retrieved_at=retrieved_at,
        ingested_at=ingested_at or retrieved_at + timedelta(seconds=1),
        source_last_reported=retrieved_at,
        docks=docks,
        bikes=10 - docks,
        docks_disabled=0,
        bikes_disabled=0,
        is_installed=True,
        is_renting=True,
        is_returning=True,
    )


def test_toronto_dst_spring_and_fall_are_unambiguous_in_utc() -> None:
    before_spring = temporal_features(datetime(2026, 3, 8, 6, 30, tzinfo=UTC), 15)
    after_spring = temporal_features(datetime(2026, 3, 8, 7, 30, tzinfo=UTC), 15)
    first_fall_fold = temporal_features(datetime(2026, 11, 1, 5, 30, tzinfo=UTC), 15)
    second_fall_fold = temporal_features(datetime(2026, 11, 1, 6, 30, tzinfo=UTC), 15)

    assert before_spring["local_hour"] == 1
    assert before_spring["local_weekday"] == 6
    assert before_spring["utc_offset_minutes"] == -300
    assert after_spring["local_hour"] == 3
    assert after_spring["utc_offset_minutes"] == -240
    assert first_fall_fold["local_hour"] == second_fall_fold["local_hour"] == 1
    assert first_fall_fold["dst_flag"] == 1
    assert second_fall_fold["dst_flag"] == 0


def test_irregular_rolling_window_requires_coverage_and_distinct_reports() -> None:
    decision = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    history = [
        observation("a", decision - timedelta(minutes=5), 5),
        observation("a", decision - timedelta(minutes=3), 4),
        observation("a", decision - timedelta(minutes=1), 2),
        observation("a", decision, 1, ingested_at=decision),
    ]
    result = rolling_dock_features(history, decision_time=decision, window_minutes=5)
    assert result["coverage_5m"] == pytest.approx(1.0)
    assert result["docks_change_5m"] == -4
    assert result["docks_slope_5m"] == pytest.approx(-0.8)

    outage = rolling_dock_features(history[:1], decision_time=decision, window_minutes=5)
    assert outage["docks_avg_5m"] is None
    assert outage["coverage_5m"] == pytest.approx(1.0)

    bikes = rolling_bike_features(history, decision_time=decision, window_minutes=5)
    assert bikes["bikes_change_5m"] == 4
    assert bikes["bikes_slope_5m"] == pytest.approx(0.8)


def test_point_in_time_feature_builder_ignores_rows_ingested_after_decision() -> None:
    decision = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    history = [
        observation("a", decision - timedelta(minutes=5), 5),
        observation("a", decision - timedelta(minutes=3), 4),
        observation("a", decision - timedelta(minutes=1), 3),
        observation(
            "a",
            decision - timedelta(seconds=30),
            0,
            ingested_at=decision + timedelta(seconds=1),
        ),
    ]
    metadata = {
        "a": StationMetadata("a", 43.6532, -79.3832, 10, decision - timedelta(days=1)),
        "b": StationMetadata("b", 43.6540, -79.3832, 12, decision - timedelta(days=1)),
    }
    neighbor_history = [
        observation("b", decision - timedelta(minutes=5), 1),
        observation("b", decision - timedelta(minutes=3), 2),
        observation("b", decision - timedelta(minutes=1), 3),
    ]
    features = build_station_features(
        station_id="a",
        decision_time=decision,
        horizon_minutes=15,
        histories={"a": history, "b": neighbor_history},
        metadata=metadata,
    )
    assert tuple(features) == FEATURE_NAMES
    assert features["docks_now"] == 3
    assert features["bikes_change_5m"] == 2
    assert features["neighbor_fresh_count"] == 1
    assert len(feature_schema_hash()) == 64
