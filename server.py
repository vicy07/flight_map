from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import csv
import json
from pathlib import Path
from datetime import datetime
from math import radians, cos, sin, asin, sqrt
import re
import requests

DATA_DIR = Path(os.environ.get("DATA_DIR", "public"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
AIRPORTS_PATH = DATA_DIR / "airports.json"
ROUTES_DB_PATH = DATA_DIR / "routes_dynamic.json"
STATS_PATH = DATA_DIR / "routes_stats.json"
AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

app = FastAPI()


CALLSIGN_RE = re.compile(r"^([A-Za-z]{2,3})")


def parse_callsign(callsign: str):
    """Return (prefix, number) from a callsign string."""
    cs = (callsign or "").strip()
    if not cs:
        return "", ""
    m = CALLSIGN_RE.match(cs)
    if m:
        prefix = m.group(1).upper()
        number = cs[m.end():].strip()
        return prefix, number
    return "", cs


@app.get("/airports.json")
def get_airports():
    """Return the stored airports dataset."""
    return FileResponse(AIRPORTS_PATH)


@app.post("/update-airports")
def update_airports():
    """Download airport data from OurAirports and build routes from collected flights."""

    airports_url = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/master/airports.csv"
    countries_url = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/master/countries.csv"

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

    # Load collected flight data and map to nearest airports
    flights = []
    if ROUTES_DB_PATH.exists():
        try:
            flights = json.loads(ROUTES_DB_PATH.read_text() or "[]")
        except json.JSONDecodeError:
            flights = []

    # Build a mapping of airline codes to human readable names
    resp_airlines = requests.get(AIRLINES_URL)
    resp_airlines.raise_for_status()
    airline_names = {}
    for row in csv.reader(resp_airlines.text.splitlines()):
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

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return R * c

    def nearest_airport(lat, lon):
        if lat is None or lon is None:
            return None
        best = None
        best_d = float("inf")
        for ap in airports.values():
            d = haversine(lat, lon, ap["lat"], ap["lon"])
            if d < best_d:
                best = ap
                best_d = d
        return best if best_d <= 30 else None

    route_count = 0
    for fl in flights:
        src = nearest_airport(*fl.get("origin_coord", (None, None)))
        dest = nearest_airport(*fl.get("last_coord", (None, None)))
        if not src or not dest:
            continue
        prefix = fl.get("airline")
        number = fl.get("flight_number")
        if not prefix:
            prefix, number = parse_callsign(fl.get("callsign", ""))
        airline_name = airline_names.get(prefix, prefix)
        src["routes"].append({
            "from": [src["lat"], src["lon"]],
            "to": [dest["lat"], dest["lon"]],
            "from_name": src["name"],
            "to_name": dest["name"],
            "airline": airline_name,
            "flight_number": number
        })
        route_count += 1

    # Keep only airports that actually have outgoing routes
    airports_with_routes = [a for a in airports.values() if a["routes"]]

    AIRPORTS_PATH.write_text(
        json.dumps(airports_with_routes, indent=2)
    )

    return {"airports": len(airports_with_routes), "routes": route_count}


@app.post("/update-flights")
def update_flights():
    """Fetch active flights from OpenSky and store simplified data."""
    resp = requests.get("https://opensky-network.org/api/states/all")
    resp.raise_for_status()
    data = resp.json()

    now = datetime.utcnow().isoformat() + "Z"

    flights = {}
    if ROUTES_DB_PATH.exists():
        try:
            for f in json.loads(ROUTES_DB_PATH.read_text() or "[]"):
                flights[f["icao24"]] = f
        except json.JSONDecodeError:
            pass

    for s in data.get("states", []):
        icao24 = s[0]
        callsign = s[1].strip() if s[1] else ""
        lon = s[5]
        lat = s[6]
        if icao24 in flights:
            flights[icao24]["last_coord"] = [lat, lon]
            flights[icao24]["last_updated"] = now
            flights[icao24]["callsign"] = callsign
            prefix, number = parse_callsign(callsign)
            flights[icao24]["airline"] = prefix
            flights[icao24]["flight_number"] = number
        else:
            prefix, number = parse_callsign(callsign)
            flights[icao24] = {
                "icao24": icao24,
                "callsign": callsign,
                "airline": prefix,
                "flight_number": number,
                "origin_coord": [lat, lon],
                "last_coord": [lat, lon],
                "first_seen": now,
                "last_updated": now,
            }

    ROUTES_DB_PATH.write_text(json.dumps(list(flights.values()), indent=2))
    STATS_PATH.write_text(json.dumps({"routes": len(flights), "last_run": now}))
    return {"routes": len(flights), "last_run": now}


@app.get("/routes-db")
def get_routes_db():
    """Return the dynamically built routes database."""
    return FileResponse(ROUTES_DB_PATH)


@app.get("/routes-stats")
def get_routes_stats():
    """Return statistics about the routes database."""
    if STATS_PATH.exists():
        return json.loads(STATS_PATH.read_text())
    return {"routes": 0, "last_run": None}

# Serve static files from the public directory (mounted last so API routes take precedence)
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
