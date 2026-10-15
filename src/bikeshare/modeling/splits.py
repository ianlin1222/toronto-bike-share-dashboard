from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class SplitName(StrEnum):
    TRAIN = "train"
    MODEL_VALIDATION = "model_validation"
    CALIBRATION = "calibration"
    POLICY_SELECTION = "policy_selection"
    FINAL_TEST = "final_test"


@dataclass(frozen=True, slots=True)
class TimeSplit:
    name: SplitName
    start: datetime
    end: datetime


def readiness_splits(start: datetime) -> tuple[TimeSplit, ...]:
    day = timedelta(days=1)
    return (
        TimeSplit(SplitName.TRAIN, start, start + 49 * day),
        TimeSplit(SplitName.MODEL_VALIDATION, start + 49 * day, start + 56 * day),
        TimeSplit(SplitName.CALIBRATION, start + 56 * day, start + 63 * day),
        TimeSplit(SplitName.POLICY_SELECTION, start + 63 * day, start + 70 * day),
        TimeSplit(SplitName.FINAL_TEST, start + 70 * day, start + 84 * day),
    )


def assign_split(
    decision_time: datetime,
    *,
    horizon_minutes: int,
    splits: tuple[TimeSplit, ...],
    embargo_minutes: int = 30,
) -> SplitName | None:
    label_time = decision_time + timedelta(minutes=horizon_minutes)
    embargo = timedelta(minutes=embargo_minutes)
    for split in splits:
        usable_start = split.start + (embargo if split.name is not SplitName.TRAIN else timedelta())
        usable_end = split.end - embargo
        if usable_start <= decision_time and label_time < usable_end:
            return split.name
    return None
