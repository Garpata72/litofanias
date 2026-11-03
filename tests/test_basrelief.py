import numpy as np

from litofania.basrelief import blur, compress, poisson, shade


def test_poisson_recupera_la_superficie():
    yy, xx = np.mgrid[0:64, 0:80] / 10.0
    h = np.sin(xx) * np.cos(yy)
    gx = np.zeros_like(h)
    gy = np.zeros_like(h)
    gx[:, :-1] = h[:, 1:] - h[:, :-1]
    gy[:-1, :] = h[1:, :] - h[:-1, :]
    div = gx.copy()
    div[:, 1:] -= gx[:, :-1]
    div += gy
    div[1:, :] -= gy[:-1, :]
    u = poisson(div)
    assert np.abs((u - u.mean()) - (h - h.mean())).max() < 1e-6


def test_compresion_conserva_el_detalle_frente_al_escalon():
    # Un escalón grande (silueta) con una ondulación pequeña encima: tras comprimir, la ondulación
    # ocupa mucha más parte de la altura total que antes.
    x = np.linspace(0, 1, 200)
    depth = np.tile(np.where(x > 0.5, 0.9, 0.1) + 0.02 * np.sin(x * 60), (50, 1))
    rel = compress(depth, depth_px=100, alpha=4.0)
    assert rel.min() >= 0 and rel.max() <= 1
    antes = np.ptp(depth[25, 110:190]) / np.ptp(depth)
    despues = np.ptp(rel[25, 110:190]) / np.ptp(rel)
    assert despues > 2 * antes


def test_blur_y_shade():
    a = np.zeros((40, 40))
    a[20, 20] = 1.0
    b = blur(a, 2.0)
    assert abs(b.sum() - 1.0) < 1e-6 and b.max() < 0.1
    img = shade(np.zeros((10, 12)), 0.1)
    assert img.shape == (10, 12, 3) and img.dtype == np.uint8


def test_aislar_deja_el_fondo_liso_y_el_motivo_en_rango():
    from litofania.basrelief import aislar
    rel = np.full((60, 60), 0.3)
    rel[20:40, 20:40] = np.linspace(0.4, 0.9, 20)[None, :]
    mask = np.zeros((60, 60))
    mask[20:40, 20:40] = 1.0
    out = aislar(rel, mask)
    assert out[:10].max() < 1e-3 and out[:, :10].max() < 1e-3
    assert out[25:35, 25:35].min() > 0.05 and out.max() <= 1.0


def test_motivo_claro_frente_a_panel_de_figuras():
    from litofania.background import dominant
    uno = np.zeros((200, 150))
    uno[40:160, 40:110] = 1.0
    assert dominant(uno)[0]
    varios = np.zeros((200, 150))
    for y in (10, 80, 150):
        for x in (10, 90):
            varios[y:y + 30, x:x + 30] = 1.0
    assert not dominant(varios)[0]
    assert not dominant(np.ones((200, 150)))[0]
    assert not dominant(np.zeros((200, 150)))[0]


def test_sharpen_realza_el_detalle_y_respeta_el_rango():
    from litofania.basrelief import blur, sharpen
    rng = np.random.default_rng(1)
    rel = np.clip(blur(rng.random((200, 200)), 2.0) * 6 - 2.0, 0, 1)
    out = sharpen(rel, 0.5)
    assert out.min() >= 0 and out.max() <= 1
    hf = lambda a: np.abs(a - blur(a, 2.0)).mean()
    assert hf(out) > hf(rel)
    assert np.array_equal(sharpen(rel, 0), rel)


def test_volumen_devuelve_forma_global(tmp_path):
    from PIL import Image
    from litofania import relief
    y, x = np.mgrid[:200, :200]
    img = (255 * np.exp(-((x - 100) ** 2 + (y - 100) ** 2) / 2500)).astype(np.uint8)   # un cerro suave
    Image.fromarray(img).convert("RGB").save(tmp_path / "f.png")
    flat = relief.compute(tmp_path / "f.png", relief.ReliefParams(method="sin-ia", background="no", volume=0.0, sharpen=0), tmp_path)
    full = relief.compute(tmp_path / "f.png", relief.ReliefParams(method="sin-ia", background="no", volume=1.0, sharpen=0), tmp_path)
    assert 0 <= full.rel.min() and full.rel.max() <= 1
    coarse = blur(full.depth, 8)
    corr = lambda a: np.corrcoef(a.ravel(), coarse.ravel())[0, 1]
    assert corr(full.rel) >= corr(flat.rel)


def test_marigold_en_proceso_aparte(tmp_path, monkeypatch):
    import sys
    from PIL import Image
    from litofania import depth, marigold
    stub = tmp_path / "worker.py"
    stub.write_text("import sys, numpy as np\nnp.save(sys.argv[2], np.tile(np.linspace(0, 1, 40, dtype='float32'), (30, 1)))\nprint('cuda')\n")
    monkeypatch.setenv("LITOFANIAS_MARIGOLD", sys.executable)
    monkeypatch.setattr(marigold, "WORKER", stub)
    assert marigold.available()
    img = Image.new("RGB", (80, 60), (120, 120, 120))
    d, device, _, _ = depth.estimate("marigold", img, np.zeros((60, 80), dtype=np.float32), (80, 60))
    assert d.shape == (60, 80) and device.startswith("gráfica") and 0 <= d.min() and d.max() <= 1
    monkeypatch.setattr(marigold, "WORKER", tmp_path / "no-existe.py")
    assert not marigold.available()
