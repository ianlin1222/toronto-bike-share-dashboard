from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CurrentStation:
    station_id: str
    lifecycle_state: str
    name: str | None
    lat: float
    lon: float
    capacity: int | None
    num_docks_available: int | None
    num_bikes_available: int | None
    num_docks_disabled: int | None
    num_bikes_disabled: int | None
    is_installed: bool | None
    is_renting: bool | None
    is_returning: bool | None
    source_last_reported: datetime | None
    retrieved_at: datetime
    ingested_at: datetime
    feed_last_updated: datetime | None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    metadata_version_id: int | None = None
    snapshot_id: int | None = None
    vehicle_docks_available: tuple[dict[str, Any], ...] = field(default_factory=tuple)
