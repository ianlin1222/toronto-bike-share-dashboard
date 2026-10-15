from __future__ import annotations

import gzip
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from sqlalchemy import Engine, text

from bikeshare.ingestion.archive import archive_history

pytestmark = pytest.mark.integration


def test_archive_verifies_parquet_and_raw_hash_before_releasing_database_copy(
    database_engine: Engine,
    tmp_path: Path,
) -> None:
    observed_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    raw = b'{"archive":"test"}'
    compressed = gzip.compress(raw, mtime=0)
    digest = hashlib.sha256(raw).hexdigest()
    source_id = uuid.uuid4()
    batch_id = uuid.uuid4()
    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO source_datasets (
                    id, source_kind, system_id, discovery_url, importer_version
                ) VALUES (:id, 'fixture', 'archive_test', :url, 'test')
                """
            ),
            {"id": source_id, "url": f"https://example.test/{source_id}"},
        )
        connection.execute(
            text(
                """
                INSERT INTO poll_batches (
                    id, source_id, scheduled_at, started_at, ended_at, status,
                    expected_records, received_records, accepted_records,
                    quarantined_records, collector_version
                ) VALUES (
                    :id, :source_id, :at, :at, :at, 'success', 1, 1, 1, 0, 'test'
                )
                """
            ),
            {"id": batch_id, "source_id": source_id, "at": observed_at},
        )
        connection.execute(
            text(
                """
                INSERT INTO raw_payload_blobs (
                    sha256, content_type, uncompressed_bytes, stored_bytes, body
                ) VALUES (:sha, 'application/json', :raw_size, :stored_size, :body)
                ON CONFLICT (sha256) DO NOTHING
                """
            ),
            {
                "sha": digest,
                "raw_size": len(raw),
                "stored_size": len(compressed),
                "body": compressed,
            },
        )
        fetch_id = connection.scalar(
            text(
                """
                INSERT INTO feed_fetches (
                    batch_id, feed_name, url, attempt, http_status, retrieved_at,
                    ingested_at, raw_sha256, validation_state
                ) VALUES (
                    :batch, 'station_status', 'https://example.test/status', 1, 200,
                    :at, :at, :sha, 'valid'
                ) RETURNING id
                """
            ),
            {"batch": batch_id, "at": observed_at, "sha": digest},
        )
        connection.execute(
            text(
                """
                INSERT INTO stations (station_id, first_seen_at, last_seen_at)
                VALUES ('archive-test', :at, :at)
                ON CONFLICT (station_id) DO NOTHING
                """
            ),
            {"at": observed_at},
        )
        metadata_id = connection.scalar(
            text(
                """
                INSERT INTO station_metadata_versions (
                    station_id, metadata_hash, name, lat, lon, capacity,
                    known_from_at, source_fetch_id
                ) VALUES (
                    'archive-test', :hash, 'Archive Test', 43.65, -79.38, 10, :at, :fetch
                ) RETURNING id
                """
            ),
            {"hash": "a" * 64, "at": observed_at, "fetch": fetch_id},
        )
        snapshot_id = connection.scalar(
            text(
                """
                INSERT INTO station_snapshots (
                    retrieved_at, station_id, feed_fetch_id, metadata_version_id,
                    ingested_at, source_last_reported, num_docks_available,
                    is_installed, is_returning, provenance_kind
                ) VALUES (:at, 'archive-test', :fetch, :metadata, :at, :at, 2, true, true, 'fixture')
                RETURNING snapshot_id
                """
            ),
            {"at": observed_at, "fetch": fetch_id, "metadata": metadata_id},
        )
        request_id = uuid.uuid4()
        connection.execute(text("""
            INSERT INTO recommendation_requests
              (id, requested_at, origin, horizon_minutes, radius_m, application_mode, policy_version)
            VALUES (:id, :at, 'fixture', 15, 750, 'fixture_demo', 'archive-test')
        """), {"id": request_id, "at": observed_at})
        connection.execute(text("""
            INSERT INTO recommendation_results
              (request_id, policy_id, rank, station_id, snapshot_id, snapshot_retrieved_at)
            VALUES (:id, 'archive-test', 1, 'archive-test', :snapshot_id, :at)
        """), {"id": request_id, "snapshot_id": snapshot_id, "at": observed_at})

    result = archive_history(
        database_engine,
        output_root=tmp_path,
        snapshot_cutoff=datetime(2026, 9, 8, tzinfo=UTC),
        raw_cutoff=datetime(2026, 9, 8, tzinfo=UTC),
        delete_after_verify=True,
    )
    archived = next(item for item in result["snapshot_days"] if item["rows"] >= 1)
    parquet_path = Path(archived["path"])
    assert pq.read_metadata(parquet_path).num_rows == archived["rows"]
    assert len(archived["sha256"]) == 64
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM station_snapshots")) == 0
        # Recommendation evidence retains the original ID/time after the detailed
        # snapshot moves into verified Parquet, instead of preventing retention.
        assert connection.scalar(text(
            'SELECT snapshot_id FROM recommendation_results WHERE request_id=:id'
        ), {"id": request_id}) == snapshot_id
        raw_row = connection.execute(
            text("SELECT body, archive_uri FROM raw_payload_blobs WHERE sha256=:sha"),
            {"sha": digest},
        ).one()
    assert raw_row[0] is None
    assert raw_row[1].endswith(f"{digest}.json.gz")
