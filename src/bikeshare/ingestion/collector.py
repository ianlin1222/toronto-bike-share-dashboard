from __future__ import annotations

import logging
import signal
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text

from bikeshare.config import Settings
from bikeshare.db.repository import IngestionRepository
from bikeshare.ingestion.service import IngestionService
from bikeshare.ingestion.summaries import refresh_reporting_summaries

logger = logging.getLogger(__name__)
COLLECTOR_LOCK_ID = 187_002_026


class Collector:
    def __init__(self, settings: Settings, repository: IngestionRepository, engine: Engine) -> None:
        self.settings = settings
        self.repository = repository
        self.engine = engine
        self.service = IngestionService(settings, repository)
        self.stopping = threading.Event()

    def run(self) -> None:
        self._install_signal_handlers()
        with self.engine.connect() as lock_connection:
            acquired = bool(
                lock_connection.scalar(
                    text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": COLLECTOR_LOCK_ID}
                )
            )
            if not acquired:
                raise RuntimeError("another collector holds the PostgreSQL advisory lock")
            self.repository.record_event(event_code="collector_started")
            last_metadata_poll: datetime | None = None
            previous_scheduled: datetime | None = None
            try:
                while not self.stopping.is_set():
                    now = datetime.now(tz=UTC)
                    scheduled = self._scheduled_slot(now)
                    if previous_scheduled and scheduled - previous_scheduled > timedelta(
                        seconds=self.settings.status_poll_seconds
                    ):
                        self.repository.record_event(
                            event_code="collection_gap_detected",
                            severity="warning",
                            detail={
                                "previous_scheduled": previous_scheduled.isoformat(),
                                "current_scheduled": scheduled.isoformat(),
                            },
                        )
                    include_metadata = (
                        last_metadata_poll is None
                        or now - last_metadata_poll
                        >= timedelta(seconds=self.settings.metadata_poll_seconds)
                    )
                    try:
                        self.service.ingest_once(
                            scheduled_at=scheduled,
                            include_metadata=include_metadata,
                        )
                        if include_metadata:
                            last_metadata_poll = now
                        refresh_reporting_summaries(self.engine, now=now)
                    except Exception:  # the failure has already been persisted
                        logger.exception(
                            "collector iteration failed",
                            extra={"service": "collector", "event_code": "iteration_failed"},
                        )
                    previous_scheduled = scheduled
                    next_slot = scheduled + timedelta(seconds=self.settings.status_poll_seconds)
                    wait_seconds = max((next_slot - datetime.now(tz=UTC)).total_seconds(), 0.1)
                    self.stopping.wait(wait_seconds)
            finally:
                self.repository.record_event(event_code="collector_stopped")
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": COLLECTOR_LOCK_ID}
                )

    def stop(self, *_args: object) -> None:
        self.stopping.set()

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    def _scheduled_slot(self, value: datetime) -> datetime:
        seconds = int(value.timestamp())
        interval = self.settings.status_poll_seconds
        return datetime.fromtimestamp(seconds - seconds % interval, tz=UTC)
