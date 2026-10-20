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
    for c in CONTOURS[:-1]:   # todos menos «propia», que viene de una imagen
        mask = contour_mask(40, 60, c)
        t2 = t.copy()
        t2[mask & ~erode(mask, 3)] = 3.0
        s = build_solid(t2, 0.5, "plana", mask=mask)
        _edges_are_manifold(s.faces)
        assert signed_volume(s.verts, s.faces) > 0, c
    heart = contour_mask(40, 60, "corazon")
    assert heart[20, 30] and not heart[0, 30] and not heart[39, 0]   # centro dentro, muesca y esquinas fuera


def test_custom_mask_with_hole_and_framing(tmp_path):
    from litofania.contours import prepare_mask
    from litofania.generate import generate
    from litofania.heightmap import crop_window

    # Anillo negro sobre fondo blanco, con margen: la máscara se recorta a la figura y conserva el hueco.
    yy, xx = np.mgrid[:120, :200]
    r = np.hypot(xx - 100, (yy - 60) * 1.0)
    img = np.where((r < 50) & (r > 20), 0, 255).astype(np.uint8)
    mask = prepare_mask(Image.fromarray(img))
    assert abs(mask.width - mask.height) <= 1
    arr = np.asarray(mask)
    assert arr[arr.shape[0] // 2, arr.shape[1] // 2] == 0 and arr[arr.shape[0] // 2, 5] == 255
    # La misma silueta en blanco sobre negro da la misma máscara.
    assert np.array_equal(np.asarray(prepare_mask(Image.fromarray(255 - img))), arr)
    mask.save(tmp_path / "m.png")

    photo = tmp_path / "f.png"
    Image.fromarray(np.tile(np.linspace(0, 255, 90, dtype=np.uint8), (60, 1))).save(photo)
    p = FlatParams(width_mm=40, mm_per_px=0.5, border_mm=2)
    r1 = generate(str(photo), str(tmp_path / "a.stl"), p, contour="propia", mask_path=str(tmp_path / "m.png"),
                  zoom=2.0, center=(0.0, 0.5))
    assert abs(r1.width_mm - r1.height_mm) < 1   # la pieza toma la proporción de la máscara

    # Encuadre: el centro pedido cae en el centro de la pieza, aunque el trozo se salga de la foto.
    assert crop_window(90, 60, 1.0, 2.0, (0.0, 0.5)) == (-15.0, 15.0, 30.0, 30.0)
    assert crop_window(90, 60, 1.5) == (0.0, 0.0, 90.0, 60.0)
    assert crop_window(90, 60, 1.5, 0.5) == (-45.0, -30.0, 180.0, 120.0)


def test_small_photo_sits_on_the_fill(tmp_path):
    from litofania.textures import PLAIN

    photo = tmp_path / "negra.png"
    Image.new("L", (60, 40), 0).save(photo)
    p = FlatParams(width_mm=40, mm_per_px=0.5, border_mm=0)
    g = load_gray(str(photo), p, zoom=0.5)
    rows, cols = g.shape
    assert abs(g[0, 0] - PLAIN) < 1e-9 and g[rows // 2, cols // 2] == 0.0    # foto en el centro, relleno alrededor
    assert 0 < g[rows // 2, cols // 4] < PLAIN                                # fundido en el borde de la foto
    moon = load_gray(str(photo), p, zoom=0.5, fill="luna")
    assert moon[rows // 2, cols // 2] == 0.0 and moon[:3].std() > 0.01         # alrededor, textura y no liso


def test_outside_relief_and_crop(tmp_path):
    from litofania.shapes import build_solid, build_sphere, signed_volume, sphere_lats

    t = np.random.default_rng(1).uniform(0.8, 3.0, (20, 40))
    for shape in ("arco", "cilindro"):
        s = build_solid(t, 0.5, shape, 120, outside=True)
        _edges_are_manifold(s.faces)
        r = np.hypot(s.verts[:, 0], s.verts[:, 1])
        assert abs(r.max() - s.radius_mm) < 1e-6 and abs(r.min() - (s.radius_mm - 3.0)) < 0.01
    lt, lb = sphere_lats(30, "esfera", 20, 0.5)
    s = build_sphere(t, 30, lt, lb, outside=True)
    _edges_are_manifold(s.faces)
    assert signed_volume(s.verts, s.faces) > 0

    # Giro y recorte: la mitad izquierda negra de una foto 40×20, girada 90°, queda arriba.
    img = np.full((20, 40), 255, np.uint8)
    img[:, :20] = 0
    Image.fromarray(img).save(tmp_path / "f.png")
    p = FlatParams(width_mm=20, mm_per_px=1, border_mm=0, rotate=90)
    g = load_gray(str(tmp_path / "f.png"), p)
    assert g.shape[0] > g.shape[1] and g[:3].mean() < 0.1 and g[-3:].mean() > 0.9
    p.crop = (0, 0.5, 1, 0.5)   # solo la mitad de abajo (la blanca)
    assert load_gray(str(tmp_path / "f.png"), p).min() > 0.9
