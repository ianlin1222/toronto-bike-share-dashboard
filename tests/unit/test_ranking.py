from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bikeshare.db.types import CurrentStation
from bikeshare.ranking import PolicyVersion, eligible_candidates, rank_candidates


def station(
    station_id: str,
    lat: float,
    *,
    docks: int | None = 2,
    reported_age: int = 30,
    returning: bool = True,
) -> CurrentStation:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    return CurrentStation(
        station_id=station_id,
        lifecycle_state="active",
        name=station_id,
        lat=lat,
        lon=-79.3832,
        capacity=10,
        num_docks_available=docks,
        num_bikes_available=8,
        num_docks_disabled=0,
        num_bikes_disabled=0,
        is_installed=True,
        is_renting=True,
        is_returning=returning,
        source_last_reported=now - timedelta(seconds=reported_age),
        retrieved_at=now,
        ingested_at=now,
        feed_last_updated=now,
    )


def test_eligibility_explains_missing_stale_full_and_nonreturning() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    result = eligible_candidates(
        [
            station("eligible", 43.6533),
            station("full", 43.6534, docks=0),
            station("missing", 43.6535, docks=None),
            station("stale", 43.6536, reported_age=301),
            station("closed", 43.6537, returning=False),
        ],
        destination_lat=43.6532,
        destination_lon=-79.3832,
        radius_m=750,
        decision_time=now,
        station_max_age_seconds=300,
        require_current_dock=True,
    )
    assert [candidate.station.station_id for candidate in result.candidates] == ["eligible"]
    assert result.exclusions == {
        "no_current_dock": 1,
        "missing_dock_count": 1,
        "stale_or_missing_report": 1,
        "not_accepting_returns": 1,
    }


def test_nearest_policy_returns_distinct_stable_primary_and_alternative() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    result = eligible_candidates(
        [station("b", 43.6534), station("a", 43.6534), station("far", 43.655)],
        destination_lat=43.6532,
        destination_lon=-79.3832,
        radius_m=750,
        decision_time=now,
        station_max_age_seconds=300,
        require_current_dock=True,
    )
    ranked = rank_candidates(
        result.candidates,
        policy=PolicyVersion.NEAREST_CURRENT_DOCK,
        radius_m=750,
    )
    assert [item.candidate.station.station_id for item in ranked[:2]] == ["a", "b"]
    assert ranked[0].candidate.station.station_id != ranked[1].candidate.station.station_id


def test_missing_forecast_is_not_treated_as_zero_probability() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    result = eligible_candidates(
        [station("known", 43.6533), station("missing", 43.6534)],
        destination_lat=43.6532,
        destination_lon=-79.3832,
        radius_m=750,
        decision_time=now,
        station_max_age_seconds=300,
        require_current_dock=False,
    )
    ranked = rank_candidates(
        result.candidates,
        policy=PolicyVersion.FORECAST_DISTANCE,
        radius_m=750,
        probabilities={"known": 0.4},
    )
    assert [item.candidate.station.station_id for item in ranked] == ["known"]
