"""Posavasos multicolor con pocos cambios de filamento, para una impresora de un solo extrusor.

Regla básica: hay que cambiar de filamento en cada capa que tenga más de un color. Así que se diseña para
que haya muy pocas capas mixtas. Dos estrategias:

- «relieve»: cada color en su propia franja de altura (base, motivo encima, detalle encima del motivo).
  Ninguna capa tiene dos colores: un cambio por color extra, ya puesto en el proyecto de Orca. Con «borde
  para resina» la pieza lleva un muro alrededor que sube por encima del motivo y hace de molde: se vierte
  resina UV hasta enrasar y queda una cara lisa, brillante y protegida.
- «incrustado»: cara vista plana y lisa, impresa BOCA ABAJO. Los colores 2 y 3 ocupan solo la primera capa
  (0,3 mm), así que solo hay una capa mixta: 1 cambio con 2 colores, 2 con 3. El motivo va en espejo.

«Imprimir todo el color 1 con huecos y rellenarlos después con el color 2» no funciona: la boquilla chocaría
con las paredes ya impresas.

Se construye con manifold3d (sin OpenSCAD). Origen: posavasos_multicolor.scad del proyecto Multicolor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold, OpType

from litofania import text as engraving
from litofania.accessories import outline_loops
from litofania.contours import load_mask

SHAPES = ("redondo", "cuadrado", "triangulo", "hexagono", "octogono", "flor", "gota")
LAYER = 0.2
SEG = 128


@dataclass
class CoasterParams:
    mode: str = "relieve"            # relieve | incrustado
    colors: int = 3                  # 2 | 3
    shape: str = "redondo"
    size_mm: float = 100.0           # ancho total de la pieza
    corner_mm: float = 6.0           # redondeo de las esquinas (cuadrado, triángulo, polígonos)
    thickness_mm: float = 4.0        # grosor de la base (color 1)
    margin_mm: float = 5.0           # franja exterior libre de motivo
    inlay_mm: float = 0.3            # incrustado: grosor de los colores 2 y 3 (= primera capa en Orca)
    bevel_mm: float = 0.6            # incrustado: bisel del canto de la cara vista
    relief2_mm: float = 1.0          # relieve: alto del motivo (color 2) sobre la base
    relief3_mm: float = 0.8          # relieve: alto del detalle (color 3) sobre el color 2
    rim_mm: float = 3.0              # relieve: ancho del borde para la resina (0 = sin borde)
    rim_up_mm: float = 0.6           # relieve: lo que sube el borde por encima del motivo (capa de resina)
    motif: str = "demo"              # demo | texto | silueta
    text2: str = "CASA"
    text3: str = ""
    text_mm: float = 16.0            # alto de las letras
    mask2: str | None = None         # silueta (PNG preparado) del color 2
    mask3: str | None = None         # silueta del color 3
    motif_mm: float = 0.0            # ancho del motivo de silueta (0 = el máximo que cabe)


def snap(v: float, step: float = LAYER) -> float:
    """Alturas en múltiplos de la capa, para que cada color empiece justo en una capa."""
    return max(step, round(v / step) * step)


def _regular(sides: int, size: float) -> CrossSection:
    """Polígono regular apoyado en un lado (abajo), de `size` de ancho."""
    a0 = -math.pi / 2 - math.pi / sides
    pts = [(math.cos(a0 + 2 * math.pi * i / sides), math.sin(a0 + 2 * math.pi * i / sides)) for i in range(sides)]
    xs = [p[0] for p in pts]
    k = size / (max(xs) - min(xs))
    ys = [p[1] for p in pts]
    cy = (max(ys) + min(ys)) / 2
    return CrossSection([[(x * k, (y - cy) * k) for x, y in pts]])


def outline(p: CoasterParams, inset: float = 0.0) -> CrossSection:
    """Contorno de la pieza, centrado en el origen, metido `inset` mm hacia dentro."""
    s, r = p.size_mm, min(p.corner_mm, p.size_mm / 6)
    if p.shape == "redondo":
        cs = CrossSection.circle(s / 2, SEG)
    elif p.shape == "flor":            # borde ondulado de 8 pétalos
        k, amp = 8, 0.07
        pts = [(math.cos(t) * (1 + amp * math.cos(k * t)), math.sin(t) * (1 + amp * math.cos(k * t)))
               for t in np.linspace(0, 2 * math.pi, 256, endpoint=False)]
        cs = CrossSection([[(x * s / 2 / (1 + amp), y * s / 2 / (1 + amp)) for x, y in pts]])
    elif p.shape == "gota":            # gota de agua con la punta arriba
        pts = []
        for t in np.linspace(0, 2 * math.pi, 256, endpoint=False):
            x = math.sin(t) * math.sin(t / 2)
            y = math.cos(t)
            pts.append((x, y))
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        k = s / (max(xs) - min(xs))
        cy = (max(ys) + min(ys)) / 2
        cs = CrossSection([[(x * k, (y - cy) * k) for x, y in reversed(pts)]])   # antihorario
    else:
        sides = {"cuadrado": 4, "triangulo": 3, "hexagono": 6, "octogono": 8}[p.shape]
        cs = _regular(sides, s)
        if p.shape == "cuadrado":
            cs = CrossSection.square((s, s), center=True)
        if r > 0:                      # esquinas redondeadas sin cambiar el tamaño de los lados rectos
            cs = cs.offset(-r, JoinType.Miter, 10).offset(r, JoinType.Round, circular_segments=SEG)
            b = cs.bounds()          # al redondear las puntas se pierde ancho: se vuelve al tamaño pedido
            k = s / (b[2] - b[0])
            cs = cs.translate((-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2)).scale((k, k))
    return cs.offset(-inset, JoinType.Round, circular_segments=SEG) if inset else cs


def _from_mask(mask: np.ndarray, mm_per_px: float) -> CrossSection:
    loops = outline_loops(mask, mm_per_px)
    if not loops:
        return CrossSection()
    cs = CrossSection(loops, FillRule.EvenOdd)
    b = cs.bounds()
    return cs.translate((-(b[0] + b[2]) / 2, -(b[1] + b[3]) / 2))


def text_section(text: str, height_mm: float, max_width_mm: float) -> CrossSection:
    if not text.strip():
        return CrossSection()
    px = 0.1                           # 10 píxeles por mm: el escalón queda muy por debajo de la boquilla
    cov = engraving.coverage(text.strip(), height_mm / px, max_width_mm / px)
    m = np.pad(cov >= 0.5, 2)
    return _from_mask(m, px)


def mask_section(path: str, width_mm: float, max_mm: float) -> CrossSection:
    from PIL import Image
    with Image.open(path) as im:
        aspect = im.width / im.height
    w = width_mm if aspect >= 1 else width_mm * aspect
    w = min(w, max_mm) if aspect >= 1 else w
    px = 0.1
    cols = max(8, round(w / px))
    rows = max(8, round(cols / aspect))
    if rows * px > max_mm:
        rows = round(max_mm / px)
        cols = max(8, round(rows * aspect))
    return _from_mask(np.pad(load_mask(path, rows, cols), 2), px)


def _flower(scale: float) -> tuple[CrossSection, CrossSection]:
    """Motivo de ejemplo: flor geométrica (color 2) con centro y puntos (color 3)."""
    def ell(r, sy, ang, dist):
        return CrossSection.circle(r, 64).scale((1, sy)).translate((dist, 0)).rotate(ang)
    petals = CrossSection.batch_boolean([ell(13, 0.55, i * 45, 30) for i in range(8)] + [CrossSection.circle(22, 96)], 0)
    holes = CrossSection.batch_boolean([ell(6, 0.5, i * 45, 31) for i in range(8)] + [CrossSection.circle(15, 96)], 0)
    c2 = petals - holes
    c3 = CrossSection.batch_boolean([CrossSection.circle(11, 96)] +
                                    [CrossSection.circle(2.6, 32).translate((25, 0)).rotate(i * 45 + 22.5) for i in range(8)], 0)
    return c2.scale((scale, scale)), c3.scale((scale, scale))


def _centroid(cs: CrossSection) -> tuple[float, float]:
    a = cx = cy = 0.0
    for loop in cs.to_polygons():
        pts = np.asarray(loop)
        x, y = pts[:, 0], pts[:, 1]
        x1, y1 = np.roll(x, -1), np.roll(y, -1)
        cross = x * y1 - x1 * y
        a += cross.sum() / 2
        cx += ((x + x1) * cross).sum() / 6
        cy += ((y + y1) * cross).sum() / 6
    return (cx / a, cy / a) if a else (0.0, 0.0)


def motifs(p: CoasterParams) -> tuple[CrossSection, CrossSection]:
    """Regiones de los colores 2 y 3, ya recortadas al contorno interior y sin solaparse con el borde."""
    inner = outline(p, p.margin_mm + (p.rim_mm if p.mode == "relieve" else 0))
    b = inner.bounds()
    room = min(b[2] - b[0], b[3] - b[1])
    if p.motif == "demo":
        c2, c3 = _flower(room / 92)
    elif p.motif == "texto":
        c2 = text_section(p.text2, p.text_mm, 0.9 * (b[2] - b[0]))
        c3 = text_section(p.text3, p.text_mm * 0.6, 0.8 * (b[2] - b[0]))
        if not c2.is_empty() and not c3.is_empty():   # el texto 3 debajo del 2
            h2 = c2.bounds()[3] - c2.bounds()[1]
            h3 = c3.bounds()[3] - c3.bounds()[1]
            gap = 0.35 * p.text_mm
            c2 = c2.translate((0, (h3 + gap) / 2))
            c3 = c3.translate((0, -(h2 + gap) / 2))
    else:
        w = p.motif_mm or room * 0.85
        c2 = mask_section(p.mask2, w, room) if p.mask2 else CrossSection()
        c3 = mask_section(p.mask3, w * 0.5, room) if p.mask3 else CrossSection()
    if p.colors < 3:
        c3 = CrossSection()
    # El motivo, en el centro de la forma (en el triángulo y la gota no es el centro de la caja) y, si no
    # cabe, más pequeño hasta que quepa entero.
    both = c2 + c3
    if not both.is_empty():
        bb = both.bounds()
        cx, cy = _centroid(inner)
        move = (cx - (bb[0] + bb[2]) / 2, cy - (bb[1] + bb[3]) / 2)
        c2, c3, both = c2.translate(move), c3.translate(move), both.translate(move)
        for _ in range(30):
            if (both - inner).area() <= 1e-3 * both.area():
                break
            c2, c3, both = (x.translate((-cx, -cy)).scale((0.93, 0.93)).translate((cx, cy)) for x in (c2, c3, both))
    c2 = c2 ^ inner
    c3 = c3 ^ inner
    return c2, c3


@dataclass
class Coaster:
    parts: list[tuple[str, int, Manifold]]   # (nombre, filamento en Orca, sólido) en su sitio de impresión
    whole: Manifold                          # la pieza entera (relieve: lo que se lamina)
    changes: list[tuple[float, int]]         # cambios por altura para Orca (relieve)
    first_layer: float
    face_down: bool                          # incrustado: la cara vista va contra la cama


def _union(parts) -> Manifold:
    # Las partes vacías (un color sin motivo) se dejan fuera: unidas, anularían el resultado.
    return Manifold.batch_boolean([m for _, _, m in parts], OpType.Add) if len(parts) > 1 else parts[0][2]


def build(p: CoasterParams) -> Coaster:
    if p.shape not in SHAPES:
        raise ValueError(f"Forma desconocida: {p.shape}")
    c2, c3 = motifs(p)
    if c2.is_empty() and c3.is_empty():
        raise ValueError("El motivo está vacío: escribe un texto o elige una silueta")
    n = p.colors
    if p.mode == "incrustado":
        t, e, bev = p.thickness_mm, p.inlay_mm, min(p.bevel_mm, p.thickness_mm / 3)
        body = Manifold.batch_hull([outline(p, bev).extrude(0.01), outline(p).extrude(t - bev).translate((0, 0, bev))])
        m2 = (c2 - c3).mirror((1, 0))     # en espejo: al dar la vuelta a la pieza se lee bien
        m3 = c3.mirror((1, 0))
        col2 = body ^ m2.extrude(e)
        col3 = body ^ m3.extrude(e)
        col1 = body - (m2 + m3).extrude(e + 1).translate((0, 0, -1))
        # Filamentos: el motivo primero y el fondo el último, para que en la capa mixta Orca acabe con el
        # fondo y siga con él hasta arriba.
        parts = [("color1", n, col1), ("color2", 1, col2)] + ([("color3", 2, col3)] if n >= 3 else [])
        parts = [q for q in parts if not q[2].is_empty()]
        return Coaster(parts, _union(parts), [], min(e, 0.3), True)

    t, a2, a3 = snap(p.thickness_mm), snap(p.relief2_mm), snap(p.relief3_mm)
    col1 = outline(p).extrude(t)
    top = t + a2 + (a3 if n >= 3 and not c3.is_empty() else 0)
    if p.rim_mm > 0:
        rim_h = snap(top + p.rim_up_mm)
        col1 = col1 + (outline(p) - outline(p, p.rim_mm)).extrude(rim_h)
    col2 = (c2 + c3).extrude(a2).translate((0, 0, t))
    col3 = c3.extrude(a3).translate((0, 0, t + a2))
    parts = [("color1", 1, col1), ("color2", 2, col2)] + ([("color3", 3, col3)] if n >= 3 and not c3.is_empty() else [])
    changes = [(round(t + LAYER, 3), 2)] + ([(round(t + a2 + LAYER, 3), 3)] if n >= 3 and not c3.is_empty() else [])
    parts = [q for q in parts if not q[2].is_empty()]
    return Coaster(parts, _union(parts), changes, LAYER, False)


def resin_ml(p: CoasterParams, c: Coaster) -> float:
    """Resina para enrasar el borde (relieve con borde): hueco dentro del borde hasta su altura, en ml."""
    if p.mode != "relieve" or p.rim_mm <= 0:
        return 0.0
    b = c.whole.bounding_box()
    h = b[5] - b[2]
    cavity = outline(p, p.rim_mm).extrude(h) - c.whole
    return max(0.0, cavity.volume()) / 1000
