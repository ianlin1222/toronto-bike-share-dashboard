from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from bikeshare.gbfs.models import NormalizedMetadata, NormalizedStatus, QuarantinedRecord

PARSER_VERSION = "gbfs-normalizer-v1"


class FeedValidationError(ValueError):
    """The feed envelope cannot be safely normalized."""


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a timestamp")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            raise ValueError("timestamp has no offset")
        return parsed.astimezone(UTC)
    raise ValueError("unsupported timestamp type")


def feed_last_updated(payload: dict[str, Any]) -> datetime | None:
    try:
        return parse_timestamp(payload.get("last_updated"))
    except (ValueError, OverflowError, OSError):
        return None


def feed_ttl(payload: dict[str, Any]) -> int | None:
    value = payload.get("ttl")
    if isinstance(value, bool) or value is None:
        return None
    try:
        ttl = int(value)
    except (TypeError, ValueError):
        return None
    return ttl if ttl >= 0 else None


def resolve_discovery_feeds(payload: dict[str, Any]) -> dict[str, str]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeedValidationError("discovery is missing object field data")
    feed_list = data.get("feeds")
    if feed_list is None:
        for language_data in data.values():
            if isinstance(language_data, dict) and isinstance(language_data.get("feeds"), list):
                feed_list = language_data["feeds"]
                break
    if not isinstance(feed_list, list):
        raise FeedValidationError("discovery data is missing feeds array")
    feeds: dict[str, str] = {}
    for item in feed_list:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("url")
        if isinstance(name, str) and isinstance(url, str) and name and url.startswith("https://"):
            feeds[name] = url
    required = {"station_information", "station_status"}
    missing = required.difference(feeds)
    if missing:
        raise FeedValidationError(f"discovery is missing required feeds: {sorted(missing)}")
    return feeds


def normalize_vehicle_types(payload: dict[str, Any]) -> set[str]:
    records = _station_array(payload, "vehicle_types")
    bicycle_ids: set[str] = set()
    for record in records:
        vehicle_type_id = record.get("vehicle_type_id")
        form_factor = record.get("form_factor")
        if isinstance(vehicle_type_id, str) and form_factor in {"bicycle", "bike"}:
            bicycle_ids.add(vehicle_type_id)
    return bicycle_ids


def normalize_station_information(
    payload: dict[str, Any],
) -> tuple[list[NormalizedMetadata], list[QuarantinedRecord]]:
    records = _station_array(payload, "stations")
    accepted: list[NormalizedMetadata] = []
    quarantined: list[QuarantinedRecord] = []
    for raw in records:
        station_id = _station_id(raw)
        errors: list[str] = []
        if station_id is None:
            errors.append("missing_station_id")
        lat = _finite_float(raw.get("lat"))
        lon = _finite_float(raw.get("lon"))
        if lat is None or not -90 <= lat <= 90:
            errors.append("invalid_latitude")
        if lon is None or not -180 <= lon <= 180:
            errors.append("invalid_longitude")
        capacity, capacity_error = _optional_nonnegative_int(raw.get("capacity"))
        if capacity_error:
            errors.append("invalid_capacity")
        if errors:
            quarantined.append(QuarantinedRecord(station_id, raw, tuple(errors)))
            continue

        warnings: list[str] = []
        if capacity in (None, 0):
            warnings.append("unknown_or_zero_capacity")
        recognized = {
            "station_id",
            "name",
            "short_name",
            "address",
            "lat",
            "lon",
            "capacity",
            "is_virtual_station",
            "is_valet_station",
            "is_charging_station",
            "vehicle_capacity",
            "vehicle_type_capacity",
            "vehicle_docks_capacity",
            "rental_uris",
            "region_id",
        }
        assert station_id is not None and lat is not None and lon is not None
        accepted.append(
            NormalizedMetadata(
                station_id=station_id,
                name=_localized_text(raw.get("name")),
                short_name=_text_or_none(raw.get("short_name")),
                address=_localized_text(raw.get("address")),
                lat=lat,
                lon=lon,
                capacity=capacity,
                is_virtual_station=_optional_bool(raw.get("is_virtual_station")),
                is_valet_station=_optional_bool(raw.get("is_valet_station")),
                is_charging_station=_optional_bool(raw.get("is_charging_station")),
                capacity_details={
                    key: raw[key]
                    for key in ("vehicle_capacity", "vehicle_type_capacity", "vehicle_docks_capacity")
                    if key in raw
                },
                compatibility={"rental_uris": raw.get("rental_uris")},
                extra_fields={key: value for key, value in raw.items() if key not in recognized},
                warnings=tuple(warnings),
            )
        )
    return accepted, quarantined


def normalize_station_status(
    payload: dict[str, Any],
    *,
    retrieved_at: datetime,
    bicycle_vehicle_type_ids: set[str] | None = None,
) -> tuple[list[NormalizedStatus], list[QuarantinedRecord]]:
    records = _station_array(payload, "stations")
    accepted: list[NormalizedStatus] = []
    quarantined: list[QuarantinedRecord] = []
    for raw in records:
        station_id = _station_id(raw)
        errors: list[str] = []
        if station_id is None:
            errors.append("missing_station_id")

        parsed_counts: dict[str, int | None] = {}
        for field_name in (
            "num_docks_available",
            "num_docks_disabled",
            "num_bikes_available",
            "num_bikes_disabled",
            "num_vehicles_available",
            "num_vehicles_disabled",
        ):
            parsed, invalid = _optional_nonnegative_int(raw.get(field_name))
            parsed_counts[field_name] = parsed
            if invalid:
                errors.append(f"invalid_{field_name}")

        try:
            last_reported = parse_timestamp(raw.get("last_reported"))
        except (ValueError, OverflowError, OSError):
            last_reported = None
            errors.append("invalid_last_reported")
        if last_reported and last_reported > retrieved_at + timedelta(seconds=30):
            errors.append("future_last_reported")

        if errors:
            quarantined.append(QuarantinedRecord(station_id, raw, tuple(errors)))
            continue

        vehicle_types = _dict_tuple(raw.get("vehicle_types_available"))
        vehicle_docks = _dict_tuple(raw.get("vehicle_docks_available"))
        warnings: list[str] = []
        bikes_available = parsed_counts["num_bikes_available"]
        if bikes_available is None and vehicle_types and bicycle_vehicle_type_ids:
            total = 0
            known_count = False
            for item in vehicle_types:
                if item.get("vehicle_type_id") in bicycle_vehicle_type_ids:
                    count, invalid = _optional_nonnegative_int(item.get("count"))
                    if not invalid and count is not None:
                        total += count
                        known_count = True
            bikes_available = total if known_count else None
        elif bikes_available is None:
            warnings.append("bicycle_count_unavailable")

        bikes_disabled = parsed_counts["num_bikes_disabled"]
        if bikes_disabled is None and parsed_counts["num_vehicles_disabled"] is not None:
            warnings.append("disabled_vehicle_count_not_bicycle_specific")

        if last_reported is None:
            warnings.append("missing_last_reported")
        assert station_id is not None
        accepted.append(
            NormalizedStatus(
                station_id=station_id,
                source_last_reported=last_reported,
                num_docks_available=parsed_counts["num_docks_available"],
                num_docks_disabled=parsed_counts["num_docks_disabled"],
                num_bikes_available=bikes_available,
                num_bikes_disabled=bikes_disabled,
                is_installed=_optional_bool(raw.get("is_installed")),
                is_renting=_optional_bool(raw.get("is_renting")),
                is_returning=_optional_bool(raw.get("is_returning")),
                vehicle_types_available=vehicle_types,
                vehicle_docks_available=vehicle_docks,
                warnings=tuple(warnings),
            )
        )
    return accepted, quarantined


def metadata_hash(record: NormalizedMetadata) -> str:
    payload = {
        "station_id": record.station_id,
        "name": record.name,
        "short_name": record.short_name,
        "address": record.address,
        "lat": record.lat,
        "lon": record.lon,
        "capacity": record.capacity,
        "is_virtual_station": record.is_virtual_station,
        "is_valet_station": record.is_valet_station,
        "is_charging_station": record.is_charging_station,
        "capacity_details": record.capacity_details,
        "compatibility": record.compatibility,
        "extra_fields": record.extra_fields,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _station_array(payload: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FeedValidationError("feed is missing object field data")
    records = data.get(field_name)
    if not isinstance(records, list):
        raise FeedValidationError(f"feed is missing array data.{field_name}")
    if not all(isinstance(record, dict) for record in records):
        raise FeedValidationError(f"data.{field_name} contains non-object records")
    return records


def _station_id(raw: dict[str, Any]) -> str | None:
    value = raw.get("station_id")
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        normalized = str(value).strip()
        return normalized or None
    return None


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _optional_nonnegative_int(value: Any) -> tuple[int | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, bool):
        return None, True
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, True
    if parsed < 0 or (isinstance(value, float) and not value.is_integer()):
        return None, True
    return parsed, False


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return None


def _localized_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        choices = [item for item in value if isinstance(item, dict) and isinstance(item.get("text"), str)]
        english = next((item for item in choices if item.get("language") == "en"), None)
        selected = english or (choices[0] if choices else None)
        return selected["text"].strip() or None if selected else None
    return None


def _text_or_none(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))
