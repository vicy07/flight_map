from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import csv
import json
from pathlib import Path
import requests

app = FastAPI()


@app.post("/update-airports")
def update_airports():
    """Download airport and route data from OpenFlights and update JSON files."""

    airports_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
    routes_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"

    # Download airports
    resp = requests.get(airports_url)
    resp.raise_for_status()
    reader = csv.reader(resp.text.splitlines())
    airports = {}
    for row in reader:
        try:
            airport_id = row[0]
            name = row[1]
            lat = float(row[6])
            lon = float(row[7])
        except (ValueError, IndexError):
            continue
        airports[airport_id] = {
            "name": name,
            "lat": lat,
            "lon": lon,
            "routes": []
        }

    # Download routes and attach to airports
    resp = requests.get(routes_url)
    resp.raise_for_status()
    reader = csv.reader(resp.text.splitlines())
    route_count = 0
    for row in reader:
        try:
            airline = row[0]
            source_id = row[3]
            dest_id = row[5]
            if source_id == "\\N" or dest_id == "\\N":
                continue
            source = airports.get(source_id)
            dest = airports.get(dest_id)
            if not source or not dest:
                continue
        except IndexError:
            continue
        source["routes"].append({
            "from": [source["lat"], source["lon"]],
            "to": [dest["lat"], dest["lon"]],
            "from_name": source["name"],
            "to_name": dest["name"],
            "airline": airline
        })
        route_count += 1

    # Keep only airports that actually have outgoing routes
    airports_with_routes = [a for a in airports.values() if a["routes"]]

    Path("public/airports.json").write_text(
        json.dumps(airports_with_routes, indent=2)
    )

    return {"airports": len(airports_with_routes), "routes": route_count}

# Serve static files from the public directory (mounted last so API routes take precedence)
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
