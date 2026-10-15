from fastapi.testclient import TestClient

from bikeshare.api import main

client = TestClient(main.app)


def test_dashboard_assets_and_fixture_contract():
    assert 'System overview' in client.get('/').text
    assert client.get('/dashboard').status_code == 200
    assert 'Where are you headed?' in client.get('/demo').text
    for asset in ('dashboard.js','dashboard.css'):
        assert client.get('/assets/'+asset).status_code == 200
    response=client.get('/v1/dashboard?start_date=2026-10-10&end_date=2026-10-11&hour=8')
    assert response.status_code == 200
    body=response.json()
    assert body['source_kind'] == 'synthetic'
    assert body['version'] == '0.2.0'
    assert body['filters']['hour'] == 8
    assert len(body['timeline']) == 2
    assert body['methodology']['forecast']


def test_dashboard_rejects_invalid_filters_and_unknown_station():
    for query in ('hour=24','hour=-1','day_type=holidays','start_date=nope',
                  'start_date=2026-01-01&end_date=2026-02-10'):
        assert client.get('/v1/dashboard?'+query).status_code == 422
    assert client.get('/v1/dashboard?station_id=missing').status_code == 404


def test_dashboard_database_failure_is_explicit_and_sanitized(monkeypatch):
    def unavailable(*args,**kwargs):
        raise RuntimeError('secret-database-password')
    monkeypatch.setattr(main,'build_dashboard',unavailable)
    response=client.get('/v1/dashboard')
    assert response.status_code == 503
    assert 'secret-database-password' not in response.text
    assert response.json()['detail']['code'] == 'dashboard_unavailable'
