"""Conversión de una imagen en un mapa de grosor (mm por vértice)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageOps


@dataclass
class FlatParams:
    width_mm: float = 150.0
    min_mm: float = 0.8
    max_mm: float = 3.0
    mm_per_px: float = 0.2
    border_mm: float = 3.0
    brightness: float = 1.0
    contrast: float = 1.0
    gamma: float = 1.0
    invert: bool = False
    rotate: int = 0                                         # giro en grados, en el sentido del reloj
    crop: tuple[float, float, float, float] | None = None   # recorte x, y, ancho, alto en fracciones (tras girar)


ROTATIONS = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}


def _adjusted(path: str, p: FlatParams) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path))
    if p.rotate in ROTATIONS:
        img = img.transpose(ROTATIONS[p.rotate])
    if p.crop is not None:
        x, y, w, h = p.crop
        box = (round(x * img.width), round(y * img.height), round((x + w) * img.width), round((y + h) * img.height))
        if box[2] - box[0] >= 2 and box[3] - box[1] >= 2:
            img = img.crop(box)
    img = img.convert("L")
    if p.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(p.brightness)
    if p.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(p.contrast)
    return img


def _finish(img: Image.Image, p: FlatParams) -> np.ndarray:
    gray = np.asarray(img, dtype=np.float64) / 255.0
    if p.gamma != 1.0:
        gray = gray ** p.gamma
    if p.invert:
        gray = 1.0 - gray
    return gray


def crop_window(img_w: int, img_h: int, aspect: float, zoom: float = 1.0,
                center: tuple[float, float] = (0.5, 0.5)) -> tuple[float, float, float, float]:
    """Trozo de la foto (x, y, ancho, alto en píxeles) que ocupa una pieza de proporción `aspect` (ancho/alto).

    Con zoom 1 es el mayor rectángulo de esa proporción que cabe en la foto; más zoom lo reduce y menos de 1
    lo hace mayor que la foto (la foto queda más pequeña que la pieza). `center` es el punto de la foto, en
    fracciones, que cae en el centro de la pieza; el trozo puede salirse de la foto.
    """
    if img_w / img_h > aspect:
        h = img_h / zoom
        w = h * aspect
    else:
        w = img_w / zoom
        h = w / aspect
    return center[0] * img_w - w / 2, center[1] * img_h - h / 2, w, h


def _ramp(n: int, start: float, size: float, feather: float, lo_open: bool, hi_open: bool) -> np.ndarray:
    """Peso 0..1 de la foto a lo largo de un eje: sube en `feather` celdas desde cada borde de la foto que
    cae dentro de la pieza; los bordes que quedan fuera no difuminan nada."""
    i = np.arange(n) + 0.5
    inside = (i >= start) & (i <= start + size)
    lo = np.full(n, np.inf) if lo_open else (i - start) / feather
    hi = np.full(n, np.inf) if hi_open else (start + size - i) / feather
    return np.where(inside, np.clip(np.minimum(lo, hi), 0, 1), 0.0)


def place_photo(img: Image.Image, p: FlatParams, cols: int, rows: int, x: float, y: float, w: float,
                background: np.ndarray, feather_frac: float = 0.03) -> np.ndarray:
    """Coloca en una rejilla rows × cols la foto ya ajustada, con el trozo que empieza en (x, y) y mide `w`
    píxeles de ancho ocupando toda la rejilla. Lo que no tapa la foto se queda con `background`, con un
    fundido suave en los bordes de la foto que caen dentro de la pieza."""
    s = cols / w                                  # celdas de rejilla por píxel de foto
    left, top, pw, ph = -x * s, -y * s, img.width * s, img.height * s
    j0, j1 = max(0, int(np.floor(left))), min(cols, int(np.ceil(left + pw)))
    i0, i1 = max(0, int(np.floor(top))), min(rows, int(np.ceil(top + ph)))
    gray = background.astype(np.float64).copy()
    if j1 <= j0 or i1 <= i0:
        return gray
    box = (max(0.0, (j0 - left) / s), max(0.0, (i0 - top) / s),
           min(img.width, (j1 - left) / s), min(img.height, (i1 - top) / s))
    photo = _finish(img.resize((j1 - j0, i1 - i0), Image.LANCZOS, box=box), p)
    feather = max(1.0, feather_frac * min(pw, ph))
    ax = _ramp(cols, left, pw, feather, left <= 0.5, left + pw >= cols - 0.5)[j0:j1]
    ay = _ramp(rows, top, ph, feather, top <= 0.5, top + ph >= rows - 0.5)[i0:i1]
    alpha = ay[:, None] * ax[None, :]
    gray[i0:i1, j0:j1] = alpha * photo + (1 - alpha) * gray[i0:i1, j0:j1]
    return gray


def load_gray(path: str, p: FlatParams, wrap: bool = False, aspect: float | None = None,
              zoom: float = 1.0, center: tuple[float, float] = (0.5, 0.5), fill="liso") -> np.ndarray:
    """Carga la imagen, aplica ajustes básicos y la escala a la resolución de impresión.

    `aspect` (ancho/alto de la pieza, por defecto el de la foto), `zoom` y `center` encuadran la foto; lo que
    no tape se rellena con `fill` (ver textures.py). Devuelve valores 0..1 donde 1 es blanco (fino, deja pasar luz).
    """
    from litofania.textures import flat_fill

    img = _adjusted(path, p)
    if wrap:   # cilindro: la imagen da la vuelta completa, sin marco en los lados
        cols = max(8, round(p.width_mm / p.mm_per_px))
    else:
        cols = max(2, round((p.width_mm - 2 * p.border_mm) / p.mm_per_px) + 1)
    if aspect is None and zoom == 1.0 and tuple(center) == (0.5, 0.5):
        rows = max(2, round(cols * img.height / img.width))
        return _finish(img.resize((cols, rows), Image.LANCZOS), p)
    aspect = aspect or img.width / img.height
    rows = max(2, round(cols / aspect))
    x, y, w, _ = crop_window(img.width, img.height, cols / rows, zoom, center)
    return place_photo(img, p, cols, rows, x, y, w, flat_fill(fill, rows, cols, p.mm_per_px))


def sphere_gray(path: str, p: FlatParams, cols: int, rows: int, lat_top: float, lat_bottom: float,
                fit: str = "centrada", coverage_deg: float = 150.0, fill="liso") -> np.ndarray:
    """Rejilla de grises (rows × cols) que cubre la esfera: longitudes completas, latitudes de arriba abajo.

    «panoramica» estira la imagen a toda la esfera (ideal para fotos 2:1). «centrada» coloca la foto
    delante, en el ecuador, ocupando `coverage_deg` grados de ancho y manteniendo su proporción; el
    resto lleva el relleno `fill` (liso, luna o textura, ver textures.py). «relleno» deja solo el relleno, sin foto.
    """
    from litofania.textures import sphere_fill

    img = _adjusted(path, p)
    if fit == "panoramica":
        return _finish(img.resize((cols, rows), Image.LANCZOS), p)

    lats = np.linspace(lat_top, lat_bottom, rows)
    lons = 2 * np.pi * np.arange(cols) / cols - np.pi        # como en shapes.build_sphere
    background = sphere_fill(fill, lats, lons, cols * p.mm_per_px / (2 * np.pi))
    if fit == "relleno":
        return background

    w = max(2, min(cols, round(cols * coverage_deg / 360)))
    h = max(2, min(rows, round(w * img.height / img.width)))
    # Fila del ecuador: las filas van de lat_top a lat_bottom en pasos iguales.
    eq = round((lat_top / (lat_top - lat_bottom)) * (rows - 1)) if lat_bottom < 0 else rows - 1 - h // 2
    r0 = int(np.clip(eq - h // 2, 0, rows - h))
    c0 = (cols - w) // 2
    k = img.width / w                                     # píxeles de foto por celda
    return place_photo(img, p, cols, rows, -c0 * k, -r0 * k, cols * k, background)


def thickness_map(gray: np.ndarray, p: FlatParams, wrap: bool = False) -> np.ndarray:
    """Oscuro = grueso, claro = fino. Añade el marco a grosor máximo.

    Con `wrap` (cilindro) el marco va solo arriba y abajo: los lados se cierran entre sí.
    """
    t = p.min_mm + (1.0 - gray) * (p.max_mm - p.min_mm)
    pad = round(p.border_mm / p.mm_per_px)
    if pad > 0:
        t = np.pad(t, ((pad, pad), (0, 0) if wrap else (pad, pad)), mode="constant", constant_values=p.max_mm)
    return t
