import json
from pathlib import Path
from fastapi.testclient import TestClient
import sys
from pathlib import Path as SysPath
sys.path.insert(0, str(SysPath(__file__).resolve().parents[1]))
import server


def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "public").mkdir()
    monkeypatch.setattr(server, "DATA_DIR", data_dir)
    monkeypatch.setattr(server, "CONFIG_PATH", data_dir / "config.json")
    return data_dir, TestClient(server.app)


def test_admin_file_ops(tmp_path, monkeypatch):
    data_dir, client = setup(tmp_path, monkeypatch)
    (data_dir / "test.txt").write_text("hello")

    resp = client.get("/admin/files")
    assert resp.status_code == 200
    names = [f["name"] for f in resp.json()["files"]]
    assert "test.txt" in names

    resp = client.get("/admin/download/test.txt")
    assert resp.status_code == 200
    assert resp.text == "hello"

    resp = client.post(
        "/admin/upload/new.txt",
        files={"file": ("new.txt", b"data")},
    )
    assert resp.status_code == 200
    assert (data_dir / "new.txt").read_text() == "data"

    # New file metadata
    resp = client.get("/admin/files")
    assert resp.status_code == 200
    files = resp.json()["files"]
    info = next(f for f in files if f["name"] == "new.txt")
    assert "size" in info and info["size"] == 4
    assert "records" in info

    # Delete file
    resp = client.delete("/admin/delete/test.txt")
    assert resp.status_code == 200
    assert not (data_dir / "test.txt").exists()


def test_admin_config(tmp_path, monkeypatch):
    data_dir, client = setup(tmp_path, monkeypatch)

    resp = client.get("/admin/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "continents" in body
    assert body["config"]["airport_continents"] == ["EU"]

    payload = {"airport_continents": ["NA", "EU"], "flight_continents": ["NA"]}
    resp = client.post("/admin/config", json=payload)
    assert resp.status_code == 200
    saved = json.loads((data_dir / "config.json").read_text())
    assert set(saved["airport_continents"]) == {"EU", "NA"}
    assert saved["flight_continents"] == ["NA"]
