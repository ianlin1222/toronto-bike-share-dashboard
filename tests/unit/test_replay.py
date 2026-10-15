from __future__ import annotations

from datetime import date

import pytest

from bikeshare.modeling.replay import ReplayOutcome, matched_paired_uplift, summarize_policy


def outcome(
    request_id: str,
    day: int,
    result: int | None,
    *,
    recommended: bool = True,
    evaluable: bool = True,
) -> ReplayOutcome:
    return ReplayOutcome(
        request_id=request_id,
        utc_day=date(2026, 1, day),
        policy_id="policy",
        recommended=recommended,
        otherwise_evaluable=evaluable,
        outcome=result,
        distance_m=100.0 if recommended else None,
    )


def test_end_to_end_metric_penalizes_abstentions_and_missing_outcomes() -> None:
    summary = summarize_policy(
        [
            outcome("success", 1, 1),
            outcome("failure", 1, 0),
            outcome("missing", 2, None),
            outcome("abstain", 2, None, recommended=False),
        ]
    )
    assert summary["conditional_success_rate"] == 0.5
    assert summary["coverage_rate"] == 0.5
    assert summary["end_to_end_success_rate"] == 0.25
    assert summary["abstentions"] == 1
    assert summary["missing_outcomes"] == 1


def test_matched_uplift_discloses_complete_case_count_and_is_deterministic() -> None:
    forecast = [outcome("a", 1, 1), outcome("b", 2, 1), outcome("unknown", 2, None)]
    baseline = [outcome("a", 1, 0), outcome("b", 2, 1), outcome("unknown", 2, 0)]
    first = matched_paired_uplift(forecast, baseline, bootstrap_resamples=50)
    second = matched_paired_uplift(forecast, baseline, bootstrap_resamples=50)
    assert first == second
    assert first["matched_cases"] == 2
    assert first["uplift"] == pytest.approx(0.5)
