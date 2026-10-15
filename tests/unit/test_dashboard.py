from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest

from bikeshare.api import dashboard
from bikeshare.api.contracts import within_toronto_envelope
from bikeshare.api.dashboard import build_dashboard, local_bounds, metrics
from bikeshare.api.store import FixtureStationStore
from bikeshare.config import AppMode, Settings


@pytest.mark.parametrize('lat,lon,expected', [(43.65,-79.38,True),(0,0,False),(None,-79.38,False)])
def test_geographic_plot_excludes_missing_and_out_of_toronto_locations(lat, lon, expected):
    assert within_toronto_envelope(lat, lon) is expected


def test_local_date_bounds_respect_both_dst_transitions():
    for day, hours in [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)]:
        start, end = local_bounds(day, day)
        assert (end-start).total_seconds() == hours*3600


def test_weighted_metrics_preserve_unknowns_and_do_not_average_averages():
    assert metrics([])['average_docks'] is None
    assert metrics([])['availability_rate'] is None
    rows = [{'observations': n, 'fresh_observations': n, 'dock_observations': n,
             'available_observations': n, 'docks_sum': docks*n,
             'bike_observations': 0, 'bikes_sum': 0} for n, docks in [(1, 10), (9, 0)]]
    assert metrics(rows)['average_docks'] == 1
    assert metrics(rows)['average_bikes'] is None


def test_fixture_filters_are_explicit_and_do_not_write_history():
    settings = Settings(app_mode=AppMode.FIXTURE_DEMO)
    store = FixtureStationStore(settings.fixture_path)
    result = build_dashboard(settings, store, None, start_date=date(2026,10,8),
        end_date=date(2026,10,14), station_id='7000', day_type='weekend', hour=9,
        now=datetime(2026,10,14,16,tzinfo=UTC))
    assert result.source_kind == 'synthetic'
    assert result.mode == 'fixture_demo'
    assert result.summary['station_count'] == 1
    assert result.stations[0]['map_eligible'] is True
    assert len(result.timeline) == 2
    assert {p['local_hour'] for p in result.hourly} == {9}
    assert len(result.health) == 2


def test_live_empty_history_stays_unknown_and_missing_polls_count(monkeypatch):
    settings = Settings(app_mode=AppMode.LIVE_BASELINE)
    store = Mock()
    store.all.return_value = []
    store.health.return_value = {}
    monkeypatch.setattr(dashboard, 'available_range', lambda _: (None,None))
    monkeypatch.setattr(dashboard, 'read_history', lambda *a, **k: [])
    monkeypatch.setattr(dashboard, 'read_polls', lambda *a, **k: [
        {'scheduled_at':datetime(2026,10,13,4,tzinfo=UTC),'status':'success'},
        {'scheduled_at':datetime(2026,10,13,4,1,tzinfo=UTC),'status':'partial'}])
    result = build_dashboard(settings, store, Mock(), start_date=date(2026,10,13),
        end_date=date(2026,10,13), now=datetime(2026,10,14,16,tzinfo=UTC))
    assert result.summary['average_docks'] is None
    assert result.timeline == []
    assert result.source_kind == 'live'
    assert result.current['stale'] is True
    assert result.coverage['successful_polls'] == 1
    assert result.coverage['expected_polls'] == 1440
    assert result.health[0]['missing'] == 1438
    assert result.health[0]['partial'] == 1


def test_default_period_shows_available_history_but_is_bounded(monkeypatch):
    settings = Settings(app_mode=AppMode.LIVE_BASELINE)
    store = Mock()
    store.all.return_value = []
    store.health.return_value = {}
    monkeypatch.setattr(dashboard, 'read_history', lambda *a, **k: [])
    monkeypatch.setattr(dashboard, 'read_polls', lambda *a, **k: [])
    for first, expected in [(datetime(2026,9,16,18,tzinfo=UTC), date(2026,9,16)),
                            (datetime(2026,8,1,18,tzinfo=UTC), date(2026,9,14))]:
        monkeypatch.setattr(dashboard, 'available_range', lambda _, first=first:
                            (first, datetime(2026,10,14,15,tzinfo=UTC)))
        result = build_dashboard(settings, store, Mock(), now=datetime(2026,10,14,16,tzinfo=UTC))
        assert result.filters['start_date'] == expected
        assert result.filters['end_date'] == date(2026,10,14)


@pytest.mark.parametrize('start,end',[(date(2026,1,1),date(2026,2,1)),(date(2026,10,14),date(2026,10,13))])
def test_date_range_limits(start,end):
    settings=Settings(app_mode=AppMode.FIXTURE_DEMO)
    with pytest.raises(ValueError):
        build_dashboard(settings,FixtureStationStore(settings.fixture_path),None,
                        start_date=start,end_date=end)
