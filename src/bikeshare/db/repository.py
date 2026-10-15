from __future__ import annotations

import gzip
import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Connection, Engine, text

from bikeshare import __version__
from bikeshare.db.types import CurrentStation
from bikeshare.gbfs.models import (
    FetchedFeed,
    NormalizedMetadata,
    NormalizedStatus,
    QuarantinedRecord,
)
from bikeshare.gbfs.parser import PARSER_VERSION, metadata_hash
from bikeshare.ranking.policy import RankedCandidate

SOURCE_NAMESPACE = uuid.UUID("2ba99486-101f-4815-8a9a-8b6e4430c522")


class IngestionRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def source_id(discovery_url: str, source_kind: str) -> uuid.UUID:
        return uuid.uuid5(SOURCE_NAMESPACE, f"{source_kind}:{discovery_url}")

    @staticmethod
    def batch_id(source_id: uuid.UUID, scheduled_at: datetime) -> uuid.UUID:
        normalized = scheduled_at.astimezone(UTC).isoformat(timespec="seconds")
        return uuid.uuid5(source_id, normalized)

    def existing_batch_status(self, batch_id: uuid.UUID) -> str | None:
        with self.engine.connect() as connection:
            return cast(
                str | None,
                connection.scalar(
                text("SELECT status FROM poll_batches WHERE id = :batch_id"),
                {"batch_id": batch_id},
                ),
            )

    def persist_ingestion(
        self,
        *,
        discovery_url: str,
        source_kind: str,
        gbfs_version: str | None,
        scheduled_at: datetime,
        started_at: datetime,
        ingested_at: datetime,
        fetches: Sequence[FetchedFeed],
        metadata_records: Sequence[NormalizedMetadata],
        status_records: Sequence[NormalizedStatus],
        quarantined_by_feed: Sequence[tuple[str, QuarantinedRecord]],
        min_coverage: float,
        metadata_polled: bool,
    ) -> dict[str, Any]:
        source_id = self.source_id(discovery_url, source_kind)
        batch_id = self.batch_id(source_id, scheduled_at)
        with self.engine.begin() as connection:
            self._upsert_source(
                connection,
                source_id=source_id,
                discovery_url=discovery_url,
                source_kind=source_kind,
                gbfs_version=gbfs_version,
            )
            existing = connection.scalar(
                text("SELECT status FROM poll_batches WHERE id = :batch_id FOR UPDATE"),
                {"batch_id": batch_id},
            )
            if existing in {"success", "partial"}:
                return {"batch_id": str(batch_id), "status": existing, "duplicate": True}

            connection.execute(
                text(
                    """
                    INSERT INTO poll_batches (
                        id, source_id, scheduled_at, started_at, status, collector_version
                    ) VALUES (
                        :id, :source_id, :scheduled_at, :started_at, 'running', :collector_version
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        started_at = EXCLUDED.started_at,
                        ended_at = NULL,
                        status = 'running',
                        warning_summary = '{}'::jsonb,
                        error_summary = '{}'::jsonb
                    """
                ),
                {
                    "id": batch_id,
                    "source_id": source_id,
                    "scheduled_at": scheduled_at,
                    "started_at": started_at,
                    "collector_version": __version__,
                },
            )
            fetch_ids: dict[str, int] = {}
            for fetched in fetches:
                fetch_ids[fetched.name] = self._persist_fetch(connection, batch_id, fetched, ingested_at)

            if metadata_records:
                metadata_fetch_id = fetch_ids["station_information"]
                self._persist_metadata(
                    connection,
                    records=metadata_records,
                    known_at=ingested_at,
                    fetch_id=metadata_fetch_id,
                )
            if metadata_polled:
                self._update_absent_metadata_stations(
                    connection,
                    station_ids=[record.station_id for record in metadata_records],
                    known_at=ingested_at,
                )

            status_fetch = next(item for item in fetches if item.name == "station_status")
            status_fetch_id = fetch_ids["station_status"]
            for record in status_records:
                self._persist_status(
                    connection,
                    record=record,
                    fetched=status_fetch,
                    fetch_id=status_fetch_id,
                    ingested_at=ingested_at,
                    provenance_kind=source_kind,
                )

            for feed_name, quarantine_record in quarantined_by_feed:
                self._persist_quarantine(
                    connection,
                    batch_id=batch_id,
                    fetch_id=fetch_ids.get(feed_name),
                    record=quarantine_record,
                    schema_version=gbfs_version,
                )

            expected = connection.scalar(
                text("SELECT count(*) FROM station_metadata_versions WHERE known_to_at IS NULL")
            )
            expected_count = int(expected or 0)
            received_count = len(status_records) + sum(
                1 for feed_name, _ in quarantined_by_feed if feed_name == "station_status"
            )
            accepted_count = len(status_records)
            quarantined_count = len(quarantined_by_feed)
            coverage = accepted_count / expected_count if expected_count else 0.0
            batch_status = "success" if expected_count and coverage >= min_coverage else "partial"
            ended_at = datetime.now(tz=UTC)
            warnings = {
                "coverage": coverage,
                "metadata_polled": metadata_polled,
                "quarantined_records": quarantined_count,
            }
            connection.execute(
                text(
                    """
                    UPDATE poll_batches SET
                        ended_at = :ended_at,
                        status = :status,
                        expected_records = :expected,
                        received_records = :received,
                        accepted_records = :accepted,
                        quarantined_records = :quarantined,
                        latency_ms = :latency_ms,
                        warning_summary = CAST(:warnings AS jsonb)
                    WHERE id = :batch_id
                    """
                ),
                {
                    "ended_at": ended_at,
                    "status": batch_status,
                    "expected": expected_count,
                    "received": received_count,
                    "accepted": accepted_count,
                    "quarantined": quarantined_count,
                    "latency_ms": max(int((ended_at - started_at).total_seconds() * 1000), 0),
                    "warnings": json.dumps(warnings),
                    "batch_id": batch_id,
                },
            )
            return {
                "batch_id": str(batch_id),
                "status": batch_status,
                "duplicate": False,
                "expected_records": expected_count,
                "received_records": received_count,
                "accepted_records": accepted_count,
                "quarantined_records": quarantined_count,
                "coverage": coverage,
            }

    def persist_failed_batch(
        self,
        *,
        discovery_url: str,
        source_kind: str,
        scheduled_at: datetime,
        started_at: datetime,
        error_code: str,
        error_detail: str,
        fetches: Sequence[FetchedFeed] = (),
    ) -> uuid.UUID:
        source_id = self.source_id(discovery_url, source_kind)
        batch_id = self.batch_id(source_id, scheduled_at)
        ended_at = datetime.now(tz=UTC)
        with self.engine.begin() as connection:
            self._upsert_source(
                connection,
                source_id=source_id,
                discovery_url=discovery_url,
                source_kind=source_kind,
                gbfs_version=None,
            )
            connection.execute(
                text(
                    """
                    INSERT INTO poll_batches (
                        id, source_id, scheduled_at, started_at, ended_at, status,
                        latency_ms, error_summary, collector_version
                    ) VALUES (
                        :id, :source_id, :scheduled_at, :started_at, :ended_at, 'failed',
                        :latency_ms, CAST(:error AS jsonb), :collector_version
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        ended_at = EXCLUDED.ended_at,
                        status = 'failed',
                        latency_ms = EXCLUDED.latency_ms,
                        error_summary = EXCLUDED.error_summary
                    """
                ),
                {
                    "id": batch_id,
                    "source_id": source_id,
                    "scheduled_at": scheduled_at,
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "latency_ms": max(int((ended_at - started_at).total_seconds() * 1000), 0),
                    "error": json.dumps({"code": error_code, "detail": error_detail[:2000]}),
                    "collector_version": __version__,
                },
            )
            for fetched in fetches:
                self._persist_fetch(connection, batch_id, fetched, ended_at)
            connection.execute(
                text(
                    """
                    INSERT INTO ingestion_events (batch_id, severity, event_code, detail)
                    VALUES (:batch_id, 'error', :event_code, CAST(:detail AS jsonb))
                    """
                ),
                {
                    "batch_id": batch_id,
                    "event_code": error_code,
                    "detail": json.dumps({"error": error_detail[:2000]}),
                },
            )
        return batch_id

    def record_event(
        self,
        *,
        event_code: str,
        severity: str = "info",
        detail: dict[str, Any] | None = None,
        batch_id: uuid.UUID | None = None,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ingestion_events (batch_id, severity, event_code, detail)
                    VALUES (:batch_id, :severity, :event_code, CAST(:detail AS jsonb))
                    """
                ),
                {
                    "batch_id": batch_id,
                    "severity": severity,
                    "event_code": event_code,
                    "detail": json.dumps(detail or {}),
                },
            )

    def get_current_station(
        self, station_id: str, *, decision_time: datetime | None = None
    ) -> CurrentStation | None:
        stations = self._current_station_query(
            station_id=station_id,
            decision_time=decision_time or datetime.now(tz=UTC),
        )
        return stations[0] if stations else None

    def get_current_stations(self, *, decision_time: datetime | None = None) -> list[CurrentStation]:
        return self._current_station_query(
            station_id=None,
            decision_time=decision_time or datetime.now(tz=UTC),
        )

    def readiness(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT latest.scheduled_at, latest.ended_at, latest.status,
                           latest.expected_records, latest.accepted_records,
                           latest.warning_summary,
                           (
                             SELECT max(complete.ended_at) FROM poll_batches complete
                             JOIN source_datasets source ON source.id = complete.source_id
                             WHERE complete.status = 'success' AND source.source_kind = 'live'
                           ) AS latest_complete_at
                    FROM poll_batches latest
                    JOIN source_datasets source ON source.id = latest.source_id
                    WHERE latest.status IN ('success','partial') AND source.source_kind = 'live'
                    ORDER BY latest.scheduled_at DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()
        return dict(row) if row else {}

    def data_audit(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            return dict(
                connection.execute(
                    text(
                        """
                        SELECT
                          (SELECT count(*) FROM poll_batches) AS poll_batches,
                          (SELECT count(*) FROM poll_batches WHERE status='success') AS successful_batches,
                          (SELECT count(*) FROM poll_batches WHERE status='partial') AS partial_batches,
                          (SELECT count(*) FROM poll_batches WHERE status='failed') AS failed_batches,
                          (SELECT count(*) FROM station_snapshots) AS snapshots,
                          (SELECT count(*) FROM quarantine_records) AS quarantined_records,
                          (SELECT min(retrieved_at) FROM station_snapshots) AS first_snapshot_at,
                          (SELECT max(retrieved_at) FROM station_snapshots) AS latest_snapshot_at,
                          (
                            SELECT pg_size_pretty(sum(pg_total_relation_size(relid)))
                            FROM pg_partition_tree('station_snapshots')
                          ) AS snapshot_table_size
                        """
                    )
                ).mappings().one()
            )

    def persist_recommendation(
        self,
        *,
        request_id: uuid.UUID,
        requested_at: datetime,
        destination_lat: float,
        destination_lon: float,
        destination_decimals: int,
        horizon_minutes: int,
        radius_m: int,
        mode: str,
        policy_version: str,
        feature_version: str,
        fallback_reason: str | None,
        ranked: Sequence[RankedCandidate],
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO recommendation_requests (
                        id, requested_at, origin, destination_lat_rounded,
                        destination_lon_rounded, horizon_minutes, radius_m,
                        application_mode, feature_version, policy_version
                    ) VALUES (
                        :id, :requested_at, 'api', :lat, :lon, :horizon, :radius,
                        :mode, :feature_version, :policy_version
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": request_id,
                    "requested_at": requested_at,
                    "lat": round(destination_lat, destination_decimals),
                    "lon": round(destination_lon, destination_decimals),
                    "horizon": horizon_minutes,
                    "radius": radius_m,
                    "mode": mode,
                    "feature_version": feature_version,
                    "policy_version": policy_version,
                },
            )
            for item in ranked:
                station = item.candidate.station
                connection.execute(
                    text(
                        """
                        INSERT INTO recommendation_results (
                            request_id, policy_id, rank, station_id, distance_m,
                            current_docks, forecast_probability, ranking_score,
                            snapshot_id, snapshot_retrieved_at, feature_version,
                            fallback_reason
                        ) VALUES (
                            :request_id, :policy_id, :rank, :station_id, :distance_m,
                            :current_docks, :probability, :score, :snapshot_id,
                            :snapshot_retrieved_at, :feature_version, :fallback_reason
                        )
                        ON CONFLICT (request_id, policy_id, rank) DO NOTHING
                        """
                    ),
                    {
                        "request_id": request_id,
                        "policy_id": policy_version,
                        "rank": item.rank,
                        "station_id": station.station_id,
                        "distance_m": item.candidate.distance_m,
                        "current_docks": station.num_docks_available,
                        "probability": item.probability,
                        "score": item.score,
                        "snapshot_id": station.snapshot_id,
                        "snapshot_retrieved_at": (
                            station.retrieved_at if station.snapshot_id is not None else None
                        ),
                        "feature_version": feature_version,
                        "fallback_reason": fallback_reason,
                    },
                )

    def _current_station_query(
        self, *, station_id: str | None, decision_time: datetime
    ) -> list[CurrentStation]:
        station_filter = "WHERE station.station_id = :station_id" if station_id is not None else ""
        statement = text(
            f"""
            SELECT latest.*, metadata.id AS metadata_version_id,
                   metadata.name, metadata.lat, metadata.lon, metadata.capacity,
                   station.lifecycle_state
            FROM stations station
            JOIN LATERAL (
                SELECT ss.snapshot_id, ss.retrieved_at, ss.station_id,
                    ss.ingested_at, ss.feed_last_updated, ss.source_last_reported,
                    ss.num_docks_available, ss.num_docks_disabled,
                    ss.num_bikes_available, ss.num_bikes_disabled,
                    ss.is_installed, ss.is_renting, ss.is_returning,
                    ss.vehicle_docks_available, ss.quality_flags
                FROM station_snapshots ss
                WHERE ss.is_canonical
                  AND ss.station_id = station.station_id
                  AND ss.ingested_at <= :decision_time
                  AND ss.retrieved_at <= :decision_time
                ORDER BY ss.retrieved_at DESC, ss.snapshot_id DESC LIMIT 1
            ) latest ON true
            JOIN LATERAL (
                SELECT * FROM station_metadata_versions smv
                WHERE smv.station_id = station.station_id
                  AND smv.known_from_at <= :decision_time
                  AND (smv.known_to_at IS NULL OR smv.known_to_at > :decision_time)
                ORDER BY smv.known_from_at DESC LIMIT 1
            ) metadata ON true
            {station_filter}
            ORDER BY latest.station_id
            """
        )
        parameters: dict[str, Any] = {"decision_time": decision_time}
        if station_id is not None:
            parameters["station_id"] = station_id
        with self.engine.connect() as connection:
            rows = connection.execute(statement, parameters).mappings()
            return [self._row_to_current_station(dict(row)) for row in rows]

    @staticmethod
    def _row_to_current_station(row: dict[str, Any]) -> CurrentStation:
        return CurrentStation(
            station_id=row["station_id"],
            lifecycle_state=row["lifecycle_state"],
            name=row["name"],
            lat=row["lat"],
            lon=row["lon"],
            capacity=row["capacity"],
            num_docks_available=row["num_docks_available"],
            num_bikes_available=row["num_bikes_available"],
            num_docks_disabled=row["num_docks_disabled"],
            num_bikes_disabled=row["num_bikes_disabled"],
            is_installed=row["is_installed"],
            is_renting=row["is_renting"],
            is_returning=row["is_returning"],
            source_last_reported=row["source_last_reported"],
            retrieved_at=row["retrieved_at"],
            ingested_at=row["ingested_at"],
            feed_last_updated=row["feed_last_updated"],
            quality_flags=tuple(row["quality_flags"] or ()),
            metadata_version_id=row["metadata_version_id"],
            snapshot_id=row["snapshot_id"],
            vehicle_docks_available=tuple(row["vehicle_docks_available"] or ()),
        )

    @staticmethod
    def _upsert_source(
        connection: Connection,
        *,
        source_id: uuid.UUID,
        discovery_url: str,
        source_kind: str,
        gbfs_version: str | None,
    ) -> None:
        connection.execute(
            text(
                """
                INSERT INTO source_datasets (
                    id, source_kind, system_id, discovery_url, gbfs_version,
                    licence_name, licence_url, attribution, accessed_on, importer_version
                ) VALUES (
                    :id, :source_kind, 'bike_share_toronto', :url, :version,
                    'Open Government Licence - Toronto',
                    'https://www.toronto.ca/city-government/data-research-maps/open-data/open-data-licence/',
                    'Contains information licensed under the Open Government Licence - Toronto.',
                    CURRENT_DATE, :importer_version
                )
                ON CONFLICT (id) DO UPDATE SET
                    gbfs_version = COALESCE(EXCLUDED.gbfs_version, source_datasets.gbfs_version),
                    importer_version = EXCLUDED.importer_version
                """
            ),
            {
                "id": source_id,
                "source_kind": source_kind,
                "url": discovery_url,
                "version": gbfs_version,
                "importer_version": __version__,
            },
        )

    @staticmethod
    def _persist_fetch(
        connection: Connection,
        batch_id: uuid.UUID,
        fetched: FetchedFeed,
        ingested_at: datetime,
    ) -> int:
        sha256 = hashlib.sha256(fetched.body).hexdigest()
        compressed = gzip.compress(fetched.body, mtime=0)
        connection.execute(
            text(
                """
                INSERT INTO raw_payload_blobs (
                    sha256, content_type, compression, uncompressed_bytes, stored_bytes, body
                ) VALUES (:sha256, 'application/json', 'gzip', :raw_size, :stored_size, :body)
                ON CONFLICT (sha256) DO NOTHING
                """
            ),
            {
                "sha256": sha256,
                "raw_size": len(fetched.body),
                "stored_size": len(compressed),
                "body": compressed,
            },
        )
        row = connection.execute(
            text(
                """
                INSERT INTO feed_fetches (
                    batch_id, feed_name, url, attempt, http_status, retrieved_at, ingested_at,
                    feed_last_updated, ttl_seconds, cache_headers, raw_sha256, validation_state
                ) VALUES (
                    :batch_id, :feed_name, :url, :attempt, :http_status, :retrieved_at, :ingested_at,
                    :feed_last_updated, :ttl_seconds, CAST(:cache_headers AS jsonb), :raw_sha256, 'valid'
                )
                ON CONFLICT (batch_id, feed_name, attempt) DO UPDATE SET
                    raw_sha256 = EXCLUDED.raw_sha256
                RETURNING id
                """
            ),
            {
                "batch_id": batch_id,
                "feed_name": fetched.name,
                "url": fetched.url,
                "attempt": fetched.attempt,
                "http_status": fetched.status_code,
                "retrieved_at": fetched.retrieved_at,
                "ingested_at": ingested_at,
                "feed_last_updated": fetched.feed_last_updated,
                "ttl_seconds": fetched.ttl_seconds,
                "cache_headers": json.dumps(fetched.cache_headers),
                "raw_sha256": sha256,
            },
        ).one()
        return int(row[0])

    @staticmethod
    def _persist_metadata(
        connection: Connection,
        *,
        records: Sequence[NormalizedMetadata],
        known_at: datetime,
        fetch_id: int,
    ) -> None:
        for record in records:
            connection.execute(
                text(
                    """
                    INSERT INTO stations (station_id, first_seen_at, last_seen_at)
                    VALUES (:station_id, :seen_at, :seen_at)
                    ON CONFLICT (station_id) DO UPDATE SET
                        last_seen_at = GREATEST(stations.last_seen_at, EXCLUDED.last_seen_at),
                        lifecycle_state = 'active', absent_metadata_polls = 0, retired_at = NULL
                    """
                ),
                {"station_id": record.station_id, "seen_at": known_at},
            )
            record_hash = metadata_hash(record)
            current = connection.execute(
                text(
                    """
                    SELECT id, metadata_hash FROM station_metadata_versions
                    WHERE station_id = :station_id AND known_to_at IS NULL
                    FOR UPDATE
                    """
                ),
                {"station_id": record.station_id},
            ).mappings().first()
            if current and current["metadata_hash"] == record_hash:
                continue
            if current:
                connection.execute(
                    text("UPDATE station_metadata_versions SET known_to_at=:known_at WHERE id=:id"),
                    {"known_at": known_at, "id": current["id"]},
                )
            connection.execute(
                text(
                    """
                    INSERT INTO station_metadata_versions (
                        station_id, metadata_hash, name, short_name, address, lat, lon, capacity,
                        is_virtual_station, is_valet_station, is_charging_station,
                        capacity_details, compatibility, extra_fields, known_from_at, source_fetch_id
                    ) VALUES (
                        :station_id, :metadata_hash, :name, :short_name, :address, :lat, :lon, :capacity,
                        :is_virtual, :is_valet, :is_charging,
                        CAST(:capacity_details AS jsonb), CAST(:compatibility AS jsonb),
                        CAST(:extra_fields AS jsonb), :known_at, :fetch_id
                    )
                    """
                ),
                {
                    "station_id": record.station_id,
                    "metadata_hash": record_hash,
                    "name": record.name,
                    "short_name": record.short_name,
                    "address": record.address,
                    "lat": record.lat,
                    "lon": record.lon,
                    "capacity": record.capacity,
                    "is_virtual": record.is_virtual_station,
                    "is_valet": record.is_valet_station,
                    "is_charging": record.is_charging_station,
                    "capacity_details": json.dumps(record.capacity_details),
                    "compatibility": json.dumps(record.compatibility),
                    "extra_fields": json.dumps(record.extra_fields),
                    "known_at": known_at,
                    "fetch_id": fetch_id,
                },
            )

    @staticmethod
    def _update_absent_metadata_stations(
        connection: Connection, *, station_ids: Sequence[str], known_at: datetime
    ) -> None:
        connection.execute(
            text(
                """
                UPDATE stations
                SET absent_metadata_polls = absent_metadata_polls + 1,
                    lifecycle_state = CASE WHEN absent_metadata_polls + 1 >= 3 THEN 'retired' ELSE 'missing' END,
                    retired_at = CASE WHEN absent_metadata_polls + 1 >= 3 THEN :known_at ELSE retired_at END
                WHERE station_id != ALL(CAST(:station_ids AS text[]))
                  AND EXISTS (
                    SELECT 1 FROM station_metadata_versions smv
                    WHERE smv.station_id = stations.station_id AND smv.known_to_at IS NULL
                  )
                """
            ),
            {"station_ids": list(station_ids), "known_at": known_at},
        )

    @staticmethod
    def _persist_status(
        connection: Connection,
        *,
        record: NormalizedStatus,
        fetched: FetchedFeed,
        fetch_id: int,
        ingested_at: datetime,
        provenance_kind: str,
    ) -> None:
        connection.execute(
            text(
                """
                INSERT INTO stations (station_id, first_seen_at, last_seen_at)
                VALUES (:station_id, :seen_at, :seen_at)
                ON CONFLICT (station_id) DO UPDATE SET
                    last_seen_at = GREATEST(stations.last_seen_at, EXCLUDED.last_seen_at)
                """
            ),
            {"station_id": record.station_id, "seen_at": ingested_at},
        )
        metadata_version_id = connection.scalar(
            text(
                """
                SELECT id FROM station_metadata_versions
                WHERE station_id = :station_id
                  AND known_from_at <= :known_at
                  AND (known_to_at IS NULL OR known_to_at > :known_at)
                ORDER BY known_from_at DESC LIMIT 1
                """
            ),
            {"station_id": record.station_id, "known_at": ingested_at},
        )
        prior_reported = connection.scalar(
            text(
                """
                SELECT max(source_last_reported) FROM station_snapshots
                WHERE station_id = :station_id AND is_canonical
                """
            ),
            {"station_id": record.station_id},
        )
        out_of_order = bool(
            prior_reported
            and record.source_last_reported
            and record.source_last_reported < prior_reported
        )
        quality_flags = list(record.warnings)
        if metadata_version_id is None:
            quality_flags.append("missing_metadata")
        if out_of_order:
            quality_flags.append("out_of_order")
        connection.execute(
            text(
                """
                INSERT INTO station_snapshots (
                    retrieved_at, station_id, feed_fetch_id, metadata_version_id, ingested_at,
                    feed_last_updated, source_last_reported, num_docks_available,
                    num_docks_disabled, num_bikes_available, num_bikes_disabled,
                    is_installed, is_renting, is_returning, vehicle_types_available,
                    vehicle_docks_available, quality_flags, provenance_kind, is_canonical
                ) VALUES (
                    :retrieved_at, :station_id, :feed_fetch_id, :metadata_version_id, :ingested_at,
                    :feed_last_updated, :source_last_reported, :num_docks_available,
                    :num_docks_disabled, :num_bikes_available, :num_bikes_disabled,
                    :is_installed, :is_renting, :is_returning,
                    CAST(:vehicle_types AS jsonb), CAST(:vehicle_docks AS jsonb),
                    CAST(:quality_flags AS text[]), :provenance_kind, :is_canonical
                )
                ON CONFLICT (feed_fetch_id, station_id, retrieved_at) DO NOTHING
                """
            ),
            {
                "retrieved_at": fetched.retrieved_at,
                "station_id": record.station_id,
                "feed_fetch_id": fetch_id,
                "metadata_version_id": metadata_version_id,
                "ingested_at": ingested_at,
                "feed_last_updated": fetched.feed_last_updated,
                "source_last_reported": record.source_last_reported,
                "num_docks_available": record.num_docks_available,
                "num_docks_disabled": record.num_docks_disabled,
                "num_bikes_available": record.num_bikes_available,
                "num_bikes_disabled": record.num_bikes_disabled,
                "is_installed": record.is_installed,
                "is_renting": record.is_renting,
                "is_returning": record.is_returning,
                "vehicle_types": json.dumps(record.vehicle_types_available),
                "vehicle_docks": json.dumps(record.vehicle_docks_available),
                "quality_flags": quality_flags,
                "provenance_kind": provenance_kind,
                "is_canonical": not out_of_order,
            },
        )

    @staticmethod
    def _persist_quarantine(
        connection: Connection,
        *,
        batch_id: uuid.UUID,
        fetch_id: int | None,
        record: QuarantinedRecord,
        schema_version: str | None,
    ) -> None:
        connection.execute(
            text(
                """
                INSERT INTO quarantine_records (
                    batch_id, feed_fetch_id, station_id, raw_fragment, validation_codes,
                    parser_version, schema_version
                ) VALUES (
                    :batch_id, :fetch_id, :station_id, CAST(:raw AS jsonb),
                    CAST(:codes AS text[]), :parser_version, :schema_version
                )
                """
            ),
            {
                "batch_id": batch_id,
                "fetch_id": fetch_id,
                "station_id": record.station_id,
                "raw": json.dumps(record.raw_fragment),
                "codes": list(record.validation_codes),
                "parser_version": PARSER_VERSION,
                "schema_version": schema_version,
            },
        )


def station_rows_from_json(rows: Iterable[dict[str, Any]]) -> list[CurrentStation]:
    def timestamp(value: Any) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)

    result: list[CurrentStation] = []
    for row in rows:
        retrieved_at = timestamp(row["retrieved_at"])
        ingested_at = timestamp(row["ingested_at"])
        assert retrieved_at is not None and ingested_at is not None
        result.append(
            CurrentStation(
                station_id=str(row["station_id"]),
                lifecycle_state=str(row.get("lifecycle_state", "active")),
                name=row.get("name"),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                capacity=row.get("capacity"),
                num_docks_available=row.get("num_docks_available"),
                num_bikes_available=row.get("num_bikes_available"),
                num_docks_disabled=row.get("num_docks_disabled"),
                num_bikes_disabled=row.get("num_bikes_disabled"),
                is_installed=row.get("is_installed"),
                is_renting=row.get("is_renting"),
                is_returning=row.get("is_returning"),
                source_last_reported=timestamp(row.get("source_last_reported")),
                retrieved_at=retrieved_at,
                ingested_at=ingested_at,
                feed_last_updated=timestamp(row.get("feed_last_updated")),
                quality_flags=tuple(row.get("quality_flags", ())),
            )
        )
    return result
