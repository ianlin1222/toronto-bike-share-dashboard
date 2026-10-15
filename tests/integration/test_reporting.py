from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import ProgrammingError

from bikeshare.api.contracts import RecommendationRequest
from bikeshare.api.dashboard import read_history
from bikeshare.api.service import RecommendationService
from bikeshare.api.store import DatabaseStationStore
from bikeshare.config import AppMode, Settings
from bikeshare.db.repository import IngestionRepository
from bikeshare.ingestion.dashboard import refresh_dashboard_hours
from bikeshare.ingestion.summaries import refresh_reporting_summaries
from bikeshare.modeling.readiness import assess_live_history

pytestmark = pytest.mark.integration


def test_reporting_views_are_bounded_and_present(database_engine: Engine) -> None:
    summary_result = refresh_reporting_summaries(
        database_engine,
        now=datetime(2026, 9, 7, 12, 30, tzinfo=UTC),
    )
    assert summary_result["station_hourly_rows"] >= 1
    views = set(inspect(database_engine).get_view_names(schema="reporting"))
    assert views == {
        "v_ingestion_health",
        "v_model_calibration",
        "v_recommendation_performance",
        "v_refresh_status",
        "v_station_current",
        "v_station_hourly_availability",
        "v_dashboard_station_hours",
    }
    with database_engine.connect() as connection:
        refresh = connection.execute(text("SELECT * FROM reporting.v_refresh_status")).mappings().one()
        assert refresh["latest_evaluation_at"] is None
        columns = {
            row["column_name"]
            for row in connection.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema='reporting'
                    """
                )
            ).mappings()
        }
    assert "body" not in columns
    assert "destination_lat_rounded" not in columns

    readiness = assess_live_history(database_engine)
    assert readiness.ready_for_label_audit is False
    assert any("84" in blocker for blocker in readiness.blockers)


def test_reporting_and_api_roles_cannot_read_raw_evidence(database_engine: Engine) -> None:
    for role, allowed_query in (
        ('bikeshare_reporter', "SELECT count(*) FROM reporting.v_refresh_status"),
        ('bikeshare_api', "SELECT count(*) FROM stations"),
    ):
        with database_engine.begin() as connection:
            connection.execute(text(f'SET LOCAL ROLE {role}'))
            assert connection.scalar(text(allowed_query)) is not None
        with database_engine.begin() as connection, pytest.raises(ProgrammingError):
            connection.execute(text(f'SET LOCAL ROLE {role}'))
            connection.execute(text("SELECT body FROM raw_payload_blobs"))


def test_api_role_can_persist_an_idempotent_recommendation(database_engine: Engine) -> None:
    restricted = create_engine(database_engine.url, connect_args={'options': '-c role=bikeshare_api'})
    request_id = uuid.uuid4()
    try:
        service = RecommendationService(Settings(app_mode=AppMode.LIVE_BASELINE),
            DatabaseStationStore(IngestionRepository(restricted)))
        payload = RecommendationRequest(destination={'lat':43.6532,'lon':-79.3832})
        for _ in range(2):
            response = service.recommend(payload, request_id=request_id,
                now=datetime(2026,9,7,12,1,tzinfo=UTC))
            assert response.primary is not None
        with restricted.begin() as connection, pytest.raises(ProgrammingError):
            connection.execute(text('SELECT destination_lat_rounded FROM recommendation_requests'))
        with database_engine.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM recommendation_requests WHERE id=:id'), {'id':request_id}) == 1
    finally:
        restricted.dispose()


def test_dashboard_summary_is_idempotent_and_api_cannot_mix_fixture_into_live(database_engine: Engine) -> None:
    for _ in range(2):
        refresh_dashboard_hours(database_engine, now=datetime(2026,9,7,13,tzinfo=UTC),
                                since=datetime(2026,9,7,tzinfo=UTC))
    with database_engine.connect() as connection:
        row = connection.execute(text("""
            SELECT count(*), sum(observations), sum(dock_observations)
            FROM dashboard_station_hours WHERE source_kind='fixture'
        """)).one()
        assert row[0] == 2
        assert row[1] == 2  # the out-of-order repeated record is not canonical
        assert row[2] == 2
    restricted = create_engine(database_engine.url, connect_args={'options':'-c role=bikeshare_api'})
    try:
        assert read_history(restricted,start=datetime(2026,9,7,tzinfo=UTC),
                            end=datetime(2026,9,8,tzinfo=UTC)) == []
        with restricted.begin() as connection, pytest.raises(ProgrammingError):
            connection.execute(text('DELETE FROM dashboard_station_hours'))
    finally:
        restricted.dispose()
