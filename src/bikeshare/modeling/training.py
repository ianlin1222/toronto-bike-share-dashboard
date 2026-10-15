from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from bikeshare.config import Settings
from bikeshare.modeling.artifact import save_artifact

SEED = 20_260_907


class LiveDataNotReady(RuntimeError):
    pass


def train(*, dataset: str, settings: Settings) -> dict[str, Any]:
    if dataset == "live":
        raise LiveDataNotReady(
            "live training is gated until the 84-day coverage, completeness, class-balance, "
            "label-coverage, and leakage audits pass"
        )
    rng = np.random.default_rng(SEED)
    rows = 1000
    # This deterministic fixture validates serialization and inference only. It is
    # intentionally not drawn from or presented as Toronto performance evidence.
    docks = rng.integers(0, 11, rows)
    distance = rng.uniform(0, 1000, rows)
    horizon = rng.choice([5, 10, 15, 30], rows)
    x = np.column_stack((docks, distance, horizon))
    y = ((docks - horizon / 10 + rng.normal(0, 2, rows)) > 0).astype(int)
    pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(C=1.0, l1_ratio=0, max_iter=500)),
        ]
    )
    pipeline.fit(x[:800], y[:800])
    probabilities = pipeline.predict_proba(x[800:])[:, 1]
    metrics = {
        "fixture_brier": float(brier_score_loss(y[800:], probabilities)),
        "fixture_log_loss": float(log_loss(y[800:], probabilities)),
        "fixture_rows": rows,
    }
    training_hash = hashlib.sha256(
        json.dumps({"seed": SEED, "rows": rows, "metrics": metrics}, sort_keys=True).encode()
    ).hexdigest()
    run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fixture:{training_hash}"))
    artifact_path = settings.model_root / f"{run_id}.joblib"
    manifest = save_artifact(
        pipeline,
        {
            "run_id": run_id,
            "source_kind": "fixture",
            "algorithm": "logistic_regression_fixture_smoke",
            "calibrated": False,
            "approved": False,
            "metrics": metrics,
        },
        artifact_path,
    )
    return {
        "run_id": manifest.run_id,
        "source_kind": "fixture",
        "status": "software_smoke_only_not_approvable",
        "artifact_sha256": manifest.artifact_sha256,
        "metrics": metrics,
        "warning": "Fixture metrics are not real-world prediction or recommendation evidence.",
    }
