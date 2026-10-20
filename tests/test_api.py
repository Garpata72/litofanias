import io
import importlib

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LITOFANIAS_DATOS", str(tmp_path))
    from app import main, storage
    importlib.reload(storage)
    importlib.reload(main)
    return TestClient(main.app)


def _png(w=60, h=40):
    arr = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_health_and_static(client):
    assert client.get("/api/salud").json()["app"] == "litofanias"
    assert "Litofanías" in client.get("/").text


def test_upload_list_and_generate(client):
    r = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")})
    assert r.status_code == 200
    meta = r.json()
    assert (meta["ancho"], meta["alto"]) == (60, 40)
    assert [m["id"] for m in client.get("/api/imagenes").json()] == [meta["id"]]
    assert client.get(f"/api/imagenes/{meta['id']}/archivo").status_code == 200

    r = client.post("/api/litofanias/plana", json={"imagen_id": meta["id"], "ancho": 40, "resolucion": 0.5, "marco": 2})
    assert r.status_code == 200
    tris = int(r.headers["x-triangulos"])
    assert len(r.content) == 84 + 50 * tris
    assert "litofania-foto.stl" in r.headers["content-disposition"]


def test_rejects_bad_input(client):
    assert client.post("/api/imagenes", files={"archivo": ("x.png", b"no es imagen", "image/png")}).status_code == 400
    assert client.post("/api/litofanias/plana", json={"imagen_id": "noexiste"}).status_code == 404
    meta = client.post("/api/imagenes", files={"archivo": ("f.png", _png(), "image/png")}).json()
    r = client.post("/api/litofanias/plana", json={"imagen_id": meta["id"], "min": 2.5, "max": 2.0})
    assert r.status_code == 422
    assert client.get("/api/imagenes/..%2f..%2fetc/archivo").status_code == 404
