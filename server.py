from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import re
import requests
from scipy.spatial import cKDTree

DATA_DIR = Path(os.environ.get("DATA_DIR", "public"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
AIRPORTS_PATH = DATA_DIR / "airports.json"
ROUTES_DB_PATH = DATA_DIR / "routes_dynamic.json"
ACTIVE_FLIGHTS_PATH = DATA_DIR / "active_flights.json"
STATS_PATH = DATA_DIR / "routes_stats.json"
AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"

app = FastAPI()


CALLSIGN_RE = re.compile(r"^([A-Za-z]{2,3})")

# Global airport lookup structures
AIRPORTS_TREE = None
AIRPORTS_INDEX = []
AIRPORTS_MAP = {}

EARTH_RADIUS_KM = 6371.0

def _to_unit_vector(lat: float, lon: float):
    """Convert lat/lon degrees to 3D unit vector."""
    lat_r = radians(lat)
    lon_r = radians(lon)
    return [
        cos(lat_r) * cos(lon_r),
        cos(lat_r) * sin(lon_r),
        sin(lat_r),
    ]


def build_airport_tree(airports):
    """Build global KDTree from iterable of airport dicts."""
    global AIRPORTS_TREE, AIRPORTS_INDEX
    coords = []
    AIRPORTS_INDEX = []
    for ap in airports:
        coords.append(_to_unit_vector(ap["lat"], ap["lon"]))
        AIRPORTS_INDEX.append(ap["code"])
    AIRPORTS_TREE = cKDTree(coords) if coords else None


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


def haversine(lat1, lon1, lat2, lon2):
    """Return distance in km between two lat/lon points."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


def nearest_airport(lat: float, lon: float):
    """Return closest airport dict within 30km of given coordinates."""
    if lat is None or lon is None or AIRPORTS_TREE is None:
        return None
    point = _to_unit_vector(lat, lon)
    dist, idx = AIRPORTS_TREE.query(point)
    if idx >= len(AIRPORTS_INDEX):
        return None
    code = AIRPORTS_INDEX[idx]
    ap = AIRPORTS_MAP.get(code)
    if not ap:
        return None
    d = haversine(lat, lon, ap["lat"], ap["lon"])
    return ap if d <= 30 else None


@app.get("/airports.json")
def get_airports():
    """Return the stored airports dataset if available."""
    if AIRPORTS_PATH.exists():
        return FileResponse(AIRPORTS_PATH)
    raise HTTPException(status_code=404, detail="airports data not found")


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

    # Load collected route data
    routes = []
    if ROUTES_DB_PATH.exists():
        try:
            routes = json.loads(ROUTES_DB_PATH.read_text() or "[]")
        except json.JSONDecodeError:
            routes = []

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


    route_count = 0
    for rt in routes:
        src = airports.get(rt.get("source"))
        dest = airports.get(rt.get("destination"))
        if not src or not dest:
            continue
        prefix = rt.get("airline", "")
        number = rt.get("flight_number", "")
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

    # Keep only airports that actually have outgoing routes. If no routes have
    # been collected yet, preserve all airports so that update_flights can
    # match future flights to the nearest airport.
    airports_with_routes = [a for a in airports.values() if a["routes"]]
    if not airports_with_routes:
        airports_with_routes = list(airports.values())

    AIRPORTS_PATH.write_text(json.dumps(airports_with_routes, indent=2))

    # Build lookup structures for nearest airport queries
    global AIRPORTS_MAP
    AIRPORTS_MAP = {a["code"]: a for a in airports_with_routes}
    build_airport_tree(airports_with_routes)

    # Update stats file with airport counts
    stats = {}
    if STATS_PATH.exists():
        try:
            stats = json.loads(STATS_PATH.read_text() or "{}")
        except json.JSONDecodeError:
            stats = {}
    stats["airports_active"] = len(airports_with_routes)
    stats["airports_total"] = len(airports)
    STATS_PATH.write_text(json.dumps(stats, indent=2))

    return {"airports": len(airports_with_routes), "routes": route_count}


@app.post("/update-flights")
def update_flights():
    """Fetch active flights from OpenSky and update route database."""
    resp = requests.get("https://opensky-network.org/api/states/all")
    resp.raise_for_status()
    data = resp.json()

    now = datetime.utcnow().isoformat() + "Z"

    # Load current active flights
    active = {}
    if ACTIVE_FLIGHTS_PATH.exists():
        try:
            active = json.loads(ACTIVE_FLIGHTS_PATH.read_text() or "{}")
        except json.JSONDecodeError:
            active = {}

    # Load existing routes
    routes = []
    if ROUTES_DB_PATH.exists():
        try:
            routes = json.loads(ROUTES_DB_PATH.read_text() or "[]")
        except json.JSONDecodeError:
            routes = []
    routes_by_key = {
        (r.get("airline"), r.get("flight_number"), r.get("source"), r.get("destination")): r
        for r in routes
    }

    # Load airports for geolocation
    airports = {}
    if AIRPORTS_PATH.exists():
        try:
            a_list = json.loads(AIRPORTS_PATH.read_text() or "[]")
            airports = {a["code"]: a for a in a_list}
        except json.JSONDecodeError:
            airports = {}
    global AIRPORTS_MAP
    AIRPORTS_MAP = airports
    if AIRPORTS_MAP and AIRPORTS_TREE is None:
        build_airport_tree(AIRPORTS_MAP.values())

    seen = set()
    for s in data.get("states", []):
        icao24 = s[0]
        callsign = s[1].strip() if s[1] else ""
        lon = s[5]
        lat = s[6]
        if lat is None or lon is None:
            continue
        seen.add(icao24)
        prefix, number = parse_callsign(callsign)
        if icao24 in active:
            af = active[icao24]
            af["last_coord"] = [lat, lon]
            af["last_updated"] = now
            af["callsign"] = callsign
            af["airline"] = prefix
            af["flight_number"] = number
        else:
            origin_ap = nearest_airport(lat, lon)
            active[icao24] = {
                "callsign": callsign,
                "airline": prefix,
                "flight_number": number,
                "origin": origin_ap["code"] if origin_ap else None,
                "origin_name": origin_ap["name"] if origin_ap else None,
                "origin_coord": [lat, lon],
                "last_coord": [lat, lon],
                "first_seen": now,
                "last_updated": now,
            }

    # Handle flights that disappeared since last run
    finished = [key for key in active.keys() if key not in seen]
    for icao24 in finished:
        af = active.pop(icao24)
        prefix, number = parse_callsign(af.get("callsign", ""))
        src = nearest_airport(*(af.get("origin_coord") or (None, None)))
        dest = nearest_airport(*(af.get("last_coord") or (None, None)))
        if not src or not dest or src["code"] == dest["code"]:
            continue
        key = (prefix, number, src["code"], dest["code"])
        route = routes_by_key.get(key)
        if route:
            route["last_seen"] = now
            route["icao24"] = icao24
        else:
            route = {
                "airline": prefix,
                "flight_number": number,
                "icao24": icao24,
                "source": src["code"],
                "destination": dest["code"],
                "first_seen": now,
                "last_seen": now,
                "status": "Active",
            }
            routes.append(route)
            routes_by_key[key] = route

    # Update status and prune old routes
    cleaned = []
    now_dt = datetime.utcnow()
    for r in routes:
        try:
            last_dt = datetime.fromisoformat(r["last_seen"].replace("Z", ""))
        except Exception:
            last_dt = now_dt
        if now_dt - last_dt > timedelta(days=365):
            continue
        r["status"] = "Active" if now_dt - last_dt <= timedelta(days=21) else "Not Active"
        cleaned.append(r)
    routes = cleaned

    ACTIVE_FLIGHTS_PATH.write_text(json.dumps(active, indent=2))
    ROUTES_DB_PATH.write_text(json.dumps(routes, indent=2))

    stats = {}
    if STATS_PATH.exists():
        try:
            stats = json.loads(STATS_PATH.read_text() or "{}")
        except json.JSONDecodeError:
            stats = {}
    stats.update({
        "routes": len(routes),
        "last_run": now,
        "active_planes": len(active),
    })
    STATS_PATH.write_text(json.dumps(stats, indent=2))
    return {"routes": len(routes), "active": len(active), "last_run": now}


@app.get("/active-flights")
def get_active_flights():
    """Return the currently tracked active flights."""
    if ACTIVE_FLIGHTS_PATH.exists():
        return FileResponse(ACTIVE_FLIGHTS_PATH)
    return {}


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


@app.get("/routes-info")
def get_routes_info():
    """Return summary statistics about airports and routes."""
    stats = {}
    if STATS_PATH.exists():
        try:
            stats = json.loads(STATS_PATH.read_text() or "{}")
        except json.JSONDecodeError:
            stats = {}

    routes = []
    if ROUTES_DB_PATH.exists():
        try:
            routes = json.loads(ROUTES_DB_PATH.read_text() or "[]")
        except json.JSONDecodeError:
            routes = []

    airports_list = []
    if AIRPORTS_PATH.exists():
        try:
            airports_list = json.loads(AIRPORTS_PATH.read_text() or "[]")
        except json.JSONDecodeError:
            airports_list = []

    now = datetime.utcnow()
    recovered_hour = 0
    recovered_day = 0
    for rt in routes:
        try:
            last = datetime.fromisoformat(rt.get("last_seen", "").replace("Z", ""))
        except Exception:
            continue
        if now - last <= timedelta(hours=1):
            recovered_hour += 1
        if now - last <= timedelta(hours=24):
            recovered_day += 1

    return {
        "active_airports": len(airports_list),
        "total_airports": stats.get("airports_total", len(airports_list)),
        "routes": len(routes),
        "last_update": stats.get("last_run"),
        "active_planes": stats.get("active_planes", 0),
        "recovered_last_hour": recovered_hour,
        "recovered_last_24h": recovered_day,
    }

# Serve static files from the public directory (mounted last so API routes take precedence)
app.mount("/", StaticFiles(directory="public", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
