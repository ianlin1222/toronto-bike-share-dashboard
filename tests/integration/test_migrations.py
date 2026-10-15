from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect

pytestmark = pytest.mark.integration


def test_initial_migration_creates_operational_and_evaluation_tables(
    database_engine: Engine,
) -> None:
    tables = set(inspect(database_engine).get_table_names())
    assert {
        "source_datasets",
        "raw_payload_blobs",
        "poll_batches",
        "feed_fetches",
        "stations",
        "station_metadata_versions",
        "station_snapshots",
        "quarantine_records",
        "ingestion_events",
        "serving_feature_rows",
        "model_runs",
        "evaluation_runs",
        "recommendation_requests",
        "recommendation_results",
        "evaluation_outcomes",
    }.issubset(tables)
