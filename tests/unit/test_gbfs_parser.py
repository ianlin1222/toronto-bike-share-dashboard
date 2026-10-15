from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bikeshare.gbfs.parser import (
    FeedValidationError,
    normalize_station_information,
    normalize_station_status,
    normalize_vehicle_types,
    parse_timestamp,
    resolve_discovery_feeds,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text())


def test_v3_discovery_and_normalization_preserve_strings_and_nulls() -> None:
    feeds = resolve_discovery_feeds(load("gbfs_v3_discovery.json"))
    assert set(feeds) == {"station_information", "station_status", "vehicle_types"}

    metadata, metadata_quarantine = normalize_station_information(
        load("gbfs_v3_station_information.json")
    )
    bicycle_ids = normalize_vehicle_types(load("gbfs_v3_vehicle_types.json"))
    statuses, status_quarantine = normalize_station_status(
        load("gbfs_v3_station_status.json"),
        retrieved_at=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
        bicycle_vehicle_type_ids=bicycle_ids,
    )

    assert [item.station_id for item in metadata] == ["7000", "7001"]
    assert metadata[0].name == "City Hall"
    assert metadata[0].capacity == 20
    assert metadata_quarantine[0].validation_codes == ("invalid_latitude",)
    assert bicycle_ids == {"ICONIC", "BOOST"}
    assert [item.station_id for item in statuses] == ["7000", "7001"]
    assert statuses[0].num_bikes_available == 15
    assert statuses[0].num_docks_available == 4
    assert statuses[0].num_bikes_disabled is None
    assert "disabled_vehicle_count_not_bicycle_specific" in statuses[0].warnings
    assert status_quarantine[0].validation_codes == ("invalid_num_docks_available",)


def test_v23_discovery_and_epoch_timestamp() -> None:
    feeds = resolve_discovery_feeds(load("gbfs_v23_discovery.json"))
    assert feeds["station_status"].endswith("station_status.json")
    assert parse_timestamp(0) == datetime(1970, 1, 1, tzinfo=UTC)


def test_numeric_station_id_is_string_and_missing_count_stays_null() -> None:
    payload = {
        "data": {
            "stations": [
                {
                    "station_id": 7000,
                    "lat": 43.65,
                    "lon": -79.38,
                    "capacity": None,
                }
            ]
        }
    }
    records, quarantine = normalize_station_information(payload)
    assert not quarantine
    assert records[0].station_id == "7000"
    assert records[0].capacity is None


def test_bad_envelope_rejects_entire_feed() -> None:
    with pytest.raises(FeedValidationError, match="stations"):
        normalize_station_information({"data": {"stations": "not-an-array"}})


def test_future_station_timestamp_is_quarantined() -> None:
    retrieved = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    payload = {
        "data": {
            "stations": [
                {
                    "station_id": "future",
                    "num_docks_available": 1,
                    "last_reported": "2026-09-07T12:00:31Z",
                }
            ]
        }
    }
    accepted, quarantine = normalize_station_status(payload, retrieved_at=retrieved)
    assert not accepted
    assert "future_last_reported" in quarantine[0].validation_codes
