import json
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

import sys
from pathlib import Path as SysPath
sys.path.insert(0, str(SysPath(__file__).resolve().parents[1]))
import server


def fake_response(data):
    mock = Mock()
    mock.json = lambda: data
    mock.status_code = 200
    mock.raise_for_status = lambda: None
    return mock


def test_update_flights(tmp_path, monkeypatch):
    states1 = {"states": [["abc", "AL123 ", "", 0, 0, 20.0, 10.0], ["def", "RYR456 ", "", 0, 0, 40.0, 30.0]]}
    states2 = {"states": [["abc", "AL123 ", "", 0, 0, 40.0, 30.0], ["def", "RYR456 ", "", 0, 0, 40.0, 30.0]]}
    states3 = {"states": [["def", "RYR456 ", "", 0, 0, 40.0, 30.0]]}
    responses = iter([states1, states2, states3])

    def fake_get(url):
        return fake_response(next(responses))

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "ACTIVE_FLIGHTS_PATH", data_dir / "active_flights.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    Path(server.AIRPORTS_PATH).write_text(
        json.dumps([
            {"code": "AAA", "name": "A", "lat": 10, "lon": 20},
            {"code": "BBB", "name": "B", "lat": 30, "lon": 40},
        ])
    )
    
    client = TestClient(server.app)
    client.post("/update-flights")
    client.post("/update-flights")
    resp = client.post("/update-flights")
    assert resp.status_code == 200

    routes = json.loads((data_dir / "routes_dynamic.json").read_text())
    assert len(routes) == 1
    r = routes[0]
    assert r["airline"] == "AL"
    assert r["flight_number"] == "123"
    assert r["source"] == "AAA"
    assert r["destination"] == "BBB"
    assert r["status"] == "Active"
    stats = json.loads((data_dir / "routes_stats.json").read_text())
    assert stats["routes"] == 1
    assert stats["active_planes"] == 1

    info = TestClient(server.app).get("/routes-info").json()
    assert info["routes"] == 1
    assert info["active_planes"] == 1

    assert TestClient(server.app).get("/routes-db").status_code == 200
    assert TestClient(server.app).get("/routes-stats").json()["routes"] == 1


def test_update_flights_missing_destination(tmp_path, monkeypatch):
    """Flight ending far from any airport should not create a route."""
    states1 = {
        "states": [
            ["abc", "AL123 ", "", 0, 0, 20.0, 10.0],
            ["ghi", "BAD1 ", "", 0, 0, 20.0, 10.0],
        ]
    }
    states2 = {
        "states": [
            ["abc", "AL123 ", "", 0, 0, 40.0, 30.0],
            ["ghi", "BAD1 ", "", 0, 0, 0.0, 0.0],
        ]
    }
    states3 = {"states": []}
    responses = iter([states1, states2, states3])

    def fake_get(url):
        return fake_response(next(responses))

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "ACTIVE_FLIGHTS_PATH", data_dir / "active_flights.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    Path(server.AIRPORTS_PATH).write_text(
        json.dumps([
            {"code": "AAA", "name": "A", "lat": 10, "lon": 20},
            {"code": "BBB", "name": "B", "lat": 30, "lon": 40},
        ])
    )

    client = TestClient(server.app)
    client.post("/update-flights")
    client.post("/update-flights")
    resp = client.post("/update-flights")
    assert resp.status_code == 200

    routes = json.loads((data_dir / "routes_dynamic.json").read_text())
    assert len(routes) == 1
    r = routes[0]
    assert r["source"] == "AAA"
    assert r["destination"] == "BBB"
    assert r["airline"] == "AL"
    stats = json.loads((data_dir / "routes_stats.json").read_text())
    assert stats["routes"] == 1
    assert stats["active_planes"] == 0

    info = TestClient(server.app).get("/routes-info").json()
    assert info["routes"] == 1
    assert info["active_planes"] == 0


def test_get_active_flights(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "ACTIVE_FLIGHTS_PATH", data_dir / "active_flights.json")
    active = {"abc": {"callsign": "AL123", "last_coord": [10, 20]}}
    (data_dir / "active_flights.json").write_text(json.dumps(active))

    client = TestClient(server.app)
    resp = client.get("/active-flights")
    assert resp.status_code == 200
    assert resp.json() == active

