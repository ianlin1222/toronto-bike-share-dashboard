from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from bikeshare.db.repository import IngestionRepository
from bikeshare.gbfs.models import FetchedFeed
from bikeshare.gbfs.parser import (
    feed_last_updated,
    feed_ttl,
    normalize_station_information,
    normalize_station_status,
    normalize_vehicle_types,
)

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parents[1] / "fixtures"


def fetched(name: str, filename: str, retrieved_at: datetime) -> FetchedFeed:
    body = (FIXTURES / filename).read_bytes()
    payload = json.loads(body)
    return FetchedFeed(
        name=name,
        url=f"https://example.test/{filename}",
        retrieved_at=retrieved_at,
        status_code=200,
        body=body,
        payload=payload,
        attempt=1,
        feed_last_updated=feed_last_updated(payload),
        ttl_seconds=feed_ttl(payload),
        cache_headers={"cache-control": "max-age=10"},
    )


def test_fixture_ingestion_is_idempotent_and_preserves_quarantine(
    database_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FixtureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            # The fixture is historical; runtime latency must use its clock too.
            return datetime(2026, 9, 7, 12, 2, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr("bikeshare.db.repository.datetime", FixtureClock)
    repository = IngestionRepository(database_engine)
    retrieved = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    discovery = fetched("gbfs", "gbfs_v3_discovery.json", retrieved)
    information = fetched("station_information", "gbfs_v3_station_information.json", retrieved)
    status = fetched("station_status", "gbfs_v3_station_status.json", retrieved)
    vehicle_types = fetched("vehicle_types", "gbfs_v3_vehicle_types.json", retrieved)
    metadata, metadata_quarantine = normalize_station_information(information.payload)
    bicycle_ids = normalize_vehicle_types(vehicle_types.payload)
    statuses, status_quarantine = normalize_station_status(
        status.payload,
        retrieved_at=retrieved,
        bicycle_vehicle_type_ids=bicycle_ids,
    )
    arguments = dict(
        discovery_url="https://example.test/gbfs.json",
        source_kind="fixture",
        gbfs_version="3.0",
        scheduled_at=retrieved,
        started_at=retrieved,
        ingested_at=retrieved,
        fetches=[discovery, information, status, vehicle_types],
        metadata_records=metadata,
        status_records=statuses,
        quarantined_by_feed=[
            *(("station_information", item) for item in metadata_quarantine),
            *(("station_status", item) for item in status_quarantine),
        ],
        min_coverage=0.95,
        metadata_polled=True,
    )
    first = repository.persist_ingestion(**arguments)
    second = repository.persist_ingestion(**arguments)
    assert first["status"] == "success"
    assert first["accepted_records"] == 2
    assert first["quarantined_records"] == 2
    assert second["duplicate"] is True
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM station_snapshots")) == 2
        assert connection.scalar(text("SELECT count(*) FROM raw_payload_blobs")) == 4
        assert connection.scalar(text("SELECT count(*) FROM quarantine_records")) == 2
        assert connection.scalar(text("SELECT count(*) FROM station_metadata_versions")) == 2

    older = replace(
        statuses[0],
        source_last_reported=datetime(2026, 9, 7, 11, 0, tzinfo=UTC),
    )
    partial_payload = {
        "last_updated": "2026-09-07T12:01:00Z",
        "ttl": 5,
        "version": "3.0",
        "data": {
            "stations": [
                {
                    "station_id": "7000",
                    "num_docks_available": older.num_docks_available,
                    "num_docks_disabled": older.num_docks_disabled,
                    "is_installed": older.is_installed,
                    "is_renting": older.is_renting,
                    "is_returning": older.is_returning,
                    "last_reported": older.source_last_reported.isoformat(),
                }
            ]
        },
    }
    partial_body = json.dumps(partial_payload).encode()
    partial_status = FetchedFeed(
        name="station_status",
        url="https://example.test/partial-status.json",
        retrieved_at=datetime(2026, 9, 7, 12, 1, tzinfo=UTC),
        status_code=200,
        body=partial_body,
        payload=partial_payload,
        attempt=1,
        feed_last_updated=datetime(2026, 9, 7, 12, 1, tzinfo=UTC),
        ttl_seconds=5,
        cache_headers={},
    )
    partial = repository.persist_ingestion(
        discovery_url="https://example.test/gbfs.json",
        source_kind="fixture",
        gbfs_version="3.0",
        scheduled_at=datetime(2026, 9, 7, 12, 1, tzinfo=UTC),
        started_at=datetime(2026, 9, 7, 12, 1, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 7, 12, 1, tzinfo=UTC),
        fetches=[
            replace(discovery, retrieved_at=datetime(2026, 9, 7, 12, 1, tzinfo=UTC)),
            partial_status,
        ],
        metadata_records=[],
        status_records=[older],
        quarantined_by_feed=[],
        min_coverage=0.95,
        metadata_polled=False,
    )
    assert partial["status"] == "partial"
    with database_engine.connect() as connection:
        out_of_order = connection.execute(
            text(
                """
                SELECT quality_flags, is_canonical FROM station_snapshots
                WHERE station_id='7000' ORDER BY retrieved_at DESC LIMIT 1
                """
            )
        ).one()
    assert "out_of_order" in out_of_order[0]
    assert out_of_order[1] is False
    current = repository.get_current_station(
        "7000", decision_time=datetime(2026, 9, 7, 13, 0, tzinfo=UTC)
    )
    assert current is not None
    assert current.source_last_reported == datetime(2026, 9, 7, 11, 59, 30, tzinfo=UTC)
