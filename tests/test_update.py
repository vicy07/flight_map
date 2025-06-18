import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path as SysPath
sys.path.insert(0, str(SysPath(__file__).resolve().parents[1]))
import server


def fake_response(text):
    mock = Mock()
    mock.text = text
    mock.status_code = 200
    mock.raise_for_status = lambda: None
    return mock


def test_update_airports(tmp_path, monkeypatch):
    airports_csv = (
        "id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,continent,iso_country,iso_region,municipality,scheduled_service,icao_code,iata_code,gps_code,local_code,home_link,wikipedia_link,keywords\n"
        "1,AAA,airport,AirportA,10,20,,EU,AA,AA-1,CityA,yes,,AAA,AAA,,,\n"
        "2,BBB,airport,AirportB,30,40,,EU,BB,BB-1,CityB,yes,,BBB,BBB,,,"
    )
    countries_csv = (
        "id,code,name,continent,wikipedia_link,keywords\n"
        "1,AA,Country AA,EU,,\n"
        "2,BB,Country BB,EU,,"
    )
    airlines_dat = "1,Test Airline,\\N,AL,ALN,CALL,Country,Y\n"

    def fake_get(url):
        if "airports.csv" in url:
            return fake_response(airports_csv)
        if "countries.csv" in url:
            return fake_response(countries_csv)
        if "airlines.dat" in url:
            return fake_response(airlines_dat)
        raise AssertionError(url)

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    monkeypatch.setattr(server, "AIRPORTS_FULL_PATH", data_dir / "airports_full.json")
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")

    routes = [
        {
            "airline": "AL",
            "flight_number": "123",
            "icao24": "abc",
            "source": "AAA",
            "destination": "BBB",
            "first_seen": "t",
            "last_seen": "t",
            "status": "Active",
        },
        {
            "airline": "BAD",
            "flight_number": "1",
            "icao24": "zzz",
            "source": "XXX",
            "destination": "YYY",
            "first_seen": "t",
            "last_seen": "t",
            "status": "Active",
        },
    ]
    (data_dir / "routes_dynamic.json").write_text(json.dumps(routes))

    client = TestClient(server.app)
    resp = client.post("/update-airports")
    assert resp.status_code == 200

    data = json.loads((data_dir / "airports.json").read_text())
    assert len(data) == 2
    airports = {a["code"]: a for a in data}
    a_aaa = airports["AAA"]
    a_bbb = airports["BBB"]
    assert len(a_aaa["routes"]) == 1
    assert len(a_bbb["routes"]) == 1
    assert a_aaa["routes"][0]["airline"] == "Test Airline"
    assert a_aaa["routes"][0]["flight_number"] == "123"
    assert a_bbb["routes"][0]["to_name"] == "AirportA"
    assert a_aaa["country_code"] == "AA"
    assert a_aaa["country"] == "Country AA"

    stats = json.loads((data_dir / "routes_stats.json").read_text())
    assert stats["airports_active"] == 2
    assert stats["airports_total"] == 2

    full = json.loads((data_dir / "airports_full.json").read_text())
    assert len(full) == 2

    info = TestClient(server.app).get("/info").json()
    assert info["active_airports"] == 2


def test_update_airports_no_routes(tmp_path, monkeypatch):
    """When no routes exist, all airports should be kept."""
    airports_csv = (
        "id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,continent,iso_country,iso_region,municipality,scheduled_service,icao_code,iata_code,gps_code,local_code,home_link,wikipedia_link,keywords\n"
        "1,AAA,airport,AirportA,10,20,,EU,AA,AA-1,CityA,yes,,AAA,AAA,,,\n"
        "2,BBB,airport,AirportB,30,40,,EU,BB,BB-1,CityB,yes,,BBB,BBB,,,"
    )
    countries_csv = (
        "id,code,name,continent,wikipedia_link,keywords\n"
        "1,AA,Country AA,EU,,\n"
        "2,BB,Country BB,EU,,"
    )
    airlines_dat = "1,Test Airline,\\N,AL,ALN,CALL,Country,Y\n"

    def fake_get(url):
        if "airports.csv" in url:
            return fake_response(airports_csv)
        if "countries.csv" in url:
            return fake_response(countries_csv)
        if "airlines.dat" in url:
            return fake_response(airlines_dat)
        raise AssertionError(url)

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    monkeypatch.setattr(server, "AIRPORTS_FULL_PATH", data_dir / "airports_full.json")
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")

    # No routes collected yet
    (data_dir / "routes_dynamic.json").write_text("[]")

    client = TestClient(server.app)
    resp = client.post("/update-airports")
    assert resp.status_code == 200

    data = json.loads((data_dir / "airports.json").read_text())
    assert len(data) == 2
    assert all(not a["routes"] for a in data)

    stats = json.loads((data_dir / "routes_stats.json").read_text())
    assert stats["airports_active"] == 2
    assert stats["airports_total"] == 2

    full = json.loads((data_dir / "airports_full.json").read_text())
    assert len(full) == 2


def test_update_airports_self_clean(tmp_path, monkeypatch):
    """Routes with identical start and end should be removed."""
    airports_csv = (
        "id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,continent,iso_country,iso_region,municipality,scheduled_service,icao_code,iata_code,gps_code,local_code,home_link,wikipedia_link,keywords\n"
        "1,AAA,airport,AirportA,10,20,,EU,AA,AA-1,CityA,yes,,AAA,AAA,,,\n"
        "2,BBB,airport,AirportB,30,40,,EU,BB,BB-1,CityB,yes,,BBB,BBB,,,"
    )
    countries_csv = (
        "id,code,name,continent,wikipedia_link,keywords\n"
        "1,AA,Country AA,EU,,\n"
        "2,BB,Country BB,EU,,"
    )
    airlines_dat = "1,Test Airline,\\N,AL,ALN,CALL,Country,Y\n"

    def fake_get(url):
        if "airports.csv" in url:
            return fake_response(airports_csv)
        if "countries.csv" in url:
            return fake_response(countries_csv)
        if "airlines.dat" in url:
            return fake_response(airlines_dat)
        raise AssertionError(url)

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    monkeypatch.setattr(server, "AIRPORTS_FULL_PATH", data_dir / "airports_full.json")
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")

    routes = [
        {
            "airline": "AL",
            "flight_number": "1",
            "icao24": "abc",
            "source": "AAA",
            "destination": "AAA",
            "first_seen": "t",
            "last_seen": "t",
            "status": "Active",
        },
        {
            "airline": "AL",
            "flight_number": "2",
            "icao24": "xyz",
            "source": "AAA",
            "destination": "BBB",
            "first_seen": "t",
            "last_seen": "t",
            "status": "Active",
        },
    ]
    (data_dir / "routes_dynamic.json").write_text(json.dumps(routes))

    client = TestClient(server.app)
    resp = client.post("/update-airports")
    assert resp.status_code == 200

    data = json.loads((data_dir / "airports.json").read_text())
    assert len(data) == 2
    airports = {a["code"]: a for a in data}
    assert len(airports["AAA"]["routes"]) == 1
    assert len(airports["BBB"]["routes"]) == 1
    assert airports["AAA"]["routes"][0]["to_name"] == "AirportB"

    routes_db = json.loads((data_dir / "routes_dynamic.json").read_text())
    assert len(routes_db) == 1
    assert routes_db[0]["destination"] == "BBB"

    full = json.loads((data_dir / "airports_full.json").read_text())
    assert len(full) == 2


def test_get_airports_missing(tmp_path, monkeypatch):
    """/airports.json should return 404 when no data file exists."""
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")

    client = TestClient(server.app)
    resp = client.get("/airports.json")
    assert resp.status_code == 404
