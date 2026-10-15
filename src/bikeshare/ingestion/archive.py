from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import Engine, text

from bikeshare.db.repository import IngestionRepository


class ArchiveVerificationError(RuntimeError):
    pass


def ensure_monthly_partitions(engine: Engine, *, months_ahead: int = 3) -> list[str]:
    now = datetime.now(tz=UTC)
    first = date(now.year, now.month, 1)
    created: list[str] = []
    with engine.begin() as connection:
        for offset in range(0, months_ahead + 1):
            month_start = _add_months(first, offset)
            month_end = _add_months(first, offset + 1)
            partition = f"station_snapshots_{month_start:%Y_%m}"
            # Names and bounds are generated from date objects, never external input.
            connection.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {partition}
                    PARTITION OF station_snapshots
                    FOR VALUES FROM ('{month_start.isoformat()}') TO ('{month_end.isoformat()}')
                    """
                )
            )
            created.append(partition)
    return created


def archive_history(
    engine: Engine,
    *,
    output_root: Path,
    snapshot_cutoff: datetime,
    raw_cutoff: datetime,
    delete_after_verify: bool = False,
) -> dict[str, Any]:
    if snapshot_cutoff.tzinfo is None or raw_cutoff.tzinfo is None:
        raise ValueError("archive cutoffs must be timezone-aware")
    # Only complete UTC days may move out of the online window.
    snapshot_cutoff = snapshot_cutoff.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    output_root.mkdir(parents=True, exist_ok=True)
    archived_days: list[dict[str, Any]] = []
    with engine.connect() as connection:
        days = [
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT DISTINCT retrieved_at::date
                    FROM station_snapshots
                    WHERE retrieved_at < :cutoff
                    ORDER BY 1
                    """
                ),
                {"cutoff": snapshot_cutoff},
            )
        ]
    for day in days:
        archived_days.append(
            _archive_snapshot_day(
                engine,
                output_root=output_root,
                day=day,
                delete_after_verify=delete_after_verify,
            )
        )
    raw_result = _archive_raw_blobs(
        engine,
        output_root=output_root,
        raw_cutoff=raw_cutoff,
        delete_after_verify=delete_after_verify,
    )
    result = {
        "snapshot_cutoff": snapshot_cutoff.isoformat(),
        "raw_cutoff": raw_cutoff.isoformat(),
        "delete_after_verify": delete_after_verify,
        "snapshot_days": archived_days,
        "raw_blobs": raw_result,
    }
    IngestionRepository(engine).record_event(event_code="archive_completed", detail=result)
    return result


def _archive_snapshot_day(
    engine: Engine,
    *,
    output_root: Path,
    day: date,
    delete_after_verify: bool,
) -> dict[str, Any]:
    day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    directory = output_root / "snapshots" / f"year={day.year:04d}" / f"month={day.month:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"day={day.day:02d}.parquet"
    partial = target.with_suffix(".parquet.partial")
    query = text(
        """
        SELECT snapshot_id, retrieved_at, station_id, feed_fetch_id, metadata_version_id,
               ingested_at, feed_last_updated, source_last_reported,
               num_docks_available, num_docks_disabled, num_bikes_available,
               num_bikes_disabled, is_installed, is_renting, is_returning,
               vehicle_types_available::text, vehicle_docks_available::text,
               quality_flags, provenance_kind, is_canonical
        FROM station_snapshots
        WHERE retrieved_at >= :day_start AND retrieved_at < :day_end
        ORDER BY retrieved_at, station_id
        """
    )
    writer: pq.ParquetWriter | None = None
    written_rows = 0
    try:
        with engine.connect() as connection:
            for frame in pd.read_sql(
                query,
                connection,
                params={"day_start": day_start, "day_end": day_end},
                chunksize=100_000,
            ):
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(partial, table.schema, compression="zstd")
                writer.write_table(table)
                written_rows += len(frame)
    finally:
        if writer is not None:
            writer.close()
    if written_rows == 0:
        if partial.exists():
            partial.unlink()
        raise ArchiveVerificationError(f"snapshot day {day} unexpectedly contained no rows")
    parquet_metadata = pq.read_metadata(partial)
    if parquet_metadata.num_rows != written_rows:
        raise ArchiveVerificationError(
            f"Parquet row mismatch for {day}: wrote {written_rows}, "
            f"read {parquet_metadata.num_rows}"
        )
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ArchiveVerificationError(f'Existing immutable archive for {day} differs; refusing to overwrite it')
    os.replace(partial, target)
    manifest = target.with_suffix(".manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "utc_day": day.isoformat(),
                "rows": written_rows,
                "sha256": digest,
                "file": target.name,
                "created_at": datetime.now(tz=UTC).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    deleted = 0
    if delete_after_verify:
        with engine.begin() as connection:
            deleted = int(
                connection.execute(
                    text(
                        """
                        DELETE FROM station_snapshots
                        WHERE retrieved_at >= :day_start AND retrieved_at < :day_end
                        """
                    ),
                    {"day_start": day_start, "day_end": day_end},
                ).rowcount
            )
            if deleted != written_rows:
                raise ArchiveVerificationError(
                    f"database delete count {deleted} differs from archive rows {written_rows}"
                )
    return {
        "utc_day": day.isoformat(),
        "rows": written_rows,
        "sha256": digest,
        "path": str(target),
        "deleted_rows": deleted,
    }


def _archive_raw_blobs(
    engine: Engine,
    *,
    output_root: Path,
    raw_cutoff: datetime,
    delete_after_verify: bool,
) -> dict[str, int]:
    with engine.connect() as connection:
        rows = list(
            connection.execute(
                text(
                    """
                    SELECT DISTINCT blob.sha256, blob.body
                    FROM raw_payload_blobs blob
                    JOIN feed_fetches retrieved_feed
                      ON retrieved_feed.raw_sha256 = blob.sha256
                    WHERE retrieved_feed.retrieved_at < :cutoff AND blob.body IS NOT NULL
                    """
                ),
                {"cutoff": raw_cutoff},
            ).mappings()
        )
    archived = 0
    released = 0
    for row in rows:
        digest = str(row["sha256"])
        compressed = bytes(row["body"])
        if hashlib.sha256(gzip.decompress(compressed)).hexdigest() != digest:
            raise ArchiveVerificationError(f"raw blob {digest} failed SHA-256 verification")
        directory = output_root / "raw" / digest[:2]
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{digest}.json.gz"
        partial = target.with_suffix(".json.gz.partial")
        partial.write_bytes(compressed)
        os.replace(partial, target)
        if hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest() != digest:
            raise ArchiveVerificationError(f"written raw blob {digest} failed verification")
        archived += 1
        if delete_after_verify:
            relative_uri = target.relative_to(output_root).as_posix()
            with engine.begin() as connection:
                released += connection.execute(
                    text(
                        """
                        UPDATE raw_payload_blobs
                        SET body = NULL, archive_uri = :archive_uri
                        WHERE sha256 = :sha256 AND body IS NOT NULL
                        """
                    ),
                    {"archive_uri": relative_uri, "sha256": digest},
                ).rowcount
    return {"archived": archived, "database_bodies_released": released}


def _add_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    return date(absolute // 12, absolute % 12 + 1, 1)
