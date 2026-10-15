from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bikeshare.modeling.labels import FutureSnapshot, future_dock_label


def snapshot(
    retrieved_at: datetime,
    *,
    docks: int | None,
    installed: bool | None = True,
    returning: bool | None = True,
    reported_age_seconds: int = 30,
) -> FutureSnapshot:
    return FutureSnapshot(
        retrieved_at=retrieved_at,
        source_last_reported=retrieved_at - timedelta(seconds=reported_age_seconds),
        is_installed=installed,
        is_returning=returning,
        num_docks_available=docks,
    )


def test_label_uses_first_fresh_observation_after_arrival() -> None:
    decision = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    arrival = decision + timedelta(minutes=15)
    result = future_dock_label(
        [snapshot(arrival + timedelta(seconds=60), docks=2)],
        decision_time=decision,
        horizon_minutes=15,
    )
    assert result.label == 1


def test_stale_or_missing_future_is_unknown_not_failure() -> None:
    decision = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    arrival = decision + timedelta(minutes=15)
    stale = future_dock_label(
        [snapshot(arrival + timedelta(seconds=30), docks=0, reported_age_seconds=301)],
        decision_time=decision,
        horizon_minutes=15,
    )
    missing = future_dock_label([], decision_time=decision, horizon_minutes=15)
    assert stale.label is None
    assert missing.label is None


def test_known_false_condition_is_negative_even_if_another_field_missing() -> None:
    decision = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    arrival = decision + timedelta(minutes=5)
    result = future_dock_label(
        [snapshot(arrival, docks=None, returning=False)],
        decision_time=decision,
        horizon_minutes=5,
    )
    assert result.label == 0
