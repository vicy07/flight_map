const map = L.map('map').setView([51.505, -0.09], 4);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

const pathEl = document.getElementById('path');
const filterSelect = document.getElementById('airline-filter');
const resetBtn = document.getElementById('reset');
const selectedRoutes = [];
const routesPane = map.createPane('routes');
routesPane.style.zIndex = 200;
const markers = [];

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
}

function applyFilter() {
  const airline = filterSelect.value;
  markers.forEach(m => {
    const hasAirline = !airline || m.airport.routes.some(r => r.airline === airline);
    if (hasAirline) {
      if (!map.hasLayer(m.marker)) {
        m.marker.addTo(map);
      }
    } else {
      if (map.hasLayer(m.marker)) {
        m.marker.routesLines.forEach(l => map.removeLayer(l));
        m.marker.routesLines = [];
        map.removeLayer(m.marker);
      }
    }
  });
  selectedRoutes.length = 0;
  updatePathDisplay();
}

function toggleRouteSelection(line, route) {
  if (line.selected) {
    line.setStyle({ color: 'blue' });
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

filterSelect.addEventListener('change', applyFilter);
resetBtn.addEventListener('click', () => {
  markers.forEach(m => {
    m.marker.routesLines.forEach(l => map.removeLayer(l));
    m.marker.routesLines = [];
  });
  selectedRoutes.length = 0;
  updatePathDisplay();
});

fetch('airports.json')
  .then(r => r.json())
  .then(data => {
    data = data.filter(a => a.routes && a.routes.length);
    const maxRoutes = Math.max(...data.map(a => a.routes.length));
    const minRadius = 8; // min radius 8px
    const maxRadius = 35; // max radius 35px

    const airlinesSet = new Set();

    data.forEach(a => {
      a.routes.forEach(r => airlinesSet.add(r.airline));
      const radius = minRadius +
        (a.routes.length / maxRoutes) * (maxRadius - minRadius);

      const marker = L.circleMarker([a.lat, a.lon], {
        radius,
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
            const line = L.polyline(
              [route.from, route.to],
              { color: 'blue', pane: 'routes' }
            )
              .addTo(map)
              .bindTooltip(`${route.from_name} - ${route.airline} - ${route.to_name}`);
            line.route = route;
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

    applyFilter();
  });
