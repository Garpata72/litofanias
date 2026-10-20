"""Contornos para recortar la litofanía plana: rectángulo, esquinas redondeadas, círculo, óvalo, corazón
(con la punta cortada en una base plana si se quiere), estrella, polígono regular o una máscara propia
subida como imagen. También la pestaña con agujero para colgar la pieza.

Las mismas fórmulas están en app/static/app.js para la vista previa; si se cambia una, cambiar la otra.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps

CONTOURS = ("rectangulo", "redondeado", "circulo", "ovalo", "corazon", "estrella", "poligono", "propia")
MASK_MAX_PX = 2000


def polygon_points(contour: str, points: int = 5, inner: float = 0.5, sides: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """Vértices de la estrella (`points` puntas, la de arriba vertical, valles a `inner` del radio) o del
    polígono regular de `sides` lados, que siempre apoya en un lado horizontal abajo."""
    if contour == "estrella":
        k = np.arange(2 * points)
        r = np.where(k % 2 == 0, 1.0, inner)
        ang = np.pi / 2 + np.pi * k / points
    else:
        r = 1.0
        ang = -np.pi / 2 + np.pi / sides + 2 * np.pi * np.arange(sides) / sides
    return r * np.cos(ang), r * np.sin(ang)


def _inside_polygon(x: np.ndarray, y: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    """Regla par-impar: True en los puntos (x, y) que quedan dentro del polígono de vértices (px, py)."""
    inside = np.zeros(np.broadcast(x, y).shape, dtype=bool)
    for i in range(len(px)):
        xi, yi, xj, yj = px[i], py[i], px[i - 1], py[i - 1]
        if yi == yj:
            continue
        inside ^= ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
    return inside


def contour_mask(rows: int, cols: int, contour: str, points: int = 5, inner: float = 0.5, sides: int = 6,
                 flat: float = 0.0) -> np.ndarray:
    """Máscara booleana (rows × cols): True dentro de la pieza. La fila 0 es la de arriba.

    Estrella y polígono mantienen su forma y se centran en la pieza, como el círculo. `flat` (0..0,4)
    corta esa fracción de la punta del corazón para que apoye en una base plana."""
    if contour == "rectangulo":
        return np.ones((rows, cols), dtype=bool)
    u = np.linspace(-1, 1, cols)[None, :]
    v = np.linspace(1, -1, rows)[:, None]
    aspect = (cols - 1) / (rows - 1)
    if contour == "ovalo":
        return u**2 + v**2 <= 1
    if contour == "circulo":
        x, y = (u * aspect, v) if aspect >= 1 else (u, v / aspect)
        return x**2 + y**2 <= 1
    if contour == "redondeado":
        w, h = aspect, 1.0                      # medio ancho y medio alto en las mismas unidades
        r = 0.15 * 2 * min(w, h)
        x, y = np.abs(u) * w, np.abs(v) * h
        return (x <= w - r) | (y <= h - r) | ((x - (w - r)) ** 2 + (y - (h - r)) ** 2 <= r**2)
    if contour == "corazon":
        x = u * 1.16
        y = (flat + (v + 1) / 2 * (1 - flat)) * 2.27 - 1.02
        return (x**2 + y**2 - 1) ** 3 - x**2 * y**3 <= 0
    if contour in ("estrella", "poligono"):
        px, py = polygon_points(contour, points, inner, sides)
        cx, cy = (px.max() + px.min()) / 2, (py.max() + py.min()) / 2
        s = min(aspect / ((px.max() - px.min()) / 2), 1 / ((py.max() - py.min()) / 2))
        return _inside_polygon(u * aspect, v, (px - cx) * s, (py - cy) * s)
    raise ValueError(f"Contorno desconocido: {contour}")


def fix_pinches(mask: np.ndarray) -> np.ndarray:
    """Rellena los puntos donde dos cuadros de la pieza solo se tocan por una esquina (pasa en los valles
    de la estrella o en máscaras propias finas): ahí la malla no sería cerrada del todo."""
    m = mask.copy()
    for _ in range(8):
        keep = m[:-1, :-1] & m[:-1, 1:] & m[1:, :-1] & m[1:, 1:]
        a = keep[:-1, :-1] & keep[1:, 1:] & ~keep[:-1, 1:] & ~keep[1:, :-1]
        b = keep[:-1, 1:] & keep[1:, :-1] & ~keep[:-1, :-1] & ~keep[1:, 1:]
        if not (a.any() or b.any()):
            break
        add = np.zeros_like(keep)
        add[:-1, 1:] |= a                     # se añade el cuadro de arriba a la derecha (o a la izquierda)
        add[:-1, :-1] |= b
        ii, jj = np.nonzero(add)
        for di in (0, 1):
            for dj in (0, 1):
                m[ii + di, jj + dj] = True
    return m


def erode(mask: np.ndarray, steps: int) -> np.ndarray:
    """Encoge la máscara `steps` píxeles (fuera de la rejilla cuenta como vacío)."""
    m = mask.copy()
    for _ in range(steps):
        inner = np.zeros_like(m)
        inner[1:-1, 1:-1] = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
        m = inner
    return m


def prepare_mask(img: Image.Image) -> Image.Image:
    """Convierte una imagen subida en máscara: blanco dentro de la pieza, negro fuera, recortada a la figura.

    Si la imagen tiene transparencia, la pieza es lo opaco. Si no, lo oscuro; y si lo oscuro es el fondo
    (toca casi todo el borde), se invierte, así vale tanto una silueta negra sobre blanco como al revés.
    """
    img = ImageOps.exif_transpose(img)
    inside = None
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        alpha = np.asarray(img.convert("RGBA"))[..., 3]
        if alpha.min() < 128:
            inside = alpha >= 128
    if inside is None:
        inside = np.asarray(img.convert("L")) < 128
    edge = np.concatenate([inside[0], inside[-1], inside[:, 0], inside[:, -1]])
    if edge.mean() > 0.5:
        inside = ~inside
    if inside.sum() < 0.01 * inside.size:
        raise ValueError("No se distingue ninguna figura en la máscara")
    rows, cols = np.nonzero(inside)
    inside = inside[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    out = Image.fromarray(inside.astype(np.uint8) * 255)
    if max(out.size) > MASK_MAX_PX:
        k = MASK_MAX_PX / max(out.size)
        out = out.resize((max(1, round(out.width * k)), max(1, round(out.height * k))), Image.LANCZOS)
    return out


def load_mask(path: str, rows: int, cols: int) -> np.ndarray:
    """Máscara propia (ya preparada) escalada a la rejilla de la pieza."""
    img = Image.open(path).convert("L").resize((cols, rows), Image.BILINEAR)
    return np.asarray(img) >= 128


def add_tab(t: np.ndarray, mask: np.ndarray, mm_per_px: float, width_mm: float, hole_mm: float,
            thick: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Añade arriba, en el centro, una pestaña redonda de `width_mm` de ancho con un agujero de `hole_mm`
    para colgar la pieza. La pestaña es maciza (grosor `thick`) y baja hasta entrar en la pieza, así queda
    unida también en contornos con entrante arriba (el corazón) o con punta (la estrella).

    Devuelve el grosor y la máscara con las filas nuevas encima y los milímetros que crece la pieza."""
    rows, cols = t.shape
    R, r = width_mm / 2 / mm_per_px, hole_mm / 2 / mm_per_px
    extra = int(np.ceil(2 * R)) + 1
    c = (cols - 1) / 2
    # Cada columna del vástago baja hasta un par de filas dentro de la pieza, sin tapar más foto.
    first = np.where(mask.any(axis=0), np.argmax(mask, axis=0), 0)
    stem_bottom = (extra + first + 2)[None, :]
    i = np.arange(rows + extra)[:, None]
    j = np.arange(cols)[None, :]
    cy = R + 0.5
    d2 = (i - cy) ** 2 + (j - c) ** 2
    tab = (d2 <= R**2) | ((i >= cy) & (i <= stem_bottom) & (np.abs(j - c) <= R))
    hole = d2 <= r**2
    t2 = np.vstack([np.full((extra, cols), thick), t])
    m2 = np.vstack([np.zeros((extra, cols), dtype=bool), mask])
    t2[tab] = thick
    return t2, fix_pinches((m2 | tab) & ~hole), extra * mm_per_px
