const map = L.map('map').setView([51.505, -0.09], 4);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

const pathEl = document.getElementById('path');
const selectedRoutes = [];
const routesPane = map.createPane('routes');
routesPane.style.zIndex = 200;

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

fetch('airports.json')
  .then(r => r.json())
  .then(data => {
    data = data.filter(a => a.routes && a.routes.length);
    const maxRoutes = Math.max(...data.map(a => a.routes.length));
    const minRadius = 1.5; // diameter 3
    const maxRadius = 7.5; // diameter 15

    data.forEach(a => {
      const radius = minRadius +
        (a.routes.length / maxRoutes) * (maxRadius - minRadius);

      const marker = L.circleMarker([a.lat, a.lon], {
        radius,
        color: 'black',
        weight: 1,
        fillColor: '#3388ff',
        fillOpacity: 1,
      }).addTo(map).bindPopup(a.name);
      marker.routesLines = [];
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
          a.routes.forEach(route => {
            const line = L.polyline(
              [route.from, route.to],
              { color: 'blue', pane: 'routes' }
            ).addTo(map);
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
  });
