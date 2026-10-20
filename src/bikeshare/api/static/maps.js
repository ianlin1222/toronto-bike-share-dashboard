'use strict';
// Shared street-map presentation; no geocoding, routing, or inventory inference.
window.DocksideMaps = (() => {
  const instances = new WeakMap();
  const node = (tag, text) => {
    const element = document.createElement(tag);
    if (text != null) element.textContent = text;
    return element;
  };
  function locationLink(point) {
    const link = node('a', 'Open location in OpenStreetMap ↗');
    link.href = `https://www.openstreetmap.org/?mlat=${point.lat}&mlon=${point.lon}#map=17/${point.lat}/${point.lon}`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }
  function renderMap(host, points, onInspect) {
    const previous = instances.get(host);
    if (previous) { clearTimeout(previous.timer); previous.map.remove(); instances.delete(host); }
    host.replaceChildren();
    const valid = points.filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon) &&
      p.lat >= 43.45 && p.lat <= 43.95 && p.lon >= -79.8 && p.lon <= -79);
    if (!valid.length) {
      host.append(node('p', 'No valid Toronto locations in this selection. See the station table for observations.'));
      return;
    }
    const notice = node('p');
    notice.className = 'map-status';
    notice.setAttribute('role', 'status');
    const privacy = node('p', 'Street tiles: OpenStreetMap. Your browser contacts external map/CDN services, which receive your IP and viewed map area. Internet required; no routing or dock reservation.');
    privacy.className = 'map-privacy';
    if (!window.L) {
      notice.textContent = 'Street map could not load. Check your connection and reload. Station locations remain available below.';
      const list = node('div'); list.className = 'map-fallback';
      for (const point of valid) {
        const row = node('p', `${point.label} · ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)} `);
        row.append(locationLink(point));
        if(point.action) {
          const filter = node('button', 'Filter dashboard to this station');
          filter.type = 'button'; filter.onclick = point.action; row.append(filter);
        }
        list.append(row);
      }
      host.append(notice, list, privacy);
      return;
    }
    const toolbar = node('div'); toolbar.className = 'map-toolbar';
    const fit = node('button', 'Show all locations'); fit.type = 'button';
    toolbar.append(fit, node('span', 'Drag to pan · use +/− to zoom · select a station for details'));
    const surface = node('div'); surface.className = 'street-map';
    surface.setAttribute('aria-label', 'Toronto street map with station locations');
    host.append(toolbar, surface, notice, privacy);
    const map = L.map(surface, {scrollWheelZoom: false});
    const showAll = () => map.fitBounds(valid.map(p => [p.lat, p.lon]), {padding: [35, 35], maxZoom: 16});
    showAll(); // Set the initial view before adding layers; Leaflet creates their DOM on load.
    const state = {map, timer: null}; instances.set(host, state);
    let failures = 0;
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
    });
    notice.textContent = 'Loading street map…';
    tiles.on('loading', () => {
      failures = 0;
      clearTimeout(state.timer);
      state.timer = setTimeout(() => {
        notice.textContent = 'Street tiles are taking too long to load. Markers alone are not a street map; use station location links or reload.';
      }, 12000);
    });
    tiles.on('tileerror', () => {
      failures++;
      notice.textContent = 'Some street tiles could not load. Markers may lack street context. Use station location links or reload.';
    });
    tiles.on('load', () => {
      clearTimeout(state.timer);
      if (!failures) notice.textContent = 'Street map loaded. Station values reflect the selected data, not guaranteed availability at arrival.';
    });
    tiles.addTo(map);
    for (const point of valid) {
      const marker = point.badge
        ? L.marker([point.lat, point.lon], {title: point.label, alt: point.label,
          icon: L.divIcon({className: 'dock-map-badge', html: '', iconSize: [30, 30]})})
        : L.circleMarker([point.lat, point.lon], {radius: point.radius || 6,
          fillColor: point.color || '#24776a', color: '#fff', weight: 1.5, fillOpacity: 0.85});
      marker.addTo(map);
      const element = marker.getElement();
      if (point.badge) element.textContent = point.badge;
      element.setAttribute('tabindex', '0');
      element.setAttribute('role', 'button');
      element.setAttribute('aria-label', point.label);
      const popup = node('div');
      popup.append(node('strong', point.label), node('p', `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`), locationLink(point));
      if (point.action) {
        const select = node('button', 'Filter dashboard to this station');
        select.type = 'button'; select.onclick = point.action; popup.append(select);
      }
      marker.bindPopup(popup);
      marker.on('click', () => onInspect?.(point.label));
      marker.on('mouseover', () => onInspect?.(point.label));
      element.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault(); marker.openPopup(); onInspect?.(point.label);
        }
      });
    }
    fit.onclick = showAll;
    map.invalidateSize(); showAll();
  }
  function render(host, points, onInspect) {
    try { renderMap(host, points, onInspect); }
    catch {
      const previous = instances.get(host);
      if(previous) {
        clearTimeout(previous.timer);
        try { previous.map.remove(); } catch { /* Keep the data UI usable. */ }
        instances.delete(host);
      }
      host.replaceChildren(node('p', 'Map unavailable. The station data and results are still usable. Reload to retry the map.'));
      const list = node('div'); list.className = 'map-fallback';
      for(const point of points) {
        if(!Number.isFinite(point.lat)||!Number.isFinite(point.lon)||point.lat<43.45||point.lat>43.95||point.lon< -79.8||point.lon> -79)continue;
        const row = node('p', `${point.label} · ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)} `);
        row.append(locationLink(point));
        if(point.action) {
          const filter = node('button', 'Filter dashboard to this station');
          filter.type = 'button'; filter.onclick = point.action; row.append(filter);
        }
        list.append(row);
      }
      host.append(list);
    }
  }
  return {render, locationLink};
})();
