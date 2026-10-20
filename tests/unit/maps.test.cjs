// Run with: node --test tests/unit/maps.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../src/bikeshare/api/static/maps.js'), 'utf8');
class Element {
  constructor() { this.children = []; this.attrs = {}; this.listeners = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(key, fn) { this.listeners[key] = fn; }
}
function setup(withLibrary = true) {
  const markers = [], events = {}, maps = [];
  const L = {
    map() {
      const map = {loaded:false, removed:false,
        fitBounds() { this.loaded = true; }, invalidateSize() {}, remove() { this.removed = true; }};
      maps.push(map); return map;
    },
    tileLayer(url, options) {
      assert.equal(url, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
      assert.match(options.attribution, /OpenStreetMap/);
      return {on(name, fn) { events[name] = fn; return this; }, addTo() {}};
    },
    circleMarker() {
      const element = new Element();
      const marker = {addTo(map) { assert.equal(map.loaded, true); return this; },
        getElement() { return element; }, bindPopup(popup) { this.popup = popup; },
        on() {}, openPopup() { this.opened = true; }};
      markers.push(marker); return marker;
    },
    marker() { return L.circleMarker(); }, divIcon(options) { return options; }
  };
  const window = withLibrary ? {L} : {};
  vm.runInNewContext(source, {window, L, document:{createElement:() => new Element()}, setTimeout, clearTimeout});
  return {api:window.DocksideMaps, host:new Element(), markers, events, maps};
}
const point = {lat:43.6532, lon:-79.3832, label:'<img src=x onerror=alert(1)> station'};
test('missing library gives safe text and explicit location links; invalid coordinates excluded', () => {
  const {api,host} = setup(false);
  api.render(host, [point, {...point,lat:0}]);
  assert.match(host.children[0].textContent, /could not load/);
  const rows = host.children[1].children;
  assert.equal(rows.length, 1);
  assert.match(rows[0].textContent, /<img/); // Remains text, never innerHTML.
  assert.match(rows[0].children[0].href, /mlat=43.6532/);
  assert.equal(rows[0].children[0].rel, 'noopener noreferrer');
});
test('view precedes marker creation; popup/filter/keyboard work; rerender cleans up', () => {
  const {api,host,markers,maps} = setup();
  let selected = false, inspected = false;
  api.render(host, [{...point,action:()=>{selected=true;}}], ()=>{inspected=true;});
  markers[0].popup.children.at(-1).onclick();
  markers[0].getElement().listeners.keydown({key:'Enter',preventDefault(){}});
  assert.ok(selected && inspected && markers[0].opened);
  api.render(host, []);
  assert.ok(maps[0].removed);
  assert.match(host.children[0].textContent, /No valid Toronto/);
});
test('tile failures remain disclosed through batch completion and recover on new successful load', () => {
  const {api,host,events} = setup();
  api.render(host, [point]);
  events.loading(); events.tileerror(); events.load();
  assert.match(host.children[2].textContent, /could not load/);
  events.loading(); events.load();
  assert.match(host.children[2].textContent, /Street map loaded/);
});
