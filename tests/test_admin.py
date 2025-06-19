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
