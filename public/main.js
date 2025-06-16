const map = L.map('map').setView([51.505, -0.09], 4);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

const selectedRoutes = [];

function toggleRouteSelection(line, route) {
  if (line.selected) {
    line.setStyle({ color: 'blue' });
    line.selected = false;
    const idx = selectedRoutes.findIndex(r => r === route);
    if (idx !== -1) selectedRoutes.splice(idx, 1);
  } else {
    line.setStyle({ color: 'red' });
    line.selected = true;
    selectedRoutes.push(route);
  }
  console.log('Selected routes', selectedRoutes);
}

fetch('airports.json')
  .then(r => r.json())
  .then(data => {
    data.forEach(a => {
      const marker = L.marker([a.lat, a.lon]).addTo(map).bindPopup(a.name);
      marker.routesLines = [];
      marker.on('click', () => {
        if (marker.routesLines.length) {
          marker.routesLines.forEach(l => map.removeLayer(l));
          marker.routesLines = [];
        } else if (a.routes) {
          a.routes.forEach(route => {
            const line = L.polyline([route.from, route.to], { color: 'blue' }).addTo(map);
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
