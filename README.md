# Flight Map

This project provides a minimal example of an interactive airline route map for Europe.

The server uses **FastAPI** to serve the static files from the `public` directory. The front-end relies on Leaflet to display airports and draw routes when an airport marker is clicked. Airport markers are rendered as circles whose radius scales between 8 and 35&nbsp;px depending on how many outgoing routes they have.

Clicking an airport toggles the display of its routes. Clicking a route highlights
it for selection; clicking again unselects it. Selected routes are shown in the
"Path" panel at the top of the page so you can build an ordered itinerary of
`Airport -> Airline -> Airport`.

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

`public/airports.json` contains example data with a small set of airports and routes. When running the container with a volume mounted at `$DATA_DIR`, updated data will be written there. The dataset is fetched from OurAirports (for airport details) and OpenFlights (for routes).

### Updating data

Run the `/update-airports` endpoint to download the latest airports from OurAirports and route information from OpenFlights:

```bash
curl -X POST http://localhost:8000/update-airports
```

This downloads `airports.csv` from OurAirports and `routes.dat` from OpenFlights, generating `$DATA_DIR/airports.json` with routes embedded for use by the front-end. Airports that have no outgoing routes are excluded from the resulting file.

## Deployment on Railway

Create a project from this repository and configure a persistent volume mounted at `/data`. Set the `DATA_DIR` environment variable to `/data` so updated airport data persists between deployments.
