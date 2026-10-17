"""The exact portfolio CTE runs against tiny synthetic CTE inputs, not live data."""

from pathlib import Path

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_case_study_dedup_freshness_nulls_and_missing_polls(database_engine):
    prefix = (Path(__file__).parents[2] / "analysis/portfolio/sql/00_prepare.sql").read_text()
    # Explicit parameter binding for the psql variable syntax in this SQL-only fixture.
    values = {
        "start_utc": "'2026-01-01T12:00:00Z'",
        "end_utc_exclusive": "'2026-01-01T12:05:00Z'",
        "timezone": "'America/Toronto'",
        "fresh_seconds": "300",
    }
    for name, value in values.items():
        prefix = prefix.replace(f":'{name}'", value).replace(f":{name}", value)
    prefix = prefix.replace("WITH study_raw", ", study_raw", 1)
    fixture = """
    WITH input(station_id,delay,age,docks,installed,return_capable,canonical,kind,ingest_delay) AS (
      VALUES ('A',0,0,1,true,true,true,'live',0),
        ('A',60,60,1,true,true,true,'live',0),
        ('B',0,600,1,true,true,true,'live',0),
        ('C',0,0,1,true,false,true,'live',0),
        ('D',0,0,NULL,true,true,true,'live',0),
        ('E',0,0,0,true,true,true,'live',0),
        ('F',0,-60,1,true,true,true,'live',0),
        ('G',0,0,1,true,true,true,'fixture',0),
        ('H',0,0,1,true,true,false,'live',0),
        ('I',0,0,1,true,true,true,'live',600)
    ), station_snapshots AS (
      SELECT row_number() OVER() AS snapshot_id,station_id,1 AS feed_fetch_id,
        NULL::bigint AS metadata_version_id,
        '2026-01-01T12:00:00Z'::timestamptz+delay*interval '1 second' AS retrieved_at,
        '2026-01-01T12:00:00Z'::timestamptz+(delay+ingest_delay)*interval '1 second' AS ingested_at,
        '2026-01-01T12:00:00Z'::timestamptz+(delay-age)*interval '1 second' AS source_last_reported,
        docks AS num_docks_available,installed AS is_installed,return_capable AS is_returning,
        canonical AS is_canonical,kind AS provenance_kind FROM input
    ), station_metadata_versions AS (
      SELECT 1::bigint id,'X'::text name,43.65::float lat,-79.38::float lon,
        20 capacity,'2026-01-01T11:00:00Z'::timestamptz known_from_at WHERE false
    ), source_datasets AS (SELECT 1 AS id,'live'::text AS source_kind),
    poll_batches AS (
      SELECT 1 AS source_id,'2026-01-01T12:00:00Z'::timestamptz AS scheduled_at,'success'::text AS status
    )
    """
    query = (
        fixture
        + prefix
        + """
    SELECT (SELECT count(*) FROM study_raw), (SELECT count(*) FROM study_unique),
      (SELECT count(*) FROM study_eligible),
      (SELECT count(*) FROM study_eligible WHERE num_docks_available=0),
      (SELECT count(*) FROM study_minutes),
      (SELECT count(*) FROM study_minutes WHERE successful)
    """
    )
    with database_engine.connect() as conn:
        assert tuple(conn.execute(text(query)).one()) == (8, 6, 2, 1, 5, 1)
