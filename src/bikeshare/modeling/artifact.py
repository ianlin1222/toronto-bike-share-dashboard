from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib

from bikeshare.features import FEATURE_NAMES, FEATURE_VERSION, feature_schema_hash


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    run_id: str
    source_kind: str
    algorithm: str
    feature_version: str
    feature_schema_hash: str
    feature_names: tuple[str, ...]
    artifact_sha256: str
    calibrated: bool
    approved: bool
    metrics: dict[str, float | int | None]


def save_artifact(model: Any, manifest_without_hash: dict[str, Any], artifact_path: Path) -> ArtifactManifest:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_path)
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    manifest = ArtifactManifest(
        run_id=str(manifest_without_hash["run_id"]),
        source_kind=str(manifest_without_hash["source_kind"]),
        algorithm=str(manifest_without_hash["algorithm"]),
        feature_version=FEATURE_VERSION,
        feature_schema_hash=feature_schema_hash(),
        feature_names=FEATURE_NAMES,
        artifact_sha256=digest,
        calibrated=bool(manifest_without_hash.get("calibrated", False)),
        approved=bool(manifest_without_hash.get("approved", False)),
        metrics=dict(manifest_without_hash.get("metrics", {})),
    )
    manifest_path = artifact_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    return manifest


def load_approved_artifact(artifact_path: Path, manifest_path: Path) -> tuple[Any, ArtifactManifest]:
    data = json.loads(manifest_path.read_text())
    data["feature_names"] = tuple(data["feature_names"])
    manifest = ArtifactManifest(**data)
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    if digest != manifest.artifact_sha256:
        raise ValueError("model artifact SHA-256 mismatch")
    if manifest.feature_version != FEATURE_VERSION or manifest.feature_schema_hash != feature_schema_hash():
        raise ValueError("model feature schema mismatch")
    if manifest.feature_names != FEATURE_NAMES:
        raise ValueError("model feature order mismatch")
    if manifest.source_kind != "live" or not manifest.approved or not manifest.calibrated:
        raise ValueError("artifact has not passed live validation and approval gates")
    return joblib.load(artifact_path), manifest
