from __future__ import annotations

from bikeshare.modeling.pipeline import CandidateResult, select_candidate


def candidate(algorithm: str, brier: float, log_loss: float) -> CandidateResult:
    return CandidateResult(
        algorithm=algorithm,
        feature_group="plus_nearby",
        parameters={"C": 1},
        estimator=object(),
        metrics={"brier": brier, "log_loss": log_loss, "roc_auc": 0.5, "pr_auc": 0.5},
    )


def test_selection_uses_brier_tolerance_then_log_loss() -> None:
    best_brier = candidate("hist_gradient_boosting", 0.1800, 0.55)
    within_tolerance = candidate("logistic_regression", 0.1809, 0.50)
    outside_tolerance = candidate("logistic_regression", 0.1820, 0.40)
    assert (
        select_candidate((best_brier, within_tolerance, outside_tolerance))
        is within_tolerance
    )


def test_selection_prefers_logistic_when_probability_metrics_tie() -> None:
    logistic = candidate("logistic_regression", 0.18, 0.50)
    boosted = candidate("hist_gradient_boosting", 0.18, 0.50)
    assert select_candidate((boosted, logistic)) is logistic
