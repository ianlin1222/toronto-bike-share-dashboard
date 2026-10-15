from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class FetchedFeed:
    name: str
    url: str
    retrieved_at: datetime
    status_code: int
    body: bytes
    payload: dict[str, Any]
    attempt: int
    feed_last_updated: datetime | None
    ttl_seconds: int | None
    cache_headers: dict[str, str]


@dataclass(frozen=True, slots=True)
class QuarantinedRecord:
    station_id: str | None
    raw_fragment: dict[str, Any]
    validation_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NormalizedMetadata:
    station_id: str
    name: str | None
    short_name: str | None
    address: str | None
    lat: float
    lon: float
    capacity: int | None
    is_virtual_station: bool | None
    is_valet_station: bool | None
    is_charging_station: bool | None
    capacity_details: dict[str, Any]
    compatibility: dict[str, Any]
    extra_fields: dict[str, Any]
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NormalizedStatus:
    station_id: str
    source_last_reported: datetime | None
    num_docks_available: int | None
    num_docks_disabled: int | None
    num_bikes_available: int | None
    num_bikes_disabled: int | None
    is_installed: bool | None
    is_renting: bool | None
    is_returning: bool | None
    vehicle_types_available: tuple[dict[str, Any], ...]
    vehicle_docks_available: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def utc_now() -> datetime:
    return datetime.now(tz=UTC)
