import numpy as np

from litofania.medal import MedalParams, build, distance_inside, medal, shape_mask


def _closed(faces):
    e = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    directed = {tuple(x) for x in e.tolist()}
    return len(directed) == len(e) and all((b, a) in directed for a, b in directed)


def test_distancia_al_borde_de_un_circulo():
    n = 121
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.hypot(xx - 60, yy - 60)
    mask = r <= 55
    d = distance_inside(mask, 20)
    esperado = np.clip(55.5 - r, 0, 21)
    assert np.abs(d[mask] - np.minimum(esperado[mask], 21)).max() < 1.0
    assert d[~mask].max() == 0.0


def test_formas_simetricas_y_no_vacias():
    for shape in ("circulo", "ovalo", "redondeado", "escudo"):
        m = shape_mask(shape, 100, 90)
        assert m.sum() > 0.4 * m.size, shape
        assert (m == m[:, ::-1]).all(), shape
    escudo = shape_mask("escudo", 100, 90)
    assert escudo[5].sum() > 4 * escudo[-3].sum()          # ancho arriba, punta abajo


def test_medalla_cerrada_con_aro_mas_alto_que_el_relieve():
    p = MedalParams(width_mm=30, height_mm=30, mm_per_px=0.25, base_mm=1.5, relief_mm=1.0, rim_mm=2.0)
    rel = np.random.default_rng(1).random((80, 80))
    t, mask, extra = build(rel, p)
    top = 1.5 + 1.0 + 0.2
    assert extra == 0.0 and abs(t.max() - top) < 1e-9
    campo = t[mask & (t < top - 1e-6)]
    assert campo.max() <= 1.5 + 1.0 + 1e-6 and campo.min() >= 1.5 - 1e-6
    s = medal(rel, p)
    assert _closed(s.faces)
    assert abs(np.ptp(s.verts[:, 0]) - 30) < 0.5 and abs(s.verts[:, 2].max() - top) < 1e-6


def test_pestana_para_colgar_anade_altura_y_sigue_cerrada():
    p = MedalParams(width_mm=30, height_mm=30, mm_per_px=0.25, tab=(8.0, 3.0))
    t, mask, extra = build(np.full((60, 60), 0.5), p)
    assert extra > 7.5
    assert _closed(medal(np.full((60, 60), 0.5), p).faces)
