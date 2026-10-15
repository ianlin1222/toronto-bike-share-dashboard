from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bikeshare.modeling.splits import SplitName, assign_split, readiness_splits


def test_split_boundary_purges_labels_and_applies_embargo() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    splits = readiness_splits(start)
    assert assign_split(start + timedelta(days=1), horizon_minutes=30, splits=splits) is SplitName.TRAIN
    # Label would overlap the 30-minute embargo before model validation.
    assert assign_split(
        start + timedelta(days=49) - timedelta(minutes=45),
        horizon_minutes=30,
        splits=splits,
    ) is None
    # First 30 minutes of each later fold are embargoed.
    assert assign_split(
        start + timedelta(days=49, minutes=10),
        horizon_minutes=5,
        splits=splits,
    ) is None
