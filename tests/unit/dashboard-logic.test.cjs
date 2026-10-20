const {test} = require('node:test');
const assert = require('node:assert/strict');
const logic = require('../../src/bikeshare/api/static/dashboard-logic.js');
test('ranking has one deterministic order and explicit support threshold without mutating input', () => {
  const rows = [
    {station_id:'b',availability_rate:.2,dock_observations:100},
    {station_id:'a',availability_rate:.2,dock_observations:100},
    {station_id:'c',availability_rate:0,dock_observations:1},
    {station_id:'d',availability_rate:null,dock_observations:1000},
    {station_id:'e',availability_rate:.2,dock_observations:200}
  ];
  assert.deepEqual(logic.rankingRows(rows).map(s=>s.station_id), ['e','a','b']);
  assert.equal(logic.rankingRows(rows,0)[0].station_id,'c');
  assert.equal(rows[0].station_id,'b');
});
test('historical station filters work without a current catalogue entry', () => {
  const rows=[{station_id:'retired',name:'Old location'}],catalog=new Map([['City Hall · #7000','7000']]);
  assert.equal(logic.resolveStation('retired',catalog,rows),'retired');
  assert.equal(logic.resolveStation('Old location · #retired',catalog,rows),'retired');
  assert.equal(logic.resolveStation('City Hall · #7000',catalog,rows),'7000');
  assert.equal(logic.resolveStation('unrecognized',catalog,rows),null);
});
test('inspector preserves ratios, coordinates, booleans and missing values', () => {
  assert.equal(logic.inspectValue(.941), '0.941');
  assert.equal(logic.inspectValue(-79.3832), '-79.3832');
  assert.equal(logic.inspectValue(0), '0');
  assert.equal(logic.inspectValue(false), 'false');
  assert.equal(logic.inspectValue(null), '—');
});
test('current strip expires by elapsed time rather than changing historical data', () => {
  const start=Date.parse('2026-10-20T12:00:00Z');
  assert.equal(logic.snapshotAged('2026-10-20T12:00:00Z',start+120000),false);
  assert.equal(logic.snapshotAged('2026-10-20T12:00:00Z',start+120001),true);
});

function station(id,n,available,docks=100) {
  return {station_id:id,name:id,dock_observations:n,available_observations:available,docks_sum:docks};
}
test('distribution bins partition stations at exact boundaries; exclude unknowns and disclose sparse rows', () => {
  const rows=[station('zero',100,100),station('ten',100,90),station('quarter',100,75),
    station('half',100,50),station('threequarters',100,25),station('full',100,0),
    station('sparse',1,0),station('unknown',0,0),station('invalid',100,101)];
  const result=logic.stationAnalysis(rows);
  assert.deepEqual(result.bins.map(b=>b.station_count),[1,1,1,1,2]);
  assert.equal(result.bins.reduce((n,b)=>n+b.station_count,0),result.included.length);
  assert.equal(result.excluded_sparse,1);
  assert.equal(result.excluded_unknown,2);
  assert.equal(result.included.find(s=>s.station_id==='ten').full_share,.1);
  assert.equal(logic.stationAnalysis(rows,500).included.length,0);
  assert.equal(logic.stationAnalysis(rows,0).included.length,7);
});
test('scatter uses unrounded paired numerator/denominator, retaining missing averages as null', () => {
  const result=logic.stationAnalysis([station('a',300,100,100),station('b',300,0,null)]);
  assert.equal(result.included[0].average_docks,1/3);
  assert.equal(result.included[0].full_share,2/3);
  assert.equal(result.included[1].average_docks,null);
  assert.equal(result.bins.reduce((n,b)=>n+b.station_count,0),2);
});
test('ranking distinguishes close rates before rounding instead of creating a false tie', () => {
  const rows=[{...station('a',100000,80004),availability_rate:.8},
    {...station('b',100000,80001),availability_rate:.8}];
  assert.deepEqual(logic.rankingRows(rows).map(s=>s.station_id),['b','a']);
});
test('day-type rates aggregate counts, never average rates; empty and low-support hours stay null', () => {
  const rows=[{heat_key:9,dock_observations:100,available_observations:50},
    {heat_key:24+9,dock_observations:900,available_observations:900},
    {heat_key:5*24+9,dock_observations:99,available_observations:99},
    {heat_key:6*24+10,dock_observations:100,available_observations:0}];
  const profile=logic.dayTypeProfile(rows),at=(day,h)=>profile.find(r=>r.day_type===day&&r.local_hour===h);
  assert.equal(profile.length,48);
  assert.equal(at('Weekday',9).availability_rate,.95);
  assert.equal(at('Weekend',9).availability_rate,null);
  assert.equal(at('Weekend',9).support_status,'below_minimum');
  assert.equal(at('Weekend',10).availability_rate,0);
  assert.equal(at('Weekday',10).support_status,'no_usable_observations');
  assert.equal(at('Weekday',10).availability_rate,null);
});
test('observation-quality categories reconcile exactly and invalid hierarchies fail closed', () => {
  const summary={observations:100,fresh_observations:90,dock_observations:80,available_observations:70};
  const rows=logic.qualityBreakdown(summary);
  assert.deepEqual(rows.map(r=>r.observation_count),[70,10,10,10]);
  assert.equal(rows.reduce((n,r)=>n+r.observation_count,0),100);
  assert.equal(rows[0].share_of_recorded_observations,.7);
  assert.equal(logic.qualityBreakdown({...summary,available_observations:81}),null);
  assert.equal(logic.qualityBreakdown({...summary,fresh_observations:101}),null);
  assert.equal(logic.qualityBreakdown({...summary,dock_observations:null}),null);
});
test('empty datasets do not manufacture positive evidence or zero availability', () => {
  assert.equal(logic.stationAnalysis([]).bins[0].share_of_included_stations,null);
  assert.ok(logic.dayTypeProfile([]).every(r=>r.availability_rate===null));
  const rows=logic.qualityBreakdown({observations:0,fresh_observations:0,dock_observations:0,available_observations:0});
  assert.ok(rows.every(r=>r.share_of_recorded_observations===null));
});
