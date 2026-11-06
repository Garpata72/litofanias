import io
import importlib
import json
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from litofania import coaster, multicolor as mc, orca
from litofania.shapes import signed_volume

FILS = [mc.Filament("negro", "#1b1b1b", 0.5), mc.Filament("marron", "#a0602e", 1.6),
        mc.Filament("gris", "#8c8c8c", 1.2), mc.Filament("blanco", "#f2eee4", 3.0)]


def _photo(path, w=80, h=60):
    x = np.linspace(0, 1, w)[None, :, None]
    y = np.linspace(0, 1, h)[:, None, None]
    rgb = np.concatenate([x * np.ones((h, 1, 1)), y * np.ones((1, w, 1)), 0.5 * np.ones((h, w, 1))], -1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(path)
    return str(path)


def test_stack_colors_follow_hueforge_model():
    s = mc.stack_colors(FILS[:2] + FILS[3:], (0, 5, 20), 32, 0.08)
    assert np.allclose(s[0], mc.hex_rgb("#1b1b1b"))           # sin capas: la base
    white = np.linalg.norm(s[20:] - mc.hex_rgb("#f2eee4"), axis=1)
    assert np.all(np.diff(white) < 0)                          # cada capa de blanco acerca el color al blanco
    # el color de una capa más nunca se aleja del filamento que se está imprimiendo
    d = np.linalg.norm(s[6:20] - mc.hex_rgb("#a0602e"), axis=1)
    assert np.all(np.diff(d) <= 1e-9)


def test_build_relief_is_watertight_and_changes_match_orca(tmp_path):
    p = mc.ColorParams(width_mm=30, mm_per_px=0.5, layers=16, contour="circulo", rim_mm=1.5)
    r = mc.build(_photo(tmp_path / "f.png"), FILS[:2] + FILS[3:], p)
    assert signed_volume(r.solid.verts, r.solid.faces) > 0
    assert r.starts[0] == 0 and len(r.starts) == 3 and list(r.starts) == sorted(r.starts)
    ch = r.changes(p)
    assert [e for _, e in ch] == [2, 3]
    assert ch[0][0] == pytest.approx(p.z_base + r.starts[1] * p.layer)
    assert r.z.max() > p.z_base + p.layers * p.layer          # el borde para la resina sobresale
    # con 2 filamentos y la base de 4 capas, el primer cambio cae como mínimo en Z = 0,48 (la prueba de Carlos en Orca)
    r2 = mc.build(str(tmp_path / "f.png"), [FILS[0], FILS[3]], mc.ColorParams(width_mm=30, mm_per_px=0.5, starts=(1,)))
    assert r2.changes(mc.ColorParams()) == [(0.48, 2)]


def test_manual_starts_are_validated(tmp_path):
    with pytest.raises(ValueError):
        mc.build(_photo(tmp_path / "f.png"), FILS[:3], mc.ColorParams(width_mm=20, mm_per_px=0.5, starts=(9, 4)))
    with pytest.raises(ValueError):
        mc.build(str(tmp_path / "f.png"), FILS + FILS[:1], mc.ColorParams(width_mm=20, mm_per_px=0.5))


def test_orca_project_has_filaments_and_layer_changes(tmp_path):
    v = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], float)
    f = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    out = tmp_path / "p.3mf"
    colors = ["#111111", "#222222", "#333333", "#444444"]
    orca.write_project(str(out), [("pieza", 1, v, f)], colors, 0.08, 0.16, [(0.48, 2), (1.0, 3), (1.6, 4)], "pieza")
    z = zipfile.ZipFile(out)
    cfg = json.loads(z.read("Metadata/project_settings.config"))
    assert cfg["filament_colour"] == colors and cfg["layer_height"] == "0.08"
    assert len(cfg["flush_volumes_matrix"]) == 16 and len(cfg["flush_volumes_vector"]) == 8
    assert cfg["change_filament_gcode"].strip().startswith("M600")
    xml = z.read("Metadata/custom_gcode_per_layer.xml").decode()
    assert xml.count('type="2"') == 3 and 'top_z="0.48"' in xml and "MultiAsSingle" in xml
    assert b"OrcaSlicer" in z.read("3D/3dmodel.model")


@pytest.mark.parametrize("shape", coaster.SHAPES)
@pytest.mark.parametrize("mode", ["relieve", "incrustado"])
def test_coaster_shapes(shape, mode):
    p = coaster.CoasterParams(shape=shape, mode=mode, size_mm=80)
    c = coaster.build(p)
    b = c.whole.bounding_box()
    assert b[3] - b[0] == pytest.approx(80, abs=0.6)
    assert all(m.volume() > 0 for _, _, m in c.parts)
    if mode == "relieve":
        assert [e for _, e in c.changes] == [2, 3]
        assert coaster.resin_ml(p, c) > 0
        # sin capas mixtas: cada color en su franja de altura
        z1 = c.parts[1][2].bounding_box()
        assert z1[2] == pytest.approx(4.0)
    else:
        assert c.face_down and c.changes == [] and sorted(f for _, f, _ in c.parts) == [1, 2, 3]


def test_coaster_text_needs_content():
    with pytest.raises(ValueError):
        coaster.build(coaster.CoasterParams(motif="texto", text2="", text3=""))
    c = coaster.build(coaster.CoasterParams(motif="texto", text2="BAR", colors=2))
    assert len(c.parts) == 2


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LITOFANIAS_DATOS", str(tmp_path))
    from app import main, storage
    importlib.reload(storage)
    importlib.reload(main)
    return TestClient(main.app)


def test_api_color_photo_and_coaster(client, tmp_path):
    buf = io.BytesIO()
    Image.open(_photo(tmp_path / "x.png")).save(buf, format="PNG")
    img = client.post("/api/imagenes", files={"archivo": ("perro.png", buf.getvalue(), "image/png")}).json()
    body = {"imagen_id": img["id"], "ancho": 30, "resolucion": 0.5, "capas": 12, "contorno": "triangulo", "borde": 1,
            "filamentos": [{"nombre": "negro", "color": "#1b1b1b", "td": 0.5}, {"nombre": "blanco", "color": "#f2eee4", "td": 3}]}
    r = client.post("/api/multicolor/foto", json=body)
    assert r.status_code == 200, r.text
    info = r.json()
    assert len(info["cambios"]) == 1 and info["cambios"][0]["filamento"] == 2
    assert len(info["capas_color"]["colores"]) > 12
    for key in ("stl", "tresmf", "ajustes", "simulacion", "vista"):
        assert client.get(info[key]).status_code == 200
    assert "RESINA UV" in client.get(info["ajustes"]).text
    # mismas capas de cambio puestas a mano
    r = client.post("/api/multicolor/foto", json={**body, "cambios": [3]})
    assert r.json()["inicio"] == [3]
    assert client.post("/api/multicolor/foto", json={**body, "cambios": [3, 5]}).status_code == 422

    r = client.post("/api/posavasos", json={"forma": "triangulo", "tamano": 90, "modo": "relieve"})
    assert r.status_code == 200, r.text
    info = r.json()
    assert len(info["partes"]) == 3 and info["resina_ml"] > 0
    for key in ("stl", "tresmf", "ajustes"):
        assert client.get(info[key]).status_code == 200
    assert client.get(info["partes"][0]["url"]).status_code == 200
    r = client.post("/api/posavasos", json={"modo": "incrustado", "colores": 2, "motivo": "texto", "texto2": "BAR"})
    assert r.status_code == 200, r.text
    z = zipfile.ZipFile(io.BytesIO(client.get(r.json()["tresmf"]).content))
    assert 'key="extruder" value="2"' in z.read("Metadata/model_settings.config").decode()


def test_coaster_motif_fits_inside_triangle():
    p = coaster.CoasterParams(shape="triangulo", motif="texto", text2="CASA", text3="2026")
    c2, c3 = coaster.motifs(p)
    full = coaster.text_section("CASA", p.text_mm, 1000)
    assert c2.num_contour() == full.num_contour()       # ninguna letra cortada por el borde


def test_api_coaster_preview(client):
    r = client.post("/api/posavasos/vista", json={"forma": "gota", "modo": "relieve", "borde": 3})
    assert r.status_code == 200
    g = r.json()
    assert g["contorno"] and g["interior"] and g["c2"] and not g["vacio"]
