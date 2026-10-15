from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from bikeshare.api.store import DatabaseStationStore
from bikeshare.db.repository import IngestionRepository


def test_serving_cache_expires_and_never_leaks_a_future_decision(monkeypatch):
    repository = Mock(spec=IngestionRepository)
    repository.get_current_stations.return_value = []
    clock = [10.0]
    monkeypatch.setattr('bikeshare.api.store.time.monotonic', lambda: clock[0])
    store = DatabaseStationStore(repository, cache_seconds=2)
    now = datetime(2026, 9, 16, tzinfo=UTC)
    store.all(decision_time=now)
    store.all(decision_time=now + timedelta(seconds=1))
    assert repository.get_current_stations.call_count == 1
    store.all(decision_time=now - timedelta(seconds=1))
    assert repository.get_current_stations.call_count == 2
    repository.get_current_stations.assert_called_with(decision_time=now - timedelta(seconds=1))
    clock[0] = 12.1
    store.all(decision_time=now + timedelta(seconds=3))
    assert repository.get_current_stations.call_count == 3


def test_cache_is_disabled_for_default_historical_store():
    repository = Mock(spec=IngestionRepository)
    repository.get_current_stations.return_value = []
    store = DatabaseStationStore(repository)
    now = datetime(2026, 9, 16, tzinfo=UTC)
    store.all(decision_time=now)
    store.all(decision_time=now)
    assert repository.get_current_stations.call_count == 2
