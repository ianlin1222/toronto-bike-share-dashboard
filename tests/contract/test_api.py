from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from bikeshare.api import main
from bikeshare.api.main import app
from bikeshare.config import AppMode, Settings

client = TestClient(app)


def test_fixture_health_and_station_contract() -> None:
    live = client.get("/livez")
    ready = client.get("/readyz")
    station = client.get("/v1/stations/7000")
    assert live.status_code == 200
    assert ready.status_code == 200
    assert ready.json()["mode"] == "fixture_demo"
    assert station.status_code == 200
    assert station.json()["available_docks"] == 4
    assert "fixture_timestamp_rebased" in station.json()["quality_flags"]


def test_recommendation_returns_primary_alternative_and_null_forecasts() -> None:
    response = client.post(
        "/v1/recommendations",
        headers={"X-Request-ID": "62f98b68-35bb-4408-8091-9bf4eceeec66"},
        json={
            "destination": {"lat": 43.6532, "lon": -79.3832},
            "horizon_minutes": 15,
            "radius_m": 750,
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "62f98b68-35bb-4408-8091-9bf4eceeec66"
    body = response.json()
    assert body["mode"] == "fixture_demo"
    assert body["primary"]["station_id"] == "7000"
    assert body["alternative"]["station_id"] == "7001"
    assert body["primary"]["forecast_probability"] is None
    assert body["fallback"]["used"] is True
    assert body["distance_kind"] == "haversine_straight_line"


def test_unsupported_horizon_is_not_rounded() -> None:
    response = client.post(
        "/v1/recommendations",
        json={
            "destination": {"lat": 43.6532, "lon": -79.3832},
            "horizon_minutes": 12,
            "radius_m": 750,
        },
    )
    assert response.status_code == 422


def test_prediction_endpoint_refuses_unvalidated_probability() -> None:
    response = client.post(
        "/v1/predictions/stations/7000",
        json={"horizon_minutes": 15},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_unavailable"


def test_unknown_station_and_service_envelope() -> None:
    assert client.get("/v1/stations/not-there").status_code == 404
    response = client.post(
        "/v1/recommendations",
        json={
            "destination": {"lat": 45.0, "lon": -79.3832},
            "horizon_minutes": 15,
            "radius_m": 750,
        },
    )
    assert response.status_code == 422


def test_home_assets_and_search_catalogue_work_without_database() -> None:
    assert client.get('/').status_code == 200
    assert client.get('/assets/app.js').status_code == 200
    catalogue = client.get('/v1/stations?q=City')
    assert catalogue.status_code == 200
    assert catalogue.json()['stations'][0]['name'] == 'City Hall'
    assert client.get('/v1/stations?q=NoSuchName').json()['stations'] == []


def test_recommendations_reject_old_complete_batch_even_with_recent_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    class Store:
        def health(self) -> dict[str, object]:
            now = datetime.now(UTC)
            return {'scheduled_at': now, 'ended_at': now, 'status': 'partial',
                    'latest_complete_at': now - timedelta(minutes=10)}

    monkeypatch.setattr(main, 'settings', Settings(app_mode=AppMode.LIVE_BASELINE))
    monkeypatch.setattr(main, 'station_store', lambda: Store())
    assert client.get('/readyz').status_code == 503
    response = client.post('/v1/recommendations', json={'destination': {'lat':43.6532,'lon':-79.3832}})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'stale_data'


def test_database_error_is_recoverable_and_does_not_expose_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_store() -> None:
        raise RuntimeError('postgresql://secret-password/private_database')

    monkeypatch.setattr(main, 'station_store', broken_store)
    for path in ['/v1/stations', '/v1/stations/7000']:
        response = client.get(path)
        assert response.status_code == 503
        assert 'secret-password' not in response.text
    assert client.post('/v1/predictions/stations/7000', json={'horizon_minutes':15}).status_code == 503
