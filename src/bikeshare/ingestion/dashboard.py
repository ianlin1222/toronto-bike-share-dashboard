"""Versioned observation aggregates: no trip reconstruction or gap filling."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text


def refresh_dashboard_hours(
    engine: Engine, *, now: datetime | None = None, since: datetime | None = None,
) -> int:
    end = now or datetime.now(UTC)
    start = (since or end - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    with engine.begin() as connection:
        return connection.execute(text("""
            INSERT INTO dashboard_station_hours
              (station_id, hour_start, source_kind, observations, fresh_observations,
               dock_observations, available_observations, docks_sum,
               bike_observations, bikes_sum, computed_at)
            SELECT station_id, date_trunc('hour', retrieved_at), provenance_kind,
              count(*), count(*) FILTER (WHERE fresh),
              count(*) FILTER (WHERE fresh AND operational AND num_docks_available IS NOT NULL),
              count(*) FILTER (WHERE fresh AND operational AND num_docks_available > 0),
              coalesce(sum(num_docks_available) FILTER (WHERE fresh AND operational), 0),
              count(*) FILTER (WHERE fresh AND operational AND num_bikes_available IS NOT NULL),
              coalesce(sum(num_bikes_available) FILTER (WHERE fresh AND operational), 0), :end
            FROM (
              SELECT *, is_installed AND is_returning AS operational,
                extract(epoch FROM retrieved_at-source_last_reported) BETWEEN -30 AND 300 AS fresh
              FROM station_snapshots
              WHERE retrieved_at >= :start AND retrieved_at <= :end
                AND ingested_at <= :end AND is_canonical
            ) snapshots
            GROUP BY 1, 2, 3
            ON CONFLICT (station_id, hour_start, source_kind) DO UPDATE SET
              observations=EXCLUDED.observations,
              fresh_observations=EXCLUDED.fresh_observations,
              dock_observations=EXCLUDED.dock_observations,
              available_observations=EXCLUDED.available_observations,
              docks_sum=EXCLUDED.docks_sum, bike_observations=EXCLUDED.bike_observations,
              bikes_sum=EXCLUDED.bikes_sum, computed_at=EXCLUDED.computed_at
        """), {'start': start, 'end': end}).rowcount
