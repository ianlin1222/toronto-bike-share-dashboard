from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text


def refresh_reporting_summaries(engine: Engine, *, now: datetime | None = None) -> dict[str, int]:
    refreshed_at = now or datetime.now(tz=UTC)
    hourly_start = (refreshed_at - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    daily_start = (refreshed_at - timedelta(days=2)).date()
    with engine.begin() as connection:
        hourly = connection.execute(
            text(
                """
                INSERT INTO station_hourly_summary (
                    station_id, local_hour_start, source_kind, observation_count,
                    operational_observation_count, average_docks, minimum_docks,
                    full_observation_count, fresh_coverage_rate, computed_at
                )
                SELECT
                    snapshot.station_id,
                    date_trunc('hour', snapshot.retrieved_at) AS utc_hour_start,
                    snapshot.provenance_kind,
                    count(*) AS observation_count,
                    count(*) FILTER (
                      WHERE snapshot.is_installed AND snapshot.is_returning
                    ) AS operational_observation_count,
                    avg(snapshot.num_docks_available) FILTER (
                      WHERE snapshot.is_installed AND snapshot.is_returning
                    ) AS average_docks,
                    min(snapshot.num_docks_available) FILTER (
                      WHERE snapshot.is_installed AND snapshot.is_returning
                    ) AS minimum_docks,
                    count(*) FILTER (
                      WHERE snapshot.is_installed AND snapshot.is_returning
                        AND snapshot.num_docks_available = 0
                    ) AS full_observation_count,
                    avg(
                      CASE
                        WHEN snapshot.source_last_reported IS NOT NULL
                          AND extract(epoch FROM (
                            snapshot.retrieved_at - snapshot.source_last_reported
                          )) BETWEEN -30 AND 300
                        THEN 1.0 ELSE 0.0
                      END
                    ) AS fresh_coverage_rate,
                    :refreshed_at
                FROM station_snapshots snapshot
                WHERE snapshot.retrieved_at >= :hourly_start
                  AND snapshot.is_canonical
                GROUP BY 1, 2, 3
                ON CONFLICT (station_id, local_hour_start, source_kind) DO UPDATE SET
                    observation_count = EXCLUDED.observation_count,
                    operational_observation_count = EXCLUDED.operational_observation_count,
                    average_docks = EXCLUDED.average_docks,
                    minimum_docks = EXCLUDED.minimum_docks,
                    full_observation_count = EXCLUDED.full_observation_count,
                    fresh_coverage_rate = EXCLUDED.fresh_coverage_rate,
                    computed_at = EXCLUDED.computed_at
                """
            ),
            {"hourly_start": hourly_start, "refreshed_at": refreshed_at},
        ).rowcount
        daily = connection.execute(
            text(
                """
                INSERT INTO pipeline_daily_summary (
                    summary_date, source_id, scheduled_polls, successful_polls,
                    partial_polls, failed_polls, accepted_records, quarantined_records,
                    average_latency_ms, station_coverage_rate, stale_station_rate, computed_at
                )
                SELECT
                    batch.scheduled_at::date,
                    batch.source_id,
                    count(*) AS scheduled_polls,
                    count(*) FILTER (WHERE batch.status = 'success'),
                    count(*) FILTER (WHERE batch.status = 'partial'),
                    count(*) FILTER (WHERE batch.status = 'failed'),
                    coalesce(sum(batch.accepted_records), 0),
                    coalesce(sum(batch.quarantined_records), 0),
                    avg(batch.latency_ms),
                    avg(
                      CASE WHEN batch.expected_records > 0
                        THEN batch.accepted_records::double precision / batch.expected_records
                      END
                    ),
                    NULL::double precision,
                    :refreshed_at
                FROM poll_batches batch
                WHERE batch.scheduled_at::date >= :daily_start
                GROUP BY 1, 2
                ON CONFLICT (summary_date, source_id) DO UPDATE SET
                    scheduled_polls = EXCLUDED.scheduled_polls,
                    successful_polls = EXCLUDED.successful_polls,
                    partial_polls = EXCLUDED.partial_polls,
                    failed_polls = EXCLUDED.failed_polls,
                    accepted_records = EXCLUDED.accepted_records,
                    quarantined_records = EXCLUDED.quarantined_records,
                    average_latency_ms = EXCLUDED.average_latency_ms,
                    station_coverage_rate = EXCLUDED.station_coverage_rate,
                    stale_station_rate = EXCLUDED.stale_station_rate,
                    computed_at = EXCLUDED.computed_at
                """
            ),
            {"daily_start": daily_start, "refreshed_at": refreshed_at},
        ).rowcount
    from bikeshare.ingestion.dashboard import refresh_dashboard_hours

    dashboard = refresh_dashboard_hours(engine, now=refreshed_at)
    return {"station_hourly_rows": hourly, "pipeline_daily_rows": daily, "dashboard_rows": dashboard}
