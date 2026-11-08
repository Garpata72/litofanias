import importlib
import io
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from litofania import magnets as m


# ───────── Maquetación ─────────

@pytest.mark.parametrize("paper,count", [("a4", 10), ("10x15", 2), ("13x18", 4), ("15x20", 4)])
def test_layout_defaults(paper, count):
    lay = m.layout(paper, m.Kit())
    assert lay.per_sheet == count
    assert lay.ruler is not None     # la regla de 50 mm cabe en todos con el imán de 50 mm


@pytest.mark.parametrize("paper", list(m.PAPERS))
@pytest.mark.parametrize("lado", [30, 50, 60, 70])
def test_layout_inside_paper_and_no_overlap(paper, lado):
    kit = m.Kit(lado=lado)
    try:
        lay = m.layout(paper, kit)
    except m.DoesNotFit:
        return
    half_w, half_h = kit.separacion + m.CROSS, lado / 2 + m.BLEED
    top = lay.height - m.MARGIN - m.HEADER
    for cx, cy in lay.centers:
        assert cx - half_w >= m.MARGIN - 1e-6 and cx + half_w <= lay.width - m.MARGIN + 1e-6
        assert cy - half_h >= m.MARGIN - 1e-6 and cy + half_h <= top + 1e-6
    for i, (ax, ay) in enumerate(lay.centers):
        for bx, by in lay.centers[i + 1:]:
            apart_x = abs(ax - bx) >= 2 * half_w + m.GAP_MIN - 1e-6
            apart_y = abs(ay - by) >= 2 * half_h + m.GAP_MIN - 1e-6
            assert apart_x or apart_y
    if lay.ruler:
        x, y, up = lay.ruler
        if up:   # la regla de pie no pisa ninguna foto ni cruz
            assert all(x - 3 > cx + half_w for cx, _ in lay.centers)
            assert y >= m.MARGIN and y + m.RULER <= top
        else:
            assert x + m.RULER <= lay.width - m.MARGIN and all(cy - half_h > y + 2 for _, cy in lay.centers)


def test_too_big_magnet_is_reported():
    with pytest.raises(m.DoesNotFit, match="no cabe en papel 10 × 15"):
        m.layout("10x15", m.Kit(lado=90))
    summary = m.layouts(m.Kit(lado=90))
    assert summary["10x15"]["por_hoja"] == 0 and "no cabe" in summary["10x15"]["error"]
    assert summary["a4"]["por_hoja"] >= 1


def test_kit_checks():
    assert m.Kit().separacion == 35
    with pytest.raises(ValueError, match="cruces caen dentro"):
        m.Kit(sep=28).check()
    with pytest.raises(ValueError, match="radio"):
        m.Kit(radio=30).check()


# ───────── Fotos ─────────

def test_crop_box_square_and_clamped():
    assert m.crop_box((400, 300), 1, 0.5, 0.5) == (50, 0, 350, 300)
    assert m.crop_box((400, 300), 2, 0.0, 1.0) == (0, 150, 150, 300)   # se queda dentro de la foto
    assert m.crop_box((300, 400), 1, 0.5, 0.2) == (0, 0, 300, 300)


def test_sheet_slots_copies_and_fill():
    a, b = m.Photo("a", copias=3), m.Photo("b")
    assert m.sheet_slots([a, b], 10, False) == [a, a, a, b]
    assert m.sheet_slots([a, b], 10, True) == [a, a, a, b, a, b, a, b, a, b]
    assert m.sheet_slots([], 4, True) == [None] * 4


def _jpg(path, w, h):
    arr = np.zeros((h, w, 3), np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)
    arr[: h // 2, :, 1] = 200
    Image.fromarray(arr).save(path, quality=92)


def test_pdf_pages_size_and_resolution(tmp_path):
    from pypdf import PdfReader

    big, small = tmp_path / "big.jpg", tmp_path / "small.jpg"
    _jpg(big, 1600, 1200)     # 1200 px a 54 mm: 564 ppp
    _jpg(small, 400, 400)     # 188 ppp: aviso
    out = tmp_path / "hoja.pdf"
    info = m.build_pdf(str(out), "10x15", m.Kit(), [m.Photo(str(big), copias=3), m.Photo(str(small))])
    assert info["hojas"] == 2 and info["fotos"] == 4 and info["por_hoja"] == 2
    assert [x["ppp"] for x in info["baja_resolucion"]] == [188]
    pdf = PdfReader(str(out))
    assert len(pdf.pages) == 2
    w, h = (float(v) / 72 * 25.4 for v in pdf.pages[0].mediabox.upper_right)
    assert (round(w, 1), round(h, 1)) == (101.6, 152.4)
    # La foto se incrusta a su resolución (sin reducirla) y una sola vez aunque tenga copias.
    sizes = set()
    for page in pdf.pages:
        for img in page.images:
            sizes.add(img.image.size)
    assert sizes == {(1200, 1200), (400, 400)}
    text = pdf.pages[0].extract_text()
    assert "Imprimir al 100 %" in text and "13 × 18" not in text


def test_pdf_respects_exif_rotation_and_frame(tmp_path):
    from pypdf import PdfReader

    arr = np.zeros((100, 200, 3), np.uint8)
    arr[:, :100] = (255, 0, 0)        # mitad izquierda roja, derecha negra
    img = Image.fromarray(arr)
    exif = img.getexif()
    exif[0x0112] = 6                   # el móvil la guardó girada: hay que girarla 90° a la derecha
    path = tmp_path / "movil.jpg"
    img.save(path, exif=exif, quality=95)
    out = tmp_path / "h.pdf"
    m.build_pdf(str(out), "a4", m.Kit(), [m.Photo(str(path), centro_y=0.0)])   # cuadrado de arriba
    im = PdfReader(str(out)).pages[0].images[0].image
    assert im.size == (100, 100)
    r, g, b = im.convert("RGB").getpixel((50, 50))
    assert r > 200 and g < 60          # tras girar, arriba queda lo que era la mitad izquierda (roja)


def test_blank_sheet(tmp_path):
    out = tmp_path / "vacia.pdf"
    info = m.build_pdf(str(out), "13x18", m.Kit(), [])
    assert info["fotos"] == 0 and info["hojas"] == 1
    assert out.stat().st_size > 1000


# ───────── Útiles ─────────

@pytest.mark.parametrize("lado,radio", [(50, 4), (60, 5), (35, 0)])
def test_tools_are_closed_meshes_matching_sizes(lado, radio):
    kit = m.Kit(lado=lado, radio=radio)
    base, marco, mont = m.base_corte(kit), m.marco_corte(kit), m.montaje(kit)
    for solid in (base, marco, mont):
        assert solid.status().name == "NoError" and solid.volume() > 0
    w, h = m.plate_size(kit)
    bb = base.bounding_box()
    assert bb[3] - bb[0] == pytest.approx(w) and bb[4] - bb[1] == pytest.approx(h)
    assert bb[5] == pytest.approx(m.PLATE + m.PIN_H)
    # Los pines de la base, los agujeros del marco y las cruces del PDF están a la misma distancia.
    pin = m.base_corte(kit) ^ m.Manifold.cube((4, 4, 2)).translate((kit.separacion - 2, -2, m.PLATE + 0.5))
    assert pin.volume() > 0
    assert (marco ^ m.Manifold.cylinder(3, 0.9, 0.9, 16).translate((kit.separacion, 0, 0))).volume() == pytest.approx(0, abs=1e-6)
    bm = mont.bounding_box()
    assert bm[5] == pytest.approx(m.pocket_depth(kit) + 2)


def test_scad_has_the_same_values():
    text = m.scad(m.Kit(lado=60, radio=5, sep=42))
    assert re.search(r"^lado\s*=\s*60;", text, re.M)
    assert re.search(r"^radio\s*=\s*5;", text, re.M)
    assert re.search(r"^sep_pines\s*=\s*42;", text, re.M)


# ───────── API ─────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LITOFANIAS_DATOS", str(tmp_path))
    from app import main, storage
    importlib.reload(storage)
    importlib.reload(main)
    return TestClient(main.app)


def _upload(client, w=900, h=700):
    buf = io.BytesIO()
    Image.fromarray(np.full((h, w, 3), 120, np.uint8)).save(buf, format="JPEG")
    return client.post("/api/imagenes", files={"archivo": ("foto.jpg", buf.getvalue(), "image/jpeg")}).json()["id"]


def test_api_papers_and_pdf(client):
    r = client.get("/api/imanes/papeles", params={"lado": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["sep"] == 35 and body["papeles"]["a4"]["por_hoja"] == 10
    assert client.get("/api/imanes/papeles", params={"lado": 50, "sep": 20}).status_code == 422

    image_id = _upload(client)
    r = client.post("/api/imanes/pdf", json={"papel": "15x20", "rellenar": True,
                                             "fotos": [{"imagen_id": image_id, "zoom": 2, "centro_x": 0.3, "copias": 1}]})
    assert r.status_code == 200, r.text
    info = r.json()
    assert info["fotos"] == 4 and info["hojas"] == 1
    assert info["baja_resolucion"] == [{"ppp": 165, "nombre": "foto.jpg"}]
    pdf = client.get(info["pdf"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    r = client.post("/api/imanes/pdf", json={"papel": "10x15", "lado": 95, "fotos": []})
    assert r.status_code == 422 and "no cabe" in r.json()["detail"]
    assert client.post("/api/imanes/pdf", json={"fotos": [{"imagen_id": "nohay"}]}).status_code == 404


def test_api_tools(client):
    for piece in ("base_corte", "marco_corte", "montaje", "todo"):
        r = client.get(f"/api/imanes/utiles/{piece}.stl", params={"lado": 60})
        assert r.status_code == 200 and len(r.content) > 1000
        assert "iman-60mm" in r.headers["content-disposition"]
    assert client.get("/api/imanes/utiles.3mf").content[:2] == b"PK"
    assert "sep_pines       = 35;" in client.get("/api/imanes/utiles.scad").text
    assert "35 mm del centro" in client.get("/api/imanes/utiles.txt").text
    assert client.get("/api/imanes/utiles/base_corte.stl", params={"radio": 40}).status_code == 422
