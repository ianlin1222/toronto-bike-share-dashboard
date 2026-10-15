from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from bikeshare.features import FEATURE_NAMES

SEED = 20_260_907

TEMPORAL_SPATIAL_CURRENT = tuple(
    name
    for name in FEATURE_NAMES
    if not name.startswith("docks_avg_")
    and not name.startswith("docks_change_")
    and not name.startswith("docks_slope_")
    and not name.startswith("docks_volatility_")
    and not name.startswith("coverage_")
    and not name.startswith("bikes_avg_")
    and not name.startswith("bikes_change_")
    and not name.startswith("bikes_slope_")
    and not name.startswith("bikes_volatility_")
    and not name.startswith("bikes_coverage_")
    and not name.startswith("neighbor_")
)
ROLLING_FEATURES = tuple(
    name
    for name in FEATURE_NAMES
    if name.startswith(
        (
            "docks_avg_",
            "docks_change_",
            "docks_slope_",
            "docks_volatility_",
            "coverage_",
            "bikes_avg_",
            "bikes_change_",
            "bikes_slope_",
            "bikes_volatility_",
            "bikes_coverage_",
        )
    )
)
NEARBY_FEATURES = tuple(name for name in FEATURE_NAMES if name.startswith("neighbor_"))
FEATURE_GROUPS = {
    "temporal_spatial_current": TEMPORAL_SPATIAL_CURRENT,
    "plus_rolling": (*TEMPORAL_SPATIAL_CURRENT, *ROLLING_FEATURES),
    "plus_nearby": FEATURE_NAMES,
}


@dataclass(frozen=True, slots=True)
class CandidateResult:
    algorithm: str
    feature_group: str
    parameters: dict[str, float | int]
    estimator: Any
    metrics: dict[str, float]


def fit_validation_candidates(
    train_features: pd.DataFrame,
    train_labels: pd.Series,
    validation_features: pd.DataFrame,
    validation_labels: pd.Series,
) -> tuple[CandidateResult, ...]:
    _validate_binary_labels(train_labels, "training")
    _validate_binary_labels(validation_labels, "validation")
    results: list[CandidateResult] = []
    for group_name, names in FEATURE_GROUPS.items():
        train_x = train_features.loc[:, names]
        validation_x = validation_features.loc[:, names]
        for c_value in (0.1, 1.0, 10.0):
            estimator = _logistic(c_value)
            estimator.fit(train_x, train_labels)
            probabilities = estimator.predict_proba(validation_x)[:, 1]
            results.append(
                CandidateResult(
                    algorithm="logistic_regression",
                    feature_group=group_name,
                    parameters={"C": c_value},
                    estimator=estimator,
                    metrics=_probability_metrics(validation_labels, probabilities),
                )
            )
        for learning_rate, leaf_nodes, minimum_leaf in product(
            (0.05, 0.1),
            (15, 31),
            (50, 200),
        ):
            parameters: dict[str, float | int] = {
                "learning_rate": learning_rate,
                "max_leaf_nodes": leaf_nodes,
                "min_samples_leaf": minimum_leaf,
                "max_iter": 200,
                "l2_regularization": 1,
            }
            estimator = HistGradientBoostingClassifier(
                **parameters,
                early_stopping=False,
                random_state=SEED,
            )
            estimator.fit(train_x, train_labels)
            probabilities = estimator.predict_proba(validation_x)[:, 1]
            results.append(
                CandidateResult(
                    algorithm="hist_gradient_boosting",
                    feature_group=group_name,
                    parameters=parameters,
                    estimator=estimator,
                    metrics=_probability_metrics(validation_labels, probabilities),
                )
            )
    return tuple(results)


def select_candidate(results: tuple[CandidateResult, ...]) -> CandidateResult:
    if not results:
        raise ValueError("no validation candidates")
    best_brier = min(result.metrics["brier"] for result in results)
    contenders = [result for result in results if result.metrics["brier"] <= best_brier + 0.001]
    return min(
        contenders,
        key=lambda result: (
            result.metrics["log_loss"],
            0 if result.algorithm == "logistic_regression" else 1,
            result.feature_group,
            tuple(sorted(result.parameters.items())),
        ),
    )


def refit_selected(
    selected: CandidateResult,
    features: pd.DataFrame,
    labels: pd.Series,
) -> Any:
    names = FEATURE_GROUPS[selected.feature_group]
    if selected.algorithm == "logistic_regression":
        estimator = _logistic(float(selected.parameters["C"]))
    else:
        estimator = HistGradientBoostingClassifier(
            **selected.parameters,
            early_stopping=False,
            random_state=SEED,
        )
    estimator.fit(features.loc[:, names], labels)
    return estimator


def fit_sigmoid_calibrator(
    fitted_estimator: Any,
    calibration_features: pd.DataFrame,
    calibration_labels: pd.Series,
    *,
    feature_group: str,
) -> CalibratedClassifierCV:
    _validate_binary_labels(calibration_labels, "calibration")
    calibrator = CalibratedClassifierCV(FrozenEstimator(fitted_estimator), method="sigmoid")
    calibrator.fit(calibration_features.loc[:, FEATURE_GROUPS[feature_group]], calibration_labels)
    return calibrator


def _logistic(c_value: float) -> Pipeline:
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(C=c_value, l1_ratio=0, max_iter=1000, random_state=SEED),
            ),
        ]
    )


def _probability_metrics(labels: pd.Series, probabilities: np.ndarray[Any, Any]) -> dict[str, float]:
    return {
        "brier": float(brier_score_loss(labels, probabilities)),
        "log_loss": float(log_loss(labels, probabilities)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "pr_auc": float(average_precision_score(labels, probabilities)),
    }


def _validate_binary_labels(labels: pd.Series, period_name: str) -> None:
    observed = set(labels.dropna().astype(int).unique())
    if observed != {0, 1}:
        raise ValueError(f"{period_name} period must contain both target classes")
