'use strict';
// Pure presentation rules, shared by the dashboard and dependency-free Node tests.
const DocksideDashboardLogic = {
  rankingRows(stations, minimum = 100) {
    return stations.filter(s => s.availability_rate != null && s.dock_observations >= minimum)
      .slice().sort((a, b) => a.availability_rate - b.availability_rate ||
        b.dock_observations - a.dock_observations ||
        String(a.station_id).localeCompare(String(b.station_id))).slice(0, 8);
  },
  resolveStation(value, catalog, historical) {
    if (!value) return null;
    return catalog.get(value) || ([...catalog.values()].includes(value) ? value : null) ||
      historical.find(s => s.station_id === value || `${s.name} · #${s.station_id}` === value)?.station_id || null;
  },
  inspectValue(value) {
    // This inspector exposes raw values; never round ratios/coordinates to one decimal.
    if (value == null) return '—';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  },
  snapshotAged(generatedAt, now = Date.now()) {
    const age = now - Date.parse(generatedAt);
    return Number.isFinite(age) && age > 120000;
  }
};
if (typeof module !== 'undefined') module.exports = DocksideDashboardLogic;
