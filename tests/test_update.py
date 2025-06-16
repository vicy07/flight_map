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
    routes_csv = "AL,1,AAA,1,BBB,2,\\N,0,\n"
    airlines_dat = "1,Test Airline,\\N,AL,TAL,CALL,Country,Y\n"


    def fake_get(url):
        if "airports.csv" in url:
            return fake_response(airports_csv)
        if "routes.dat" in url:
            return fake_response(routes_csv)
        return fake_response(airlines_dat)

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")

    client = TestClient(server.app)
    resp = client.post("/update-airports")
    assert resp.status_code == 200

    data = json.loads((data_dir / "airports.json").read_text())
    assert len(data) == 1
    assert len(data[0]["routes"]) == 1
    assert data[0]["routes"][0]["airline"] == "Test Airline"