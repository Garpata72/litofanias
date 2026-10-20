"""Texto grabado (un nombre, una fecha…): letras finas, que se encienden, sobre una banda gruesa y oscura.

Se dibuja en la rejilla de grises antes de pasar a grosores: 0 es la banda (grosor máximo) y 1 las letras
(grosor mínimo). La fuente va incluida (DejaVu Sans Bold, licencia en fuentes/) para no depender del sistema.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).resolve().parent / "fuentes" / "DejaVuSans-Bold.ttf"
MARGIN = 0.4        # margen de la banda alrededor del texto, en alturas de texto


def coverage(text: str, height_px: float, max_width_px: float | None = None, stretch: float = 1.0) -> np.ndarray:
    """Cobertura 0..1 del texto con `height_px` de alto (de la parte más alta a la más baja de las letras).

    `stretch` ensancha en horizontal (en la esfera las filas de abajo son más cortas). Si no cabe en
    `max_width_px`, se reduce entero.
    """
    probe = ImageFont.truetype(str(FONT), 200)
    l, t, r, b = probe.getbbox(text)
    k = height_px / max(1, b - t)
    if max_width_px is not None and (r - l) * k * stretch > max_width_px:
        k = max_width_px / ((r - l) * stretch)
    font = ImageFont.truetype(str(FONT), max(4, round(200 * k)))
    l, t, r, b = font.getbbox(text)
    img = Image.new("L", (max(1, r - l), max(1, b - t)))
    ImageDraw.Draw(img).text((-l, -t), text, font=font, fill=255)
    if stretch != 1.0:
        img = img.resize((max(1, round(img.width * stretch)), img.height), Image.LANCZOS)
    return np.asarray(img, dtype=np.float64) / 255.0


def band(text: str, height_px: float, cols: int, stretch: float = 1.0, width: int | None = None) -> np.ndarray:
    """Banda (oscura) con el texto centrado; ancho `width` o el del texto más el margen."""
    m = round(MARGIN * height_px)
    limit = (width or cols) - 2 * m
    cov = coverage(text, height_px, limit, stretch)
    w = width or min(cols, cov.shape[1] + 2 * m)
    out = np.zeros((cov.shape[0] + 2 * m, w))
    c0 = (w - cov.shape[1]) // 2
    out[m:m + cov.shape[0], c0:c0 + cov.shape[1]] = cov
    return out


def add_below(gray: np.ndarray, text: str, height_px: float) -> np.ndarray:
    """Añade debajo de la foto una franja de todo el ancho con el texto."""
    return np.vstack([gray, band(text, height_px, gray.shape[1], width=gray.shape[1])])


def overlay(gray: np.ndarray, text: str, height_px: float, row: int, col: int, stretch: float = 1.0,
            allowed: np.ndarray | None = None, max_width: int | None = None) -> np.ndarray:
    """Pone la banda con el texto sobre la rejilla, centrada en la columna `col`.

    `row` es la fila de abajo de la banda. Con `allowed` (máscara de la pieza ya sin el marco) se sube la
    banda hasta que quepa entera dentro.
    """
    rows, cols = gray.shape
    b = band(text, height_px, cols, stretch, None)
    if max_width is not None and b.shape[1] > max_width:
        b = band(text, height_px * max_width / b.shape[1], cols, stretch, None)
    bh, bw = b.shape
    c0 = int(np.clip(col - bw // 2, 0, max(0, cols - bw)))
    bottom = min(row, rows - 1)
    if allowed is not None:
        while bottom - bh + 1 > 0 and not allowed[bottom - bh + 1:bottom + 1, c0:c0 + bw].all():
            bottom -= 1
    top = max(0, bottom - bh + 1)
    out = gray.copy()
    out[top:top + bh, c0:c0 + bw] = b[:bottom + 1 - top, :cols - c0]
    return out
