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
