from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import csv
import json
from pathlib import Path
import requests

DATA_DIR = Path(os.environ.get("DATA_DIR", "public"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
AIRPORTS_PATH = DATA_DIR / "airports.json"

app = FastAPI()


@app.get("/airports.json")
def get_airports():
    """Return the stored airports dataset."""
    return FileResponse(AIRPORTS_PATH)


@app.post("/update-airports")
def update_airports():
    """Download airport data from OurAirports and route data from OpenFlights."""

    airports_url = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/master/airports.csv"
    countries_url = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/master/countries.csv"
    routes_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat"
    airlines_url = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

    # Download airports from OurAirports
    resp = requests.get(airports_url)
    resp.raise_for_status()
    reader = csv.DictReader(resp.text.splitlines())
    airports = {}

    # Download countries to resolve ISO codes to readable names
    resp_countries = requests.get(countries_url)
    resp_countries.raise_for_status()
    country_map = {r["code"]: r["name"] for r in csv.DictReader(resp_countries.text.splitlines())}
    for row in reader:
        try:
            iata = row.get("iata_code")
            icao = row.get("icao_code")
            if not iata and not icao:
                continue
            key = iata or icao
            name = row["name"]
            lat = float(row["latitude_deg"])
            lon = float(row["longitude_deg"])
        except (ValueError, KeyError):
            continue
        country_code = row.get("iso_country", "")
        airports[key] = {
            "name": name,
            "code": key,
            "lat": lat,
            "lon": lon,

            "country_code": country_code,
            "country": country_map.get(country_code, country_code),
            "routes": []
        }

    # Build a mapping of airline codes to human readable names
    resp = requests.get(airlines_url)
    resp.raise_for_status()
    airline_names = {}
    reader = csv.reader(resp.text.splitlines())
    for row in reader:
        try:
            name = row[1]
            iata = row[3]
            icao = row[4]
        except IndexError:
            continue
        if iata and iata != "\\N":
            airline_names[iata] = name
        if icao and icao != "\\N":
            airline_names[icao] = name

    # Download routes and attach to airports
    resp = requests.get(routes_url)
    resp.raise_for_status()
    reader = csv.reader(resp.text.splitlines())
    route_count = 0
    for row in reader:
        try:
            airline_code = row[0]
            source_code = row[2]
            dest_code = row[4]
            if source_code == "\\N" or dest_code == "\\N":
                continue
            source = airports.get(source_code)
            dest = airports.get(dest_code)
            if not source or not dest:
                continue
        except IndexError:
            continue
        source["routes"].append({
            "from": [source["lat"], source["lon"]],
            "to": [dest["lat"], dest["lon"]],
            "from_name": source["name"],
            "to_name": dest["name"],
            "airline": airline_names.get(airline_code, airline_code)
        })
        route_count += 1

    # Keep only airports that actually have outgoing routes
    airports_with_routes = [a for a in airports.values() if a["routes"]]

    AIRPORTS_PATH.write_text(
        json.dumps(airports_with_routes, indent=2)
    )

    return {"airports": len(airports_with_routes), "routes": route_count}

# Serve static files from the public directory (mounted last so API routes take precedence)
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
