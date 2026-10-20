import numpy as np
from PIL import Image

from litofania.flat import flat_mesh
from litofania.heightmap import FlatParams, load_gray, thickness_map
from litofania.stl import write_stl


def _edges_are_manifold(faces):
    e = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    directed = {tuple(x) for x in e.tolist()}
    assert len(directed) == len(e), "arista dirigida repetida: orientación inconsistente"
    assert all((b, a) in directed for a, b in directed), "malla abierta"


def _volume(verts, faces):
    tri = verts[faces]
    return np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6


def test_flat_is_watertight_with_positive_volume():
    t = np.full((5, 7), 2.0)
    verts, faces = flat_mesh(t, 1.0)
    _edges_are_manifold(faces)
    assert np.isclose(_volume(verts, faces), 6 * 4 * 2.0)


def test_dark_is_thick_and_border_is_max(tmp_path):
    img = np.zeros((20, 40), dtype=np.uint8)
    img[:, 20:] = 255
    path = tmp_path / "in.png"
    Image.fromarray(img).save(path)
    p = FlatParams(width_mm=20, mm_per_px=0.5, border_mm=1.0)
    t = thickness_map(load_gray(str(path), p), p)
    assert np.isclose(t[0, 0], p.max_mm)
    mid = t.shape[0] // 2
    assert t[mid, 3] > t[mid, -4]
    verts, faces = flat_mesh(t, p.mm_per_px)
    _edges_are_manifold(faces)
    out = tmp_path / "out.stl"
    write_stl(str(out), verts, faces)
    assert out.stat().st_size == 84 + 50 * len(faces)


def test_curved_shapes_are_watertight():
    from litofania.shapes import build_solid, signed_volume

    t = np.random.default_rng(1).uniform(0.8, 3.0, (12, 40))
    for shape in ("plana", "arco", "cilindro"):
        s = build_solid(t, 0.5, shape, 120)
        _edges_are_manifold(s.faces)
        assert signed_volume(s.verts, s.faces) > 0, shape


def test_cylinder_geometry():
    from litofania.shapes import build_solid

    t = np.full((10, 63), 2.0)
    s = build_solid(t, 1.0, "cilindro")
    r = np.hypot(s.verts[:, 0], s.verts[:, 1])
    assert np.isclose(r.max(), 63 / (2 * np.pi))       # perímetro exterior = ancho de la imagen
    assert np.isclose(r.min(), r.max() - 2.0)          # el relieve va por dentro


def test_sphere_and_dome_are_watertight():
    from litofania.shapes import build_sphere, signed_volume, sphere_lats

    t = np.random.default_rng(2).uniform(0.8, 3.0, (20, 48))
    for shape in ("esfera", "cupula"):
        top, bottom = sphere_lats(30.0, shape, 20.0, 1.0)
        s = build_sphere(t, 30.0, top, bottom)
        _edges_are_manifold(s.faces)
        assert signed_volume(s.verts, s.faces) > 0, shape
        r = np.linalg.norm(s.verts, axis=1)
        assert np.isclose(r.max(), 30.0)
    top, bottom = sphere_lats(30.0, "esfera", 20.0, 1.0)
    assert np.isclose(30.0 * np.cos(bottom), 10.0)   # abertura de 20 mm de diámetro


def test_contours_are_watertight_with_frame():
    from litofania.contours import CONTOURS, contour_mask, erode
    from litofania.shapes import build_solid, signed_volume

    t = np.full((40, 60), 1.0)
    for c in CONTOURS:
        mask = contour_mask(40, 60, c)
        t2 = t.copy()
        t2[mask & ~erode(mask, 3)] = 3.0
        s = build_solid(t2, 0.5, "plana", mask=mask)
        _edges_are_manifold(s.faces)
        assert signed_volume(s.verts, s.faces) > 0, c
    heart = contour_mask(40, 60, "corazon")
    assert heart[20, 30] and not heart[0, 30] and not heart[39, 0]   # centro dentro, muesca y esquinas fuera
