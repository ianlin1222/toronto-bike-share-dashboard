from __future__ import annotations

from pathlib import Path

import pytest

from bikeshare.modeling.artifact import load_approved_artifact, save_artifact


def test_fixture_artifact_cannot_be_loaded_as_approved_model(tmp_path: Path) -> None:
    artifact = tmp_path / "fixture.joblib"
    save_artifact(
        {"model": "fixture"},
        {
            "run_id": "fixture-run",
            "source_kind": "fixture",
            "algorithm": "test",
            "calibrated": False,
            "approved": False,
            "metrics": {"fixture_only": 1},
        },
        artifact,
    )
    with pytest.raises(ValueError, match="live validation"):
        load_approved_artifact(artifact, artifact.with_suffix(".manifest.json"))


def test_artifact_hash_tampering_fails_before_loading(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.joblib"
    save_artifact(
        {"model": "candidate"},
        {
            "run_id": "candidate-run",
            "source_kind": "live",
            "algorithm": "test",
            "calibrated": True,
            "approved": True,
        },
        artifact,
    )
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        load_approved_artifact(artifact, artifact.with_suffix(".manifest.json"))
