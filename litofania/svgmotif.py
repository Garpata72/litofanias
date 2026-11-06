"""Motivos para el posavasos a partir de un archivo SVG, sin internet.

Se leen las formas con relleno (rectángulos, círculos, elipses, polígonos y trazados, con sus transformaciones)
y se agrupan por color de relleno. Cada color del SVG se asigna después al color 2 (el motivo), al color 3 (el
detalle) o se ignora. Los trazos sin relleno y los textos no se convierten (pasa el texto a trazados en
Inkscape: Trayecto › Objeto a trayecto); se avisa de ello.
"""
from __future__ import annotations

import math
from functools import lru_cache
from dataclasses import dataclass, field

import numpy as np
from manifold3d import CrossSection, FillRule
from svgelements import SVG, Color, Path, Shape, Text

MAX_BYTES = 5 * 1024 * 1024
MAX_POINTS = 400_000
CURVE_STEP_MM = 0.15        # separación entre puntos al aplanar curvas (en mm del SVG a tamaño real)
FILL_MARKS = ("none", "transparent")


@dataclass
class SvgColors:
    sections: dict[str, CrossSection]      # color «#rrggbb» → región, en las unidades del SVG, y hacia arriba
    areas: dict[str, float]
    width: float
    height: float
    warnings: list[str] = field(default_factory=list)


def _hex(c) -> str | None:
    if c is None:
        return None
    col = Color(c) if not isinstance(c, Color) else c
    if col.value is None or col.alpha == 0:
        return None
    return "#%02x%02x%02x" % (col.red, col.green, col.blue)


def _polygons(shape: Shape, scale: float) -> list[np.ndarray]:
    """Contornos cerrados de la forma, ya con todas sus transformaciones, con y hacia arriba."""
    out = []
    for sub in Path(shape).as_subpaths():
        sp = Path(sub)
        length = sp.length(error=1e-3)
        if not length:
            continue
        n = int(min(2000, max(24, length * scale / CURVE_STEP_MM)))
        pts = np.asarray(sp.npoint(np.linspace(0, 1, n)), dtype=float)
        if len(pts) >= 3 and np.isfinite(pts).all():
            out.append(pts * np.array([1.0, -1.0]))
    return out


@lru_cache(maxsize=8)
def read_cached(path: str, mtime: float) -> SvgColors:
    return read(path)


def read(path: str) -> SvgColors:
    from pathlib import Path as P
    if P(path).stat().st_size > MAX_BYTES:
        raise ValueError("El SVG pesa más de 5 MB")
    try:
        svg = SVG.parse(path, reify=True)
    except Exception as e:      # XML mal formado, etc.
        raise ValueError(f"No se puede leer el SVG: {e}") from None
    bb = svg.bbox()
    if not bb or not all(math.isfinite(v) for v in bb) or bb[2] - bb[0] <= 0 or bb[3] - bb[1] <= 0:
        raise ValueError("El SVG no tiene formas dibujadas (si solo tiene texto, conviértelo a trazados en Inkscape: Trayecto › Objeto a trayecto)")
    # Unidades de usuario → mm aproximados, solo para elegir la finura de las curvas.
    scale = 100.0 / max(bb[2] - bb[0], bb[3] - bb[1])
    sections: dict[str, CrossSection] = {}
    warn, strokes, texts, total = [], 0, 0, 0
    for el in svg.elements():        # en orden de pintado: lo de después tapa lo de antes
        if isinstance(el, Text):
            texts += 1
            continue
        if not isinstance(el, Shape):
            continue
        fill = _hex(el.fill)
        if fill is None:
            strokes += 1 if el.stroke is not None else 0
            continue
        rule = FillRule.EvenOdd if (getattr(el, "values", {}) or {}).get("fill-rule") == "evenodd" else FillRule.NonZero
        polys = _polygons(el, scale)
        total += sum(len(p) for p in polys)
        if total > MAX_POINTS:
            raise ValueError("El SVG es demasiado complejo: simplifícalo en Inkscape (Trayecto › Simplificar)")
        if not polys:
            continue
        region = CrossSection([p.tolist() for p in polys], rule)
        if region.is_empty():
            continue
        for other in list(sections):
            if other != fill:
                sections[other] = sections[other] - region
        sections[fill] = sections[fill] + region if fill in sections else region
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    sections = {c: sec for c, sec in sections.items() if not sec.is_empty() and sec.area() > 1e-6 * w * h}
    if not sections:
        raise ValueError("No he encontrado formas con relleno en el SVG")
    if strokes:
        warn.append(f"{strokes} forma(s) solo con contorno y sin relleno se han ignorado (en Inkscape: Trayecto › Contorno a trayecto).")
    if texts:
        warn.append(f"{texts} texto(s) se han ignorado: conviértelos a trazados (Trayecto › Objeto a trayecto).")
    areas = {c: s.area() for c, s in sections.items()}
    return SvgColors(sections, areas, w, h, warn)


def default_map(areas: dict[str, float]) -> dict[str, int]:
    """El color con más área va al color 2 y el segundo al color 3; el resto se ignora. Si el mayor ocupa
    el 60 % o más y hay otro color, se supone que es un fondo (ya es el color del posavasos) y se ignora."""
    order = sorted(areas, key=areas.get, reverse=True)
    if len(order) >= 2 and areas[order[0]] >= 0.6 * sum(areas.values()):
        order = order[1:] + order[:1]
        return {c: (2 if i == 0 else 3 if i == 1 else 0) for i, c in enumerate(order[:-1])} | {order[-1]: 0}
    return {c: (2 if i == 0 else 3 if i == 1 else 0) for i, c in enumerate(order)}


def _bounds(cs: CrossSection) -> tuple[float, float, float, float]:
    return cs.bounds()


def place(svg: SvgColors, mapping: dict[str, int], inner: CrossSection, centre: tuple[float, float],
          width_mm: float = 0.0, fit: str = "encajar", rotate: float = 0.0, dx: float = 0.0, dy: float = 0.0,
          colors: int = 3) -> tuple[CrossSection, CrossSection]:
    """Regiones de los colores 2 y 3 ya colocadas en el posavasos.

    - `encajar`: el motivo entero cabe dentro del área libre (se reduce hasta que cabe).
    - `rellenar`: cubre el área libre y se recorta por su contorno.
    `width_mm` fija el ancho del motivo (0 = el máximo que cabe); `rotate` en grados; `dx`, `dy` lo mueven
    después de encajarlo (lo que se salga del área libre se recorta)."""
    c2 = CrossSection.batch_boolean([svg.sections[c] for c, s in mapping.items() if s == 2 and c in svg.sections], 0) \
        if any(s == 2 and c in svg.sections for c, s in mapping.items()) else CrossSection()
    c3 = CrossSection.batch_boolean([svg.sections[c] for c, s in mapping.items() if s == 3 and c in svg.sections], 0) \
        if colors >= 3 and any(s == 3 and c in svg.sections for c, s in mapping.items()) else CrossSection()
    both = c2 + c3
    if both.is_empty():
        return CrossSection(), CrossSection()
    b = both.bounds()
    mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    c2, c3 = (x.translate((-mx, -my)) for x in (c2, c3))
    if rotate:
        c2, c3 = c2.rotate(rotate), c3.rotate(rotate)
    both = c2 + c3
    b = both.bounds()
    w, h = b[2] - b[0], b[3] - b[1]
    ib = inner.bounds()
    iw, ih = ib[2] - ib[0], ib[3] - ib[1]
    if width_mm > 0:
        k = width_mm / w
    elif fit == "rellenar":
        k = max(iw / w, ih / h)
    else:
        k = min(iw / w, ih / h)
    c2, c3 = (x.scale((k, k)).translate(centre) for x in (c2, c3))
    if width_mm <= 0 and fit != "rellenar":      # que quepa entera: se reduce hasta que no se salga del área libre
        both = c2 + c3
        for _ in range(40):
            if (both - inner).area() <= 1e-3 * both.area():
                break
            c2, c3, both = (x.translate((-centre[0], -centre[1])).scale((0.96, 0.96)).translate(centre) for x in (c2, c3, both))
    if dx or dy:
        c2, c3 = c2.translate((dx, dy)), c3.translate((dx, dy))
    return c2, c3
