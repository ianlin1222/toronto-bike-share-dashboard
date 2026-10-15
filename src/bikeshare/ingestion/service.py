from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bikeshare.config import Settings
from bikeshare.db.repository import IngestionRepository
from bikeshare.gbfs.client import FeedFetchError, GBFSClient
from bikeshare.gbfs.models import FetchedFeed, NormalizedMetadata, QuarantinedRecord
from bikeshare.gbfs.parser import (
    FeedValidationError,
    normalize_station_information,
    normalize_station_status,
    normalize_vehicle_types,
    resolve_discovery_feeds,
)

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, settings: Settings, repository: IngestionRepository) -> None:
        self.settings = settings
        self.repository = repository
        self.bicycle_vehicle_type_ids: set[str] = set()

    def ingest_once(
        self,
        *,
        scheduled_at: datetime | None = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        if scheduled_at is None:
            now = datetime.now(tz=UTC)
            epoch = int(now.timestamp())
            scheduled = datetime.fromtimestamp(
                epoch - epoch % self.settings.status_poll_seconds,
                tz=UTC,
            )
        else:
            scheduled = scheduled_at.astimezone(UTC).replace(microsecond=0)
        source_id = self.repository.source_id(self.settings.gbfs_discovery_url, "live")
        batch_id = self.repository.batch_id(source_id, scheduled)
        existing = self.repository.existing_batch_status(batch_id)
        if existing in {"success", "partial"}:
            return {"batch_id": str(batch_id), "status": existing, "duplicate": True}

        started_at = datetime.now(tz=UTC)
        fetches: list[FetchedFeed] = []
        try:
            with GBFSClient(user_agent=self.settings.user_agent) as client:
                discovery = client.fetch("gbfs", self.settings.gbfs_discovery_url)
                fetches.append(discovery)
                feed_urls = resolve_discovery_feeds(discovery.payload)
                if include_metadata:
                    information = client.fetch("station_information", feed_urls["station_information"])
                    fetches.append(information)
                    if "vehicle_types" in feed_urls:
                        vehicle_types = client.fetch("vehicle_types", feed_urls["vehicle_types"])
                        fetches.append(vehicle_types)
                        self.bicycle_vehicle_type_ids = normalize_vehicle_types(vehicle_types.payload)
                status = client.fetch("station_status", feed_urls["station_status"])
                fetches.append(status)

            metadata_records: list[NormalizedMetadata] = []
            quarantined: list[tuple[str, QuarantinedRecord]] = []
            if include_metadata:
                metadata_records, metadata_quarantine = normalize_station_information(information.payload)
                quarantined.extend(("station_information", record) for record in metadata_quarantine)
            status_records, status_quarantine = normalize_station_status(
                status.payload,
                retrieved_at=status.retrieved_at,
                bicycle_vehicle_type_ids=self.bicycle_vehicle_type_ids,
            )
            quarantined.extend(("station_status", record) for record in status_quarantine)
            version = discovery.payload.get("version")
            ingested_at = datetime.now(tz=UTC)
            result = self.repository.persist_ingestion(
                discovery_url=self.settings.gbfs_discovery_url,
                source_kind="live",
                gbfs_version=str(version) if version is not None else None,
                scheduled_at=scheduled,
                started_at=started_at,
                ingested_at=ingested_at,
                fetches=fetches,
                metadata_records=metadata_records,
                status_records=status_records,
                quarantined_by_feed=quarantined,
                min_coverage=self.settings.partial_batch_min_coverage,
                metadata_polled=include_metadata,
            )
            logger.info(
                "GBFS batch persisted",
                extra={"service": "collector", "event_code": "batch_complete", "batch_id": result["batch_id"]},
            )
            return result
        except (FeedFetchError, FeedValidationError, KeyError, ValueError) as error:
            failed_batch_id = self.repository.persist_failed_batch(
                discovery_url=self.settings.gbfs_discovery_url,
                source_kind="live",
                scheduled_at=scheduled,
                started_at=started_at,
                error_code="feed_ingestion_failed",
                error_detail=str(error),
                fetches=fetches,
            )
            logger.exception(
                "GBFS batch failed",
                extra={
                    "service": "collector",
                    "event_code": "batch_failed",
                    "batch_id": str(failed_batch_id),
                },
            )
            raise
