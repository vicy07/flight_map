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
const selectedRoutes = [];
const routesPane = map.createPane('routes');
routesPane.style.zIndex = 200;
const markers = [];
const activeFlightMarkers = [];
const minRadius = 8;
const maxRadius = 35;
const airlineColors = {};
const colorPalette = [
  '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
  '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff',
  '#9A6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1',
  '#000075', '#808080'
];

const planeIcon = L.icon({
  iconUrl: 'plane.svg',
  iconSize: [4, 4],
  iconAnchor: [2, 2],
});

function parseCallsign(cs) {
  cs = (cs || '').trim();
  if (!cs) return ['', ''];
  const m = cs.match(/^([A-Za-z]{2,3})(.*)$/);
  if (m) return [m[1].toUpperCase(), m[2].trim()];
  return ['', cs];
}

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
  fetch('active-flights')
    .then(r => r.json())
    .then(data => {
      activeFlightMarkers.forEach(m => map.removeLayer(m));
      activeFlightMarkers.length = 0;
      Object.values(data || {}).forEach(f => {
        if (!Array.isArray(f.last_coord)) return;
        const [lat, lon] = f.last_coord;
        if (lat == null || lon == null) return;
        const [, number] = parseCallsign(f.callsign);
        const marker = L.marker([lat, lon], { icon: planeIcon })
          .addTo(map)
          .bindTooltip(number || f.callsign || '');
        activeFlightMarkers.push(marker);
      });
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
      a.routes.forEach(r => airlinesSet.add(r.airline));
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
    loadActiveFlights();
  });
