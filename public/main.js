const map = L.map('map').setView([51.505, -0.09], 4);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

const pathEl = document.getElementById('path');
const filterSelect = document.getElementById('airline-filter');
const resetBtn = document.getElementById('reset');
const resetAirlineBtn = document.getElementById('reset-airline');
const countrySelect = document.getElementById('country-filter');
const resetCountryBtn = document.getElementById('reset-country');
const planeToggle = document.getElementById('plane-toggle');
const selectedRoutes = [];
const routesPane = map.createPane('routes');
routesPane.style.zIndex = 200;
const markers = [];
const activeFlightMarkers = new Map();
const activeFlightsLayer = L.layerGroup();
let planeIntervalId = null;
const minRadius = 8;
const maxRadius = 35;
const airlineColors = {};
const colorPalette = [
  '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
  '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff',
  '#9A6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1',
  '#000075', '#808080'
];

const airlineNameToCode = {};

const planeIcon = L.icon({
  iconUrl: 'plane.svg',
  iconSize: [8, 8],
  iconAnchor: [4, 4],
});

const statsEl = document.getElementById('stats');
let infoStats = {};

function getAirlineColor(code) {
  if (!airlineColors[code]) {
    const idx = Object.keys(airlineColors).length % colorPalette.length;
    airlineColors[code] = colorPalette[idx];
  }
  return airlineColors[code];
}
let airportsData = [];

function updatePathDisplay() {
  const parts = [];
  selectedRoutes.forEach((item, idx) => {
    if (idx === 0) {
      parts.push(item.route.from_name);
    }
    parts.push(item.route.airline);
    parts.push(item.route.to_name);
  });
  pathEl.textContent = parts.join(' => ');
  resetBtn.style.display = selectedRoutes.length ? 'inline' : 'none';
}

function updateStatsDisplay() {
  const visibleAirports = markers.filter(m => map.hasLayer(m.marker)).length;
  const totalAirports = infoStats.active_airports || airportsData.length || 0;
  const visiblePlanes = planeToggle.checked ? activeFlightMarkers.size : 0;
  const totalPlanes = infoStats.active_planes || 0;
  const routes = infoStats.routes || 0;
  const recent = infoStats.recovered_last_hour || 0;
  statsEl.textContent = `Airports: ${visibleAirports}/${totalAirports} | ` +
    `Planes: ${visiblePlanes}/${totalPlanes} | ` +
    `Routes: ${routes} (last hr: ${recent})`;
}

function applyFilter() {
  const airline = filterSelect.value;
  const country = countrySelect.value;
  const counts = [];
  let maxRoutes = 0;
  markers.forEach(m => {
    const inCountry = !country || m.airport.country_code === country;
    const count = inCountry ?
      m.airport.routes.filter(r => !airline || r.airline === airline).length : 0;
    counts.push(count);
    if (count > maxRoutes) maxRoutes = count;
  });
  if (maxRoutes === 0) maxRoutes = 1;

  markers.forEach((mObj, idx) => {
    const m = mObj.marker;
    const count = counts[idx];
    const show = count > 0;
    const radius = minRadius + (count / maxRoutes) * (maxRadius - minRadius);
    m.setRadius(radius);

    if (show) {
      if (!map.hasLayer(m)) {
        m.addTo(map);
      }
    } else {
      if (map.hasLayer(m)) {
        m.routesLines.forEach(l => map.removeLayer(l));
        m.routesLines = [];
        map.removeLayer(m);
      }
    }
  });

  selectedRoutes.length = 0;
  updatePathDisplay();
  if (planeToggle.checked) {
    if (!map.hasLayer(activeFlightsLayer)) {
      activeFlightsLayer.addTo(map);
    }
    loadActiveFlights();
  }
  updateStatsDisplay();
}

function toggleRouteSelection(line, route) {
  if (line.selected) {
    line.setStyle({ color: line.originalColor });
    line.selected = false;
    const idx = selectedRoutes.findIndex(r => r.route === route);
    if (idx !== -1) selectedRoutes.splice(idx, 1);
  } else {
    line.setStyle({ color: 'red' });
    line.selected = true;
  selectedRoutes.push({ line, route });
  }
  updatePathDisplay();
}

function loadActiveFlights() {
  fetch('active-planes')
    .then(r => r.json())
    .then(data => {
      const seen = new Set();
      const airlineFilter = filterSelect.value;
      const filterCode = airlineNameToCode[airlineFilter] || airlineFilter;
      Object.entries(data || {}).forEach(([icao24, f]) => {
        if (airlineFilter && f.airline !== filterCode) return;
        if (!Array.isArray(f.last_coord)) return;
        const [lat, lon] = f.last_coord;
        if (lat == null || lon == null) return;
        const code = (f.callsign || '').trim() || `${f.airline || ''}${f.flight_number || ''}`;
        let duration = '';
        if (f.first_seen && f.last_updated) {
          const first = Date.parse(f.first_seen);
          const last = Date.parse(f.last_updated);
          if (!isNaN(first) && !isNaN(last) && last >= first) {
            const mins = Math.floor((last - first) / 60000);
            const h = Math.floor(mins / 60);
            const m = mins % 60;
            duration = h ? `${h}h ${m}m` : `${m}m`;
          }
        }
        const info = [code, f.airline, duration, f.origin_name || f.origin]
          .filter(Boolean)
          .join(', ');
        seen.add(icao24);
        if (activeFlightMarkers.has(icao24)) {
          const marker = activeFlightMarkers.get(icao24);
          marker.setLatLng([lat, lon]);
          marker.getTooltip().setContent(info);
        } else {
          const marker = L.marker([lat, lon], { icon: planeIcon })
            .addTo(activeFlightsLayer)
            .bindTooltip(info);
          activeFlightMarkers.set(icao24, marker);
        }
      });
      activeFlightMarkers.forEach((marker, key) => {
        if (!seen.has(key)) {
          activeFlightsLayer.removeLayer(marker);
          activeFlightMarkers.delete(key);
        }
      });
      updateStatsDisplay();
    });
}

filterSelect.addEventListener('change', applyFilter);
resetAirlineBtn.addEventListener('click', () => {
  filterSelect.value = '';
  applyFilter();
});
countrySelect.addEventListener('change', applyFilter);
resetCountryBtn.addEventListener('click', () => {
  countrySelect.value = '';
  applyFilter();
});
planeToggle.addEventListener('change', () => {
  if (planeToggle.checked) {
    activeFlightsLayer.addTo(map);
    loadActiveFlights();
    planeIntervalId = setInterval(loadActiveFlights, 60000);
  } else {
    if (planeIntervalId) {
      clearInterval(planeIntervalId);
      planeIntervalId = null;
    }
    activeFlightMarkers.forEach(m => activeFlightsLayer.removeLayer(m));
    activeFlightMarkers.clear();
    map.removeLayer(activeFlightsLayer);
  }
  updateStatsDisplay();
});
resetBtn.addEventListener('click', () => {
  markers.forEach(m => {
    m.marker.routesLines.forEach(l => map.removeLayer(l));
    m.marker.routesLines = [];
  });
  selectedRoutes.length = 0;
  updatePathDisplay();
});

fetch('airports.json')
  .then(r => {
    if (!r.ok) {
      console.error('Failed to load airports data:', r.status);
      return [];
    }
    return r.json();
  })
  .then(data => {
    if (!Array.isArray(data)) data = [];
    airportsData = data.filter(a => a.routes && a.routes.length);
    const airlinesSet = new Set();
    const countriesMap = new Map();

    airportsData.forEach(a => {
      a.routes.forEach(r => {
        airlinesSet.add(r.airline);
        if (r.airline && r.airline_code) {
          airlineNameToCode[r.airline] = r.airline_code;
        }
      });
      countriesMap.set(a.country_code, a.country);

      const marker = L.circleMarker([a.lat, a.lon], {
        radius: minRadius,
        color: 'black',
        weight: 1,
        fillColor: '#3388ff',
        fillOpacity: 1,
      })
        .addTo(map)
        .bindTooltip(`${a.name} (${a.code})`);
      marker.routesLines = [];
      marker.airport = a;
      markers.push({ marker, airport: a });
      marker.on('click', () => {
        if (marker.routesLines.length) {
          marker.routesLines.forEach(l => {
            map.removeLayer(l);
            const idx = selectedRoutes.findIndex(r => r.line === l);
            if (idx !== -1) selectedRoutes.splice(idx, 1);
          });
          marker.routesLines = [];
          updatePathDisplay();
        } else if (a.routes) {
          const airlineFilter = filterSelect.value;
          a.routes.forEach(route => {
            if (airlineFilter && route.airline !== airlineFilter) {
              return;
            }
          const color = getAirlineColor(route.airline);
          const line = L.polyline(
            [route.from, route.to],
            { color, pane: 'routes' }
          )
            .addTo(map)
            .bindTooltip(`${route.from_name} - ${route.airline} - ${route.to_name}`);
          line.route = route;
          line.originalColor = color;
          line.on('click', e => {
            toggleRouteSelection(line, route);
            L.DomEvent.stopPropagation(e);
          });
            marker.routesLines.push(line);
          });
        }
      });
    });

    Array.from(airlinesSet).sort().forEach(code => {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = code;
      filterSelect.appendChild(opt);
    });

    Array.from(countriesMap.entries())
      .sort((a, b) => a[1].localeCompare(b[1]))
      .forEach(([code, name]) => {
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = name;
        countrySelect.appendChild(opt);
      });

    applyFilter();
    if (planeToggle.checked) {
      activeFlightsLayer.addTo(map);
      planeIntervalId = setInterval(loadActiveFlights, 60000);
      loadActiveFlights();
    }
    fetch('info')
      .then(r => r.json())
      .then(info => {
        if (info && typeof info === 'object') infoStats = info;
        updateStatsDisplay();
      });
  });
