"""Varias fotos en una pieza: celdas iguales en filas y columnas (o dando la vuelta al cilindro y a la
esfera), separadas por un borde a grosor máximo que se ve oscuro a contraluz.

Cada foto lleva su propio giro, recorte y encuadre (zoom y centro dentro de su celda); brillo, contraste,
gamma e inversión son los de la pieza. Todas las celdas tienen la proporción de la primera foto, salvo que
la pieza ya tenga una proporción fija (máscara propia), y entonces se reparten el alto.

El mismo reparto está en app/static/app.js (collageLayout) para la vista previa; si se cambia uno, cambiar el otro.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

from litofania.heightmap import FlatParams, _adjusted, crop_window, image_cols, place_photo

MAX_PHOTOS = 8


@dataclass
class Photo:
    path: str
    rotate: int = 0
    crop: tuple[float, float, float, float] | None = None
    zoom: float = 1.0
    center: tuple[float, float] = (0.5, 0.5)


def _image(ph: Photo, p: FlatParams) -> Image.Image:
    return _adjusted(ph.path, replace(p, rotate=ph.rotate, crop=ph.crop))


def grid(n: int, rows: int) -> tuple[int, int]:
    """Filas y columnas para `n` fotos en `rows` filas como mucho (sin dejar filas vacías)."""
    cols = math.ceil(n / max(1, min(rows, n)))
    return math.ceil(n / cols), cols


def layout(n: int, cols: int, rows_wanted: int, sep: float, wrap: bool, aspect: float | None = None,
           rows: int | None = None) -> tuple[int, list[tuple[int, int, int, int]]]:
    """Reparte `n` fotos en una rejilla de `cols` columnas con `sep` celdas de separación.

    Si no se da `rows`, el alto sale de que cada celda tenga la proporción `aspect`. En `wrap` (cilindro y
    esfera panorámica) también hay separación entre la última foto y la primera, y la primera queda centrada
    delante. Devuelve el alto y las casillas (fila, columna, alto, ancho) de la rejilla completa, fila a fila;
    las columnas de una casilla pueden pasarse de `cols` en `wrap` (dan la vuelta)."""
    nr, nc = grid(n, rows_wanted)
    cw = (cols - (nc if wrap else nc - 1) * sep) / nc
    if cw < 2:
        raise ValueError("Las fotos no caben: reduce la separación o pon menos fotos por fila")
    if rows is None:
        ch = cw / aspect
        rows = max(2, round(nr * ch + (nr - 1) * sep))
    ch = (rows - (nr - 1) * sep) / nr
    if ch < 2:
        raise ValueError("Las fotos no caben: reduce la separación o pon menos filas")
    off = (cols - cw) / 2 if wrap else 0.0
    slots = []
    for i in range(nr):
        for j in range(nc):
            y0, x0 = i * (ch + sep), off + j * (cw + sep)
            r0, c0 = round(y0), round(x0)
            slots.append((r0, c0, round(y0 + ch) - r0, round(x0 + cw) - c0))
    return rows, slots


def paint(region: np.ndarray, photos: list[Photo], p: FlatParams, slots: list, wrap: bool) -> np.ndarray:
    """Pone las fotos en sus casillas de `region` (que ya lleva el relleno de fondo) y deja la separación
    entre casillas a 0 (negro: grosor máximo). Las casillas sin foto conservan el relleno."""
    rows, cols = region.shape
    covered = np.zeros_like(region, dtype=bool)
    idx = []
    for r0, c0, h, w in slots:
        cj = (c0 + np.arange(w)) % cols if wrap else np.arange(c0, min(cols, c0 + w))
        idx.append((slice(r0, min(rows, r0 + h)), cj))
        covered[idx[-1][0], cj] = True
    region[~covered] = 0.0
    for ph, (ri, cj) in zip(photos, idx):
        bg = region[ri][:, cj]
        h, w = bg.shape
        img = _image(ph, p)
        x, y, ww, _ = crop_window(img.width, img.height, w / h, ph.zoom, ph.center)
        region[ri, cj] = place_photo(img, p, w, h, x, y, ww, bg)
    return region


def first_aspect(photos: list[Photo], p: FlatParams) -> float:
    img = _image(photos[0], p)
    return img.width / img.height


def collage_gray(photos: list[Photo], p: FlatParams, background, wrap: bool = False, rows_wanted: int = 1,
                 sep_mm: float = 2.0, aspect: float | None = None) -> np.ndarray:
    """Rejilla de grises de una plana, arco o cilindro con varias fotos, del mismo ancho que la de una sola
    foto (heightmap.image_cols). `aspect` fija la proporción de la pieza; `background(rows, cols)` da el relleno."""
    cols = image_cols(p, wrap)
    rows = max(2, round(cols / aspect)) if aspect else None
    rows, slots = layout(len(photos), cols, rows_wanted, sep_mm / p.mm_per_px, wrap,
                         first_aspect(photos, p), rows)
    return paint(np.array(background(rows, cols), dtype=np.float64), photos, p, slots, wrap)
