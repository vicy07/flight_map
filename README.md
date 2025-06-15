# Flight Map

This project provides a minimal example of an interactive airline route map for Europe.

The server uses **FastAPI** to serve the static files from the `public` directory. The front-end relies on Leaflet to display airports and draw sample routes when an airport marker is clicked.

## Development

Install dependencies and start the server:

```bash
pip install -r requirements.txt
uvicorn server:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## Docker

To build and run the image:

```bash
docker build -t flight_map .
docker run -p 8000:8000 flight_map
```

## Data

`public/airports.json` contains example data with a small set of airports and routes. Replace this file with data from sources like OpenFlights for real usage.
