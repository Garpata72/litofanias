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
    info = r.json()
    assert info["medidas_mm"][0] == 40.0

    stl = client.get(info["stl"])
    assert len(stl.content) == 84 + 50 * info["triangulos"]
    assert "litofania-plana-foto.stl" in stl.headers["content-disposition"]
    assert client.get(info["vista"]).status_code == 200


def test_preview_is_lighter_for_big_pieces(client):
    meta = client.post("/api/imagenes", files={"archivo": ("g.png", _png(1500, 1000), "image/png")}).json()
    info = client.post("/api/litofanias/plana", json={"imagen_id": meta["id"], "ancho": 200, "resolucion": 0.1}).json()
    full = int(client.get(info["stl"]).content[80:84][::-1].hex(), 16)
    preview = int(client.get(info["vista"]).content[80:84][::-1].hex(), 16)
    assert full == info["triangulos"] > 4_000_000
    assert preview <= 750_000


def test_rejects_bad_input(client):
    assert client.post("/api/imagenes", files={"archivo": ("x.png", b"no es imagen", "image/png")}).status_code == 400
    assert client.post("/api/litofanias/plana", json={"imagen_id": "noexiste"}).status_code == 404
    meta = client.post("/api/imagenes", files={"archivo": ("f.png", _png(), "image/png")}).json()
    r = client.post("/api/litofanias/plana", json={"imagen_id": meta["id"], "min": 2.5, "max": 2.0})
    assert r.status_code == 422
    assert client.get("/api/imagenes/..%2f..%2fetc/archivo").status_code == 404


def test_curved_shapes(client):
    meta = client.post("/api/imagenes", files={"archivo": ("c.png", _png(120, 60), "image/png")}).json()
    arc = client.post("/api/litofanias", json={"imagen_id": meta["id"], "forma": "arco", "ancho": 60, "angulo": 90, "resolucion": 0.5}).json()
    assert arc["radio_mm"] > 0 and client.get(arc["stl"]).status_code == 200

    cyl = client.post("/api/litofanias", json={"imagen_id": meta["id"], "forma": "cilindro", "diametro": 40, "resolucion": 0.5}).json()
    assert abs(cyl["medidas_mm"][0] - 40) < 0.5          # diámetro exterior
    assert "litofania-cilindro-c.stl" in client.get(cyl["stl"]).headers["content-disposition"]
    assert client.get(cyl["vista"]).status_code == 200
    assert client.get(f"/api/litofanias/{meta['id']}/esfera.stl").status_code == 404


def test_sphere_and_dome(client):
    meta = client.post("/api/imagenes", files={"archivo": ("s.png", _png(80, 50), "image/png")}).json()
    sph = client.post("/api/litofanias", json={"imagen_id": meta["id"], "forma": "esfera", "diametro": 50, "agujero": 20, "resolucion": 1}).json()
    assert abs(sph["medidas_mm"][0] - 50) < 1 and sph["radio_mm"] == 25
    assert client.get(sph["stl"]).status_code == 200
    dome = client.post("/api/litofanias", json={"imagen_id": meta["id"], "forma": "cupula", "diametro": 50, "ajuste": "panoramica", "resolucion": 1}).json()
    assert abs(dome["medidas_mm"][1] - 25) < 1      # media esfera de alto
    bad = client.post("/api/litofanias", json={"imagen_id": meta["id"], "forma": "esfera", "diametro": 50, "agujero": 45})
    assert bad.status_code == 422


def test_custom_mask_upload_and_generate(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")}).json()
    star = np.full((50, 80), 255, np.uint8)
    star[10:40, 20:60] = 0
    buf = io.BytesIO()
    Image.fromarray(star).save(buf, format="PNG")
    m = client.post("/api/mascaras", files={"archivo": ("rect.png", buf.getvalue(), "image/png")}).json()
    assert (m["ancho"], m["alto"]) == (40, 30)
    assert [x["id"] for x in client.get("/api/mascaras").json()] == [m["id"]]
    assert client.get(f"/api/mascaras/{m['id']}/archivo").status_code == 200

    body = {"imagen_id": meta["id"], "ancho": 40, "resolucion": 0.5, "marco": 2, "contorno": "propia"}
    assert client.post("/api/litofanias", json=body).status_code == 422
    info = client.post("/api/litofanias", json={**body, "mascara_id": m["id"], "zoom": 1.5, "centro_x": 0.2}).json()
    assert info["medidas_mm"][:2] == [40.0, 30.0]

    blank = io.BytesIO()
    Image.new("L", (30, 30), 255).save(blank, format="PNG")
    assert client.post("/api/mascaras", files={"archivo": ("b.png", blank.getvalue(), "image/png")}).status_code == 400
