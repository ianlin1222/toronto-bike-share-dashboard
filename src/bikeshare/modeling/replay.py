from __future__ import annotations

import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import numpy as np

SEED = 20_260_907


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    request_id: str
    utc_day: date
    policy_id: str
    recommended: bool
    otherwise_evaluable: bool
    outcome: int | None
    distance_m: float | None


def summarize_policy(outcomes: list[ReplayOutcome]) -> dict[str, float | int | None]:
    protocol_requests = len(outcomes)
    evaluable = sum(item.otherwise_evaluable for item in outcomes)
    abstentions = sum(item.otherwise_evaluable and not item.recommended for item in outcomes)
    known = [item for item in outcomes if item.recommended and item.outcome is not None]
    successes = sum(item.outcome == 1 for item in known)
    missing = sum(item.recommended and item.outcome is None for item in outcomes)
    distances = [item.distance_m for item in known if item.distance_m is not None]
    return {
        "successes": successes,
        "known_recommendation_outcomes": len(known),
        "protocol_requests": protocol_requests,
        "otherwise_evaluable_requests": evaluable,
        "abstentions": abstentions,
        "missing_outcomes": missing,
        "conditional_success_rate": successes / len(known) if known else None,
        "coverage_rate": len(known) / protocol_requests if protocol_requests else None,
        "end_to_end_success_rate": successes / evaluable if evaluable else None,
        "median_distance_m": statistics.median(distances) if distances else None,
        "p90_distance_m": _percentile(distances, 0.90) if distances else None,
    }


def matched_paired_uplift(
    forecast: list[ReplayOutcome],
    baseline: list[ReplayOutcome],
    *,
    bootstrap_resamples: int = 2000,
    seed: int = SEED,
) -> dict[str, float | int | None]:
    baseline_by_request = {item.request_id: item for item in baseline}
    matched = [
        (item, baseline_by_request[item.request_id])
        for item in forecast
        if item.request_id in baseline_by_request
        and item.outcome is not None
        and baseline_by_request[item.request_id].outcome is not None
    ]
    if not matched:
        return {"matched_cases": 0, "uplift": None, "ci_lower": None, "ci_upper": None}
    day_differences: dict[date, list[int]] = defaultdict(list)
    differences: list[int] = []
    for forecast_item, baseline_item in matched:
        difference = int(forecast_item.outcome == 1) - int(baseline_item.outcome == 1)
        differences.append(difference)
        day_differences[forecast_item.utc_day].append(difference)
    days = sorted(day_differences)
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(bootstrap_resamples):
        sampled_days = [rng.choice(days) for _ in days]
        sampled = [value for sampled_day in sampled_days for value in day_differences[sampled_day]]
        samples.append(statistics.fmean(sampled))
    return {
        "matched_cases": len(matched),
        "uplift": statistics.fmean(differences),
        "ci_lower": _percentile(samples, 0.025),
        "ci_upper": _percentile(samples, 0.975),
    }


def _percentile(values: list[float], quantile: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), quantile))
