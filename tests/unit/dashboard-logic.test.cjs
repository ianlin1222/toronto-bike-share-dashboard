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
