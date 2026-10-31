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


def test_moon_fill(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")}).json()
    r = client.get("/api/relleno.png?relleno=luna&ancho=80&alto=50")
    assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).size == (80, 50)
    for body in ({"forma": "esfera", "relleno": "luna", "ajuste": "relleno", "agujero": 20}, {"forma": "plana", "relleno": "luna", "zoom": 0.6}):
        info = client.post("/api/litofanias", json={"imagen_id": meta["id"], "diametro": 40, "ancho": 40, "resolucion": 0.8, **body})
        assert info.status_code == 200, info.text


def test_text_settings_and_presets(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")}).json()
    base = {"imagen_id": meta["id"], "ancho": 40, "resolucion": 0.5, "marco": 2}
    plain = client.post("/api/litofanias", json=base).json()
    info = client.post("/api/litofanias", json={**base, "texto": "Año 2026", "texto_mm": 6}).json()
    assert info["medidas_mm"][1] > plain["medidas_mm"][1] + 6       # la franja del texto va debajo
    assert info["gramos"] > 0
    txt = client.get(info["ajustes"])
    assert txt.status_code == 200 and "Ender 3 V3 KE" in txt.text and "DE PIE" in txt.text
    sphere = client.post("/api/litofanias", json={**base, "forma": "cupula", "diametro": 40, "texto": "Luna"})
    assert sphere.status_code == 200

    assert client.put("/api/plantillas/Regalo", json={"forma": "plana", "ancho": 120, "imagen_id": "x"}).status_code == 200
    assert client.get("/api/plantillas").json() == [{"nombre": "Regalo", "ajustes": {"forma": "plana", "ancho": 120}}]
    assert client.delete("/api/plantillas/Regalo").status_code == 200
    assert client.get("/api/plantillas").json() == []


def _closed(stl: bytes) -> bool:
    n = int.from_bytes(stl[80:84], "little")
    tri = np.frombuffer(stl[84:], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n)["v"]
    pts, idx = np.unique(tri.reshape(-1, 3), axis=0, return_inverse=True)
    f = idx.reshape(-1, 3)
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    return bool((np.unique(e, axis=0, return_counts=True)[1] == 2).all())


def test_accessories(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")}).json()
    base = {"imagen_id": meta["id"], "ancho": 60, "diametro": 50, "agujero": 30, "resolucion": 0.8, "marco": 3}
    assert client.post("/api/accesorios", json={"imagen_id": meta["id"], "forma": "plana"}).status_code == 404
    for forma, extra in [("plana", {}), ("plana", {"contorno": "corazon"}), ("arco", {}), ("cilindro", {}),
                         ("esfera", {}), ("cupula", {})]:
        lito = client.post("/api/litofanias", json={**base, "forma": forma, **extra}).json()
        info = client.post("/api/accesorios", json={"imagen_id": meta["id"], "forma": forma}).json()
        stl = client.get(info["stl"]).content
        assert _closed(stl), forma
        if forma == "plana":   # la caja y su marco, una al lado de la otra, son más anchas que la litofanía
            assert info["piezas"] == 2 and lito["medidas_mm"][0] < info["medidas_mm"][0]
        assert "LED USB" in client.get(info["ajustes"]).text


def test_texture_fill(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")}).json()
    rgb = np.zeros((40, 40, 3), np.uint8)
    rgb[::8] = (200, 40, 40)                       # rayas rojas: se guardan en gris con todo el contraste
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    tex = client.post("/api/texturas", files={"archivo": ("rayas.png", buf.getvalue(), "image/png")}).json()
    stored = Image.open(io.BytesIO(client.get(f"/api/texturas/{tex['id']}/archivo").content))
    assert stored.mode == "L" and np.asarray(stored).max() == 255 and np.asarray(stored).min() == 0
    assert [t["id"] for t in client.get("/api/texturas").json()] == [tex["id"]]

    q = f"relleno=textura&textura_id={tex['id']}&ancho=60&alto=40&mm_px=0.5"
    flat = np.asarray(Image.open(io.BytesIO(client.get(f"/api/relleno.png?{q}").content)), dtype=float)
    soft = np.asarray(Image.open(io.BytesIO(client.get(f"/api/relleno.png?{q}&textura_relieve=0.3").content)), dtype=float)
    assert flat.std() > soft.std() > 0               # el relieve se puede bajar
    assert client.get("/api/relleno.png?relleno=textura&textura_id=nada").status_code == 422

    body = {"imagen_id": meta["id"], "ancho": 40, "diametro": 40, "agujero": 20, "resolucion": 0.8,
            "relleno": "textura", "textura_id": tex["id"], "textura_mm": 10}
    assert client.post("/api/litofanias", json={**body, "zoom": 0.5}).status_code == 200
    assert client.post("/api/litofanias", json={**body, "forma": "esfera", "ajuste": "relleno"}).status_code == 200
    assert client.post("/api/litofanias", json={**body, "textura_id": None}).status_code == 422


def test_star_polygon_heart_and_hanging_tab(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(), "image/png")}).json()
    base = {"imagen_id": meta["id"], "ancho": 60, "resolucion": 0.5, "marco": 2}
    for extra in ({"contorno": "estrella", "puntas": 6, "interior": 40}, {"contorno": "poligono", "lados": 3},
                  {"contorno": "corazon", "base_plana": 20}, {"contorno": "corazon", "colgar": True},
                  {"colgar": True, "texto": "Hola"}):
        r = client.post("/api/litofanias", json={**base, **extra})
        assert r.status_code == 200, (extra, r.text)
        assert _closed(client.get(r.json()["stl"]).content), extra
    plain = client.post("/api/litofanias", json=base).json()
    tab = client.post("/api/litofanias", json={**base, "colgar": True, "colgar_ancho": 16}).json()
    assert 16 <= tab["medidas_mm"][1] - plain["medidas_mm"][1] <= 18   # la pestaña sale por arriba
    assert client.post("/api/accesorios", json={"imagen_id": meta["id"], "forma": "plana"}).status_code == 422
    bad = client.post("/api/litofanias", json={**base, "colgar": True, "colgar_ancho": 10, "colgar_agujero": 8})
    assert bad.status_code == 422


def test_collage(client):
    ids = [client.post("/api/imagenes", files={"archivo": (f"f{k}.png", _png(60 + 20 * k, 40), "image/png")}).json()["id"]
           for k in range(3)]
    items = [{"imagen_id": i} for i in ids]
    items[1].update(girar=90, recorte=[0.1, 0.1, 0.8, 0.8], zoom=0.7)
    base = {"imagen_id": ids[0], "collage": items, "resolucion": 0.5, "separacion": 3}
    single = client.post("/api/litofanias", json={**base, "collage": [], "ancho": 90, "marco": 2}).json()
    row = client.post("/api/litofanias", json={**base, "ancho": 90, "marco": 2}).json()
    assert row["medidas_mm"][0] == 90 and row["medidas_mm"][1] < single["medidas_mm"][1]   # tres en fila: más bajas
    grid = client.post("/api/litofanias", json={**base, "ancho": 90, "marco": 2, "collage_filas": 2}).json()
    assert grid["medidas_mm"][1] > row["medidas_mm"][1]
    for extra in ({"contorno": "corazon"}, {"forma": "arco"}, {"forma": "cilindro", "diametro": 50},
                  {"forma": "esfera", "diametro": 50, "agujero": 20, "cobertura": 240},
                  {"forma": "cupula", "diametro": 50, "ajuste": "panoramica"}):
        r = client.post("/api/litofanias", json={**base, "ancho": 90, **extra})
        assert r.status_code == 200, (extra, r.text)
        assert _closed(client.get(r.json()["stl"]).content), extra
    gone = client.post("/api/litofanias", json={**base, "collage": items + [{"imagen_id": "noexiste"}]})
    assert gone.status_code == 404
    tight = client.post("/api/litofanias", json={**base, "ancho": 30, "marco": 2, "separacion": 12})
    assert tight.status_code == 422


def test_cone_waves_and_sphere_options(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(60, 60), "image/png")}).json()
    base = {"imagen_id": meta["id"], "resolucion": 0.8}
    for extra in ({"forma": "cono", "diametro": 70, "diametro_arriba": 50},
                  {"forma": "cono", "diametro": 50, "diametro_arriba": 70, "ondas": 8, "onda_mm": 2, "relieve": "fuera"},
                  {"forma": "cilindro", "diametro": 60, "ondas": 6, "onda_mm": 2},
                  {"forma": "esfera", "diametro": 60, "agujero": 30, "alto_grados": 60, "cobertura": 120,
                   "agujero_arriba": 15, "cuello": 8},
                  {"forma": "cupula", "diametro": 60, "agujero_arriba": 20, "relieve": "fuera"}):
        r = client.post("/api/litofanias", json={**base, **extra})
        assert r.status_code == 200, (extra, r.text)
        assert _closed(client.get(r.json()["stl"]).content), extra
    cone = client.post("/api/litofanias", json={**base, "forma": "cono", "diametro": 70, "diametro_arriba": 50}).json()
    assert abs(cone["medidas_mm"][0] - 70) < 1 and cone["conico"]["pendiente"] < 0
    wide = client.post("/api/imagenes", files={"archivo": ("ancha.png", _png(400, 40), "image/png")}).json()
    flat = client.post("/api/litofanias", json={**base, "imagen_id": wide["id"], "forma": "cono", "diametro": 200,
                                                "diametro_arriba": 40})
    assert flat.status_code == 422          # demasiado bajo para tanta diferencia de diámetros


def test_new_accessories_and_3mf(client):
    import zipfile
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(80, 60), "image/png")}).json()
    base = {"imagen_id": meta["id"], "resolucion": 0.8}
    acc = lambda forma, **kw: client.post("/api/accesorios", json={"imagen_id": meta["id"], "forma": forma, **kw})

    lito = client.post("/api/litofanias", json={**base, "ancho": 60}).json()
    desk = acc("plana", escritorio=True, inclinacion=12).json()
    assert desk["piezas"] == 3 and _closed(client.get(desk["stl"]).content)     # caja, marco y peana
    z = zipfile.ZipFile(io.BytesIO(client.get(lito["tresmf"]).content))
    model = z.read("3D/3dmodel.model").decode()
    assert model.count("<object ") == 4 and "peana" in model and "marco" in model   # litofanía, caja, marco y peana
    assert zipfile.ZipFile(io.BytesIO(client.get(desk["tresmf"]).content)).read("3D/3dmodel.model").decode().count("<object ") == 3
    tight = acc("plana", holgura_marco=0.05).json()
    assert tight["piezas"] == 2 and _closed(client.get(tight["stl"]).content)
    slot = acc("plana", montaje="ranura").json()
    assert slot["piezas"] == 1 and _closed(client.get(slot["stl"]).content)

    client.post("/api/litofanias", json={**base, "forma": "cono", "diametro": 90, "diametro_arriba": 70, "ondas": 6})
    for kw in ({}, {"pilas": True}, {"vela": True}, {"tipo": "casquillo", "casquillo": 29}):
        r = acc("cono", **kw)
        assert r.status_code == 200, (kw, r.text)
        assert _closed(client.get(r.json()["stl"]).content), kw
    assert acc("cono", tipo="casquillo", casquillo=29).json()["nombre"] == "Aro para el casquillo"
    assert acc("cono", tipo="casquillo", casquillo=50).status_code == 422   # el casquillo no cabe arriba

    client.post("/api/litofanias", json={**base, "forma": "esfera", "diametro": 90, "agujero": 60, "cuello": 8})
    r = acc("esfera", vela=True)
    assert r.status_code == 200 and _closed(client.get(r.json()["stl"]).content)
    client.post("/api/litofanias", json={**base, "forma": "cilindro", "diametro": 40})
    assert acc("cilindro", pilas=True).status_code == 422          # el portapilas no cabe


def test_prism_box_and_overhang(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(80, 60), "image/png")}).json()
    other = client.post("/api/imagenes", files={"archivo": ("otra.png", _png(60, 80), "image/png")}).json()
    base = {"imagen_id": meta["id"], "resolucion": 0.8, "forma": "cilindro", "caras": 4, "ancho": 60, "separacion": 4}
    r = client.post("/api/litofanias", json=base)
    assert r.status_code == 200, r.text            # sin collage, la misma foto en las 4 caras
    info = r.json()
    assert info["caras"] == 4 and _closed(client.get(info["stl"]).content)
    assert abs(info["medidas_mm"][0] - 60) < 2   # cara de 60 mm
    photos = [{"imagen_id": i} for i in (meta["id"], other["id"], meta["id"], other["id"])]
    for caras, fuera in ((4, False), (4, True), (3, False)):
        r = client.post("/api/litofanias", json={**base, "caras": caras, "relieve": "fuera" if fuera else "dentro",
                                                  "collage": photos[:caras]})
        assert r.status_code == 200, (caras, r.text)
        assert _closed(client.get(r.json()["stl"]).content), (caras, fuera)
    assert client.post("/api/litofanias", json={**base, "collage": photos[:3]}).status_code == 422   # faltan fotos
    assert client.post("/api/litofanias", json={**base, "caras": 2}).status_code == 422

    flat = {"imagen_id": meta["id"], "resolucion": 0.8, "ancho": 60}
    plain = client.post("/api/litofanias", json=flat).json()
    ramp = client.post("/api/litofanias", json={**flat, "voladizo": 45}).json()
    assert _closed(client.get(ramp["stl"]).content) and ramp["gramos"] <= plain["gramos"]


def test_prism_base(client):
    meta = client.post("/api/imagenes", files={"archivo": ("foto.png", _png(80, 60), "image/png")}).json()
    client.post("/api/litofanias", json={"imagen_id": meta["id"], "resolucion": 0.8, "forma": "cilindro",
                                         "caras": 5, "ancho": 50})
    for kw in ({}, {"vela": True}):
        r = client.post("/api/accesorios", json={"imagen_id": meta["id"], "forma": "cilindro", **kw})
        assert r.status_code == 200, r.text
        assert _closed(client.get(r.json()["stl"]).content)
    r = client.post("/api/accesorios", json={"imagen_id": meta["id"], "forma": "cilindro", "tipo": "casquillo"})
    assert r.status_code == 422
