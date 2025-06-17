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
    states = {
        "time": 1,
        "states": [
            ["abc", "CALL1 ", "", 0, 0, 10.0, 20.0],
            ["def", "CALL2 ", "", 0, 0, 30.0, 40.0],
        ],
    }

    def fake_get(url):
        return fake_response(states)

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "ROUTES_DB_PATH", data_dir / "routes_dynamic.json")
    monkeypatch.setattr(server, "STATS_PATH", data_dir / "routes_stats.json")

    client = TestClient(server.app)
    resp = client.post("/update-flights")
    assert resp.status_code == 200

    data = json.loads((data_dir / "routes_dynamic.json").read_text())
    assert len(data) == 2
    stats = json.loads((data_dir / "routes_stats.json").read_text())
    assert stats["routes"] == 2

    resp = client.get("/routes-db")
    assert resp.status_code == 200

    resp = client.get("/routes-stats")
    assert resp.json()["routes"] == 2

