"""Read-only dashboard contract and aggregation over observed station hours."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import Engine, text

from bikeshare.api.contracts import within_toronto_envelope
from bikeshare.api.store import StationStore
from bikeshare.config import AppMode, Settings

TORONTO = ZoneInfo('America/Toronto')
DayType = Literal['all', 'weekday', 'weekend']


class DashboardResponse(BaseModel):
    version: str = '0.2.0'
    mode: Literal['fixture_demo', 'live_baseline']
    generated_at: datetime
    timezone: str = 'America/Toronto'
    source_kind: Literal['synthetic', 'live']
    filters: dict[str, Any]
    coverage: dict[str, Any]
    summary: dict[str, Any]
    current: dict[str, Any]
    stations: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    hourly: list[dict[str, Any]]
    heatmap: list[dict[str, Any]]
    health: list[dict[str, Any]]
    methodology: dict[str, Any]


def local_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive local dates, exclusive UTC endpoint; handles 23/25-hour days."""
    return (datetime.combine(start, time.min, TORONTO).astimezone(UTC),
            datetime.combine(end + timedelta(days=1), time.min, TORONTO).astimezone(UTC))


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ('observations', 'fresh_observations', 'dock_observations',
            'available_observations', 'docks_sum', 'bike_observations', 'bikes_sum')
    result = {key: sum(int(row[key]) for row in rows) for key in keys}
    def ratio(numerator: str, denominator: str) -> float | None:
        return round(result[numerator] / result[denominator], 4) if result[denominator] else None
    return {**result, 'average_docks': ratio('docks_sum', 'dock_observations'),
            'average_bikes': ratio('bikes_sum', 'bike_observations'),
            'availability_rate': ratio('available_observations', 'dock_observations'),
            'freshness_rate': ratio('fresh_observations', 'observations')}


def summarize(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return [{field: key, **metrics(values), 'station_count': len({r['station_id'] for r in values})}
            for key, values in sorted(groups.items())]


def read_history(engine: Engine, *, start: datetime, end: datetime) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        connection.execute(text("SET LOCAL statement_timeout='15s'"))
        return [dict(row) for row in connection.execute(text('''
            SELECT * FROM dashboard_station_hours
            WHERE source_kind='live' AND hour_start >= :start AND hour_start < :end
            ORDER BY hour_start, station_id
        '''), {'start': start, 'end': end}).mappings()]


def available_range(engine: Engine) -> tuple[datetime | None, datetime | None]:
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT min(hour_start), max(hour_start) FROM dashboard_station_hours WHERE source_kind='live'
        """)).one()
        return row[0], row[1]


def read_polls(engine: Engine, *, start: datetime, end: datetime) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(text('''
            SELECT b.scheduled_at, b.status, b.accepted_records, b.quarantined_records
            FROM poll_batches b JOIN source_datasets s ON s.id=b.source_id
            WHERE s.source_kind='live' AND b.scheduled_at >= :start AND b.scheduled_at < :end
            ORDER BY b.scheduled_at
        '''), {'start': start, 'end': end}).mappings()]


def fixture_history(stations: list[Any], start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Deterministic synthetic charts, served only in explicit fixture_demo mode."""
    rows = []
    at = start
    while at < end:
        local = at.astimezone(TORONTO)
        for i, station in enumerate(stations):
            capacity = station.capacity or 20
            docks = max(0, round(capacity * (0.4 + 0.32 * math.sin((local.hour + i*3)/3))))
            rows.append({'station_id': station.station_id, 'hour_start': at,
                         'observations': 60, 'fresh_observations': 58, 'dock_observations': 58,
                         'available_observations': 58 if docks > 2 else 36,
                         'docks_sum': docks*58, 'bike_observations': 58,
                         'bikes_sum': (capacity-docks)*58, 'computed_at': end})
        at += timedelta(hours=1)
    return rows


def build_dashboard(
    settings: Settings, store: StationStore, engine: Engine | None, *,
    start_date: date | None = None, end_date: date | None = None,
    station_id: str | None = None, day_type: DayType = 'all', hour: int | None = None,
    now: datetime | None = None,
) -> DashboardResponse:
    now = now or datetime.now(UTC)
    fixture = settings.app_mode is AppMode.FIXTURE_DEMO
    current_stations = store.all(decision_time=now)
    first: datetime | None
    last: datetime | None
    if fixture:
        first = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        last = now
    else:
        assert engine is not None
        first, last = available_range(engine)
    end_date = end_date or (last or now).astimezone(TORONTO).date()
    if start_date is None:
        # Open on the available history, not an almost-empty recent week after
        # a laptop outage. Never exceed the bounded 31-day query contract.
        earliest = first.astimezone(TORONTO).date() if first else end_date
        start_date = max(min(earliest, end_date), end_date - timedelta(days=30))
    if start_date > end_date or (end_date-start_date).days > 30:
        raise ValueError('Choose an inclusive date range of 1-31 days.')
    if end_date > now.astimezone(TORONTO).date():
        raise ValueError('Historical end date cannot be in the future.')
    start, end = local_bounds(start_date, end_date)
    end = min(end, now)
    if fixture:
        first, last = start, end
    rows = fixture_history(current_stations, start, end) if fixture else read_history(
        engine, start=start, end=end)  # type: ignore[arg-type]
    polls = [] if fixture else read_polls(engine, start=start, end=end)  # type: ignore[arg-type]
    station_names = {s.station_id: s for s in current_stations}
    known_ids = set(station_names) | {r['station_id'] for r in rows}
    if station_id and station_id not in known_ids:
        raise LookupError('Unknown station. Clear the station filter and try again.')
    def matches(local: datetime) -> bool:
        return ((day_type == 'all' or (local.weekday() < 5) == (day_type == 'weekday'))
                and (hour is None or local.hour == hour))
    selected = []
    for row in rows:
        local = row['hour_start'].astimezone(TORONTO)
        if (not station_id or row['station_id'] == station_id) and matches(local):
            selected.append({**row, 'local_hour': local.hour, 'weekday': local.weekday(),
                             'heat_key': local.weekday()*24 + local.hour})
    summary = metrics(selected)
    summary['station_count'] = len({r['station_id'] for r in selected})
    stations = []
    for item in summarize(selected, 'station_id'):
        meta = station_names.get(item['station_id'])
        stations.append({**item, 'name': meta.name if meta else item['station_id'],
                         'lat': meta.lat if meta else None, 'lon': meta.lon if meta else None,
                         'map_eligible': bool(meta and within_toronto_envelope(meta.lat, meta.lon))})
    current = []
    for s in current_stations:
        if station_id and s.station_id != station_id:
            continue
        fresh = s.source_last_reported is not None and -30 <= (now-s.source_last_reported).total_seconds() <= 300
        if fresh and s.is_installed and s.is_returning and s.num_docks_available is not None:
            current.append(s)
    poll_by_slot = {int(p['scheduled_at'].timestamp()) // settings.status_poll_seconds: p for p in polls}
    daily: dict[date, dict[str, Any]] = {}
    slot = math.ceil(start.timestamp() / settings.status_poll_seconds)
    stop = math.floor(end.timestamp() / settings.status_poll_seconds)
    for index in range(slot, stop):
        local = datetime.fromtimestamp(index*settings.status_poll_seconds, UTC).astimezone(TORONTO)
        if not matches(local):
            continue
        item = daily.setdefault(local.date(), {'date': local.date(), 'expected': 0,
                                               'success': 0, 'partial': 0, 'failed': 0, 'missing': 0})
        item['expected'] += 1
        status = 'success' if fixture else poll_by_slot.get(index, {}).get('status', 'missing')
        item[status if status in ('success', 'partial', 'failed') else 'missing'] += 1
    health = [{**v, 'coverage': v['success']/v['expected'] if v['expected'] else None} for v in daily.values()]
    expected = sum(d['expected'] for d in health)
    successes = sum(d['success'] for d in health)
    health_state = store.health()
    complete = health_state.get('latest_complete_at')
    stale = not fixture and (not isinstance(complete, datetime) or (now-complete).total_seconds() > 120)
    current_summary = {'fresh_stations': len(current), 'stations_with_dock': sum((s.num_docks_available or 0) > 0 for s in current),
                       'docks': sum(s.num_docks_available or 0 for s in current), 'stale': stale,
                       'latest_complete_poll': complete, 'scope': 'Current reports; date/day/hour filters do not apply.'}
    return DashboardResponse(
        mode='fixture_demo' if fixture else 'live_baseline', generated_at=now,
        source_kind='synthetic' if fixture else 'live',
        filters={'start_date': start_date, 'end_date': end_date, 'start_utc': start,
                 'end_utc': end, 'station_id': station_id,
                 'day_type': day_type, 'hour': hour},
        coverage={'first_hour': first, 'last_hour': last, 'observed_hours': len({r['hour_start'] for r in selected}),
                  'expected_polls': expected, 'successful_polls': successes,
                  'poll_coverage': successes/expected if expected else None,
                  'last_aggregated_at': max((r['computed_at'] for r in rows), default=None),
                  'notice': 'Gaps are missing data, not zero availability. Collection coverage is system-wide.'},
        summary=summary, current=current_summary, stations=stations,
        timeline=summarize(selected, 'hour_start'), hourly=summarize(selected, 'local_hour'),
        heatmap=summarize(selected, 'heat_key'), health=health,
        methodology={'availability': 'Fresh, installed, return-capable observations with ≥1 reported dock / all such observations with a known dock count.',
                     'average': 'Sum of reported docks / known dock observations. Observation-weighted, not a time-weighted continuous measurement.',
                     'freshness': 'Station last_reported within -30 to 300 seconds of retrieval; only canonical records.',
                     'coverage': 'Successful minute slots / expected scheduled slots in the selected Toronto-local time range, including outages. Station filter does not change this system-wide metric.',
                     'locations': 'Map uses current-known station coordinates, not historical positions. Missing or out-of-Toronto coordinates are excluded from the plot, with counts disclosed; their observations remain in totals/tables. It is a geographic plot, not a route map.',
                     'history': 'Version-2 hourly aggregates of retained snapshots. Archived-only history is not reconstructed. Repeated polls remain observations, not new trips.',
                     'forecast': 'Forecast validation, rider success, trip counts and rebalancing measurements are unavailable.'},
    )
