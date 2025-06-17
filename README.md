# Flight Map

This project provides a minimal example of an interactive airline route map for Europe.

The server uses **FastAPI** to serve the static files from the `public` directory. The front-end relies on Leaflet to display airports and draw routes when an airport marker is clicked. Airport markers are rendered as circles whose radius scales between 8 and 35&nbsp;px depending on how many outgoing routes they have. When an airline filter is active the sizing is recalculated using only the routes for that carrier.

Click an airport to toggle the display of its routes. Hovering over a marker or
route shows a tooltip with details. Clicking a route highlights it for
selection; clicking again unselects it. Selected routes are shown in the
"Path" panel so you can build an ordered itinerary of
`Airport -> Airline -> Airport`. Use the **Airline** dropdown to show only
airports served by a particular carrier. A **Reset Airline** button beside the
dropdown clears that filter. You can also filter airports by **Country** using
the new country dropdown and **Clear Country** button. When a filter is active,
clicking an airport displays only its routes for the chosen airline and marker
sizes update to reflect only those routes. Once a route is selected, a **Reset Path** button
appears next to the path display so you can clear the itinerary with a single
click.
Routes flown by different airlines use unique colors so overlapping carriers are
easy to distinguish on the map.

## Development

Install dependencies and start the server:

```bash
pip install -r requirements.txt
uvicorn server:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## Docker

To build and run the image with a persistent data volume you can use Docker
Compose:

```bash
docker compose up --build
```

This mounts the local `./data` directory at `/data` inside the container so
updated datasets persist between runs. You can still build and run the image
manually if desired:

```bash
docker build -t flight_map .
docker run -p 8000:8000 -v $(pwd)/data:/data -e DATA_DIR=/data flight_map
```

### Running tests

Unit tests verify data updates. Execute them inside the container:

```bash
docker run --rm flight_map pytest
```

## Data

`public/airports.json` contains example data with a small set of airports and routes. Each airport entry lists its code, ISO country and human readable country name so the front-end can provide tooltips and filtering. When running the container with a volume mounted at `$DATA_DIR`, updated data will be written there. The dataset is fetched from OurAirports for airport and country details while route information comes from the flights collected via `/update-flights`.

### Updating data

Run the `/update-airports` endpoint to download the latest airports from OurAirports and merge them with your collected flight database (`routes_dynamic.json`):

```bash
curl -X POST http://localhost:8000/update-airports
```

This downloads `airports.csv` and `countries.csv` from OurAirports and combines them with the data in `routes_dynamic.json`, generating `$DATA_DIR/airports.json` with country names embedded for use by the front-end. Airports that have no outgoing routes are excluded from the resulting file.

### Updating live flight data

Use `/update-flights` to gather active flights from the OpenSky API. Flights are tracked until they disappear from the feed, at which point a route entry is stored in `$DATA_DIR/routes_dynamic.json`:

```json
[
  {
    "airline": "BT",
    "flight_number": "123",
    "icao24": "4ca77d",
    "source": "EVRA",
    "destination": "EGLL",
    "first_seen": "2025-06-10T13:45:00Z",
    "last_seen": "2025-06-16T10:45:00Z",
    "status": "Active"
  }
]
```

Statistics about the collection are written to `$DATA_DIR/routes_stats.json` and can be retrieved via `/routes-stats`.

```bash
curl -X POST http://localhost:8000/update-flights
```

The current dataset can be downloaded with:

```bash
curl http://localhost:8000/routes-db
```

## Deployment on Railway

Create a project from this repository and configure a persistent volume mounted at `/data`. Set the `DATA_DIR` environment variable to `/data` so updated airport data persists between deployments.
