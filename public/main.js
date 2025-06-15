const map = L.map('map').setView([51.505, -0.09], 4);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

fetch('airports.json')
  .then(r => r.json())
  .then(data => {
    data.forEach(a => {
      const marker = L.marker([a.lat, a.lon]).addTo(map).bindPopup(a.name);
      marker.on('click', () => {
        // highlight routes from this airport
        if (a.routes) {
          a.routes.forEach(route => {
            const line = L.polyline([route.from, route.to], {color: 'blue'}).addTo(map);
          });
        }
      });
    });
  });
