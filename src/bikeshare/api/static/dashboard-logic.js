'use strict';
// Pure presentation rules, shared by the dashboard and dependency-free Node tests.
const DocksideDashboardLogic = {
  stationAnalysis(stations, minimum = 100) {
    // Recalculate ratios from integer counts, not the API's rounded display rates.
    const count = value => Number.isSafeInteger(value) && value >= 0;
    const known = stations.filter(s => count(s.dock_observations) && s.dock_observations > 0 &&
      count(s.available_observations) && s.available_observations <= s.dock_observations);
    const included = known.filter(s => s.dock_observations >= minimum).map(s => ({
      station_id:s.station_id, name:s.name, usable_observations:s.dock_observations,
      full_observations:s.dock_observations-s.available_observations,
      full_share:(s.dock_observations-s.available_observations)/s.dock_observations,
      average_docks:count(s.docks_sum) ? s.docks_sum/s.dock_observations : null,
      minimum_station_observations:minimum
    })).sort((a,b)=>String(a.station_id).localeCompare(String(b.station_id)));
    const bounds = [0,10,25,50,75,100];
    const bins = bounds.slice(0,-1).map((lower,i)=>{
      const upper=bounds[i+1],last=i===bounds.length-2;
      const members=included.filter(s=>s.full_observations*100>=lower*s.usable_observations &&
        (last?s.full_observations*100<=upper*s.usable_observations:s.full_observations*100<upper*s.usable_observations));
      return {band:`${lower}–${last?'':'<'}${upper}%`,lower_percent:lower,upper_percent:upper,
        upper_inclusive:last,station_count:members.length,
        share_of_included_stations:included.length?members.length/included.length:null,
        minimum_station_observations:minimum,members};
    });
    return {included,bins,excluded_unknown:stations.length-known.length,
      excluded_sparse:known.length-included.length};
  },
  dayTypeProfile(heatmap, minimum = 100) {
    return ['Weekday','Weekend'].flatMap(day_type=>Array.from({length:24},(_,local_hour)=>{
      const rows=heatmap.filter(r=>r.heat_key%24===local_hour &&
        (Math.floor(r.heat_key/24)<5)===(day_type==='Weekday'));
      const usable_observations=rows.reduce((sum,r)=>sum+r.dock_observations,0);
      const available_observations=rows.reduce((sum,r)=>sum+r.available_observations,0);
      const supported=usable_observations>0 && usable_observations>=minimum;
      return {day_type,local_hour,available_observations,usable_observations,
        availability_rate:supported?available_observations/usable_observations:null,
        support_status:!usable_observations?'no_usable_observations':supported?'shown':'below_minimum',
        minimum_cell_observations:minimum};
    }));
  },
  qualityBreakdown(summary) {
    const {observations:total,fresh_observations:fresh,dock_observations:usable,
      available_observations:available}=summary;
    if(![total,fresh,usable,available].every(n=>Number.isSafeInteger(n)&&n>=0) ||
      fresh>total || usable>fresh || available>usable)return null;
    return [
      ['Usable · a dock available',available,'Fresh, installed, accepting returns; reported docks ≥1.'],
      ['Usable · zero docks',usable-available,'Fresh, installed, accepting returns; reported docks =0.'],
      ['Fresh · not usable',fresh-usable,'Not installed/return-capable, unknown operating flags, or missing dock count; combined reasons cannot be separated here.'],
      ['Not fresh / time unknown',total-fresh,'Outside the freshness window or missing source report time.']
    ].map(([category,observation_count,definition])=>({category,observation_count,
      share_of_recorded_observations:total?observation_count/total:null,
      recorded_observations:total,definition}));
  },
  rankingRows(stations, minimum = 100) {
    const rate=s=>Number.isFinite(s.available_observations) && s.dock_observations>0
      ?s.available_observations/s.dock_observations:s.availability_rate;
    return stations.filter(s => s.availability_rate != null && s.dock_observations >= minimum)
      .slice().sort((a, b) => rate(a) - rate(b) ||
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
