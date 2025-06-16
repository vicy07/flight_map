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
    airports_csv = "1,AirportA,City,Country,AA,AAA,10,20\n2,AirportB,City,Country,BB,BBB,30,40"
    routes_csv = "AL,1,AAA,1,BBB,2,\\N,0,\n"

    def fake_get(url):
        if "airports.dat" in url:
            return fake_response(airports_csv)
        return fake_response(routes_csv)

    monkeypatch.chdir(tmp_path)
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server.requests, "get", fake_get)

    client = TestClient(server.app)
    resp = client.post("/update-airports")
    assert resp.status_code == 200

    data = json.loads(Path("public/airports.json").read_text())
    assert len(data) == 1
    assert len(data[0]["routes"]) == 1
    assert data[0]["routes"][0]["airline"] == "AL"

