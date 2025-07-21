import json
from pathlib import Path
from datetime import datetime, timedelta
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


def test_update_routes(tmp_path, monkeypatch):
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
    monkeypatch.setattr(server, "ACTIVE_PLANES_PATH", data_dir / "active_planes.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    monkeypatch.setattr(server, "AIRPORTS_FULL_PATH", data_dir / "airports_full.json")
    monkeypatch.setattr(server, "update_airports", lambda: {})
    airports = [
        {"code": "AAA", "name": "A", "lat": 10, "lon": 20},
        {"code": "BBB", "name": "B", "lat": 30, "lon": 40},
    ]
    Path(server.AIRPORTS_PATH).write_text(json.dumps(airports))
    Path(server.AIRPORTS_FULL_PATH).write_text(json.dumps(airports))
    server.AIRPORTS_MAP = {a["code"]: a for a in airports}
    server.build_airport_tree(airports)
    
    client = TestClient(server.app)
    client.post("/update-routes")
    client.post("/update-routes")
    resp = client.post("/update-routes")
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

    info = TestClient(server.app).get("/info").json()
    assert info["routes"] == 1
    assert info["active_planes"] == 1




def test_update_routes_missing_destination(tmp_path, monkeypatch):
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
    monkeypatch.setattr(server, "ACTIVE_PLANES_PATH", data_dir / "active_planes.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    monkeypatch.setattr(server, "AIRPORTS_FULL_PATH", data_dir / "airports_full.json")
    monkeypatch.setattr(server, "update_airports", lambda: {})
    airports = [
        {"code": "AAA", "name": "A", "lat": 10, "lon": 20},
        {"code": "BBB", "name": "B", "lat": 30, "lon": 40},
    ]
    Path(server.AIRPORTS_PATH).write_text(json.dumps(airports))
    Path(server.AIRPORTS_FULL_PATH).write_text(json.dumps(airports))
    server.AIRPORTS_MAP = {a["code"]: a for a in airports}
    server.build_airport_tree(airports)

    client = TestClient(server.app)
    client.post("/update-routes")
    client.post("/update-routes")
    resp = client.post("/update-routes")
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

    info = TestClient(server.app).get("/info").json()
    assert info["routes"] == 1
    assert info["active_planes"] == 0


def test_get_active_planes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "ACTIVE_PLANES_PATH", data_dir / "active_planes.json")
    active = {"abc": {"callsign": "AL123", "last_coord": [10, 20]}}
    (data_dir / "active_planes.json").write_text(json.dumps(active))

    client = TestClient(server.app)
    resp = client.get("/active-planes")
    assert resp.status_code == 200
    assert resp.json() == active


def test_route_expiration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "ACTIVE_PLANES_PATH", data_dir / "active_planes.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")
    monkeypatch.setattr(server, "AIRPORTS_PATH", data_dir / "airports.json")
    monkeypatch.setattr(server, "AIRPORTS_FULL_PATH", data_dir / "airports_full.json")
    monkeypatch.setattr(server, "update_airports", lambda: {})

    airports = [
        {"code": "AAA", "name": "A", "lat": 10, "lon": 20},
        {"code": "BBB", "name": "B", "lat": 30, "lon": 40},
    ]
    Path(server.AIRPORTS_PATH).write_text(json.dumps(airports))
    Path(server.AIRPORTS_FULL_PATH).write_text(json.dumps(airports))
    server.AIRPORTS_MAP = {a["code"]: a for a in airports}
    server.build_airport_tree(airports)

    past = (datetime.utcnow() - timedelta(days=32)).isoformat() + "Z"
    routes = [
        {
            "airline": "AL",
            "flight_number": "123",
            "icao24": "abc",
            "source": "AAA",
            "destination": "BBB",
            "first_seen": past,
            "last_seen": past,
            "status": "Not Active",
        }
    ]
    (data_dir / "routes_dynamic.json").write_text(json.dumps(routes))
    (data_dir / "active_planes.json").write_text("{}")

    def fake_get(url):
        return fake_response({"states": []})

    monkeypatch.setattr(server.requests, "get", fake_get)

    client = TestClient(server.app)
    resp = client.post("/update-routes")
    assert resp.status_code == 200

    remaining = json.loads((data_dir / "routes_dynamic.json").read_text())
    assert remaining == []

    stats = json.loads((data_dir / "routes_stats.json").read_text())
    assert stats["removed_last_run"] == 1

    info = TestClient(server.app).get("/info").json()
    assert info["removed_last_hour"] == 1



