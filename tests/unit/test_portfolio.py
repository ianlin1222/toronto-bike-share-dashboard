"""Reconcile the public, frozen SQL extracts without live database access."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "analysis/portfolio"


def test_portfolio_aggregate_reconciliation():
    d = json.loads((HERE / "data/analysis.json").read_text())
    q = d["quality"][0]
    for name in ["stations", "daily", "time_patterns", "station_days"]:
        assert sum(r["reports"] for r in d[name]) == q["eligible_reports"]
        assert sum(r["available_reports"] for r in d[name]) == q["available_reports"]
        assert sum(r["docks_sum"] for r in d[name]) == q["docks_sum"]
    assert q["full_reports"] + q["available_reports"] == q["eligible_reports"]
    assert q["fresh_unique_reports"] + q["stale_unique_reports"] == q["unique_reports"]
    assert (
        q["fresh_unique_reports"] - q["nonoperational_or_unknown_reports"] - q["missing_docks"]
    ) == q["eligible_reports"]
    assert sum(r["successful_minutes"] for r in d["daily"]) == q["successful_minutes"]
    assert all(
        0 <= r["nearby_available_reports"] <= r["matched_reports"] <= r["full_reports"]
        for r in d["nearby"]
    )


def test_portfolio_hashes_and_period():
    manifest = json.loads((HERE / "data/manifest.json").read_text())
    assert (
        hashlib.sha256((HERE / "data/analysis.json").read_bytes()).hexdigest()
        == manifest["analysis_json_sha256"]
    )
    for folder, key in [("data", "csv_sha256"), ("sql", "sql_sha256")]:
        for name, expected in manifest[key].items():
            assert hashlib.sha256((HERE / folder / name).read_bytes()).hexdigest() == expected
    cfg = manifest["configuration"]
    assert cfg == json.loads((HERE / "config.json").read_text())
    minutes = (
        datetime.fromisoformat(cfg["end_utc_exclusive"]) - datetime.fromisoformat(cfg["start_utc"])
    ).total_seconds() / 60
    q = json.loads((HERE / "data/analysis.json").read_text())["quality"][0]
    assert minutes == q["expected_minutes"]
    assert q["successful_minutes"] <= q["attempted_minutes"] <= minutes
