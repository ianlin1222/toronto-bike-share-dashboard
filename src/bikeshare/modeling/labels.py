from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class FutureSnapshot:
    retrieved_at: datetime
    source_last_reported: datetime | None
    is_installed: bool | None
    is_returning: bool | None
    num_docks_available: int | None
    canonical: bool = True


@dataclass(frozen=True, slots=True)
class LabelResult:
    label: int | None
    matched: FutureSnapshot | None
    unknown_reason: str | None


def future_dock_label(
    snapshots: list[FutureSnapshot],
    *,
    decision_time: datetime,
    horizon_minutes: int,
    match_tolerance_seconds: int = 90,
    freshness_seconds: int = 300,
) -> LabelResult:
    if horizon_minutes not in {5, 10, 15, 30}:
        raise ValueError("unsupported horizon")
    arrival = decision_time + timedelta(minutes=horizon_minutes)
    deadline = arrival + timedelta(seconds=match_tolerance_seconds)
    matched = next(
        (
            item
            for item in sorted(snapshots, key=lambda value: value.retrieved_at)
            if item.canonical and arrival <= item.retrieved_at <= deadline
        ),
        None,
    )
    if matched is None:
        return LabelResult(None, None, "no_future_observation_within_tolerance")
    if matched.source_last_reported is None:
        return LabelResult(None, matched, "missing_future_report_timestamp")
    report_age = (matched.retrieved_at - matched.source_last_reported).total_seconds()
    if report_age < -30 or report_age > freshness_seconds:
        return LabelResult(None, matched, "stale_or_future_report_timestamp")
    if matched.is_installed is False or matched.is_returning is False:
        return LabelResult(0, matched, None)
    if matched.num_docks_available == 0:
        return LabelResult(0, matched, None)
    if (
        matched.is_installed is True
        and matched.is_returning is True
        and matched.num_docks_available is not None
        and matched.num_docks_available >= 1
    ):
        return LabelResult(1, matched, None)
    return LabelResult(None, matched, "future_target_fields_missing")
