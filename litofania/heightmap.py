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


def load_gray(path: str, p: FlatParams, wrap: bool = False) -> np.ndarray:
    """Carga la imagen, aplica ajustes básicos y la escala a la resolución de impresión.

    Devuelve valores 0..1 donde 1 es blanco (zona fina, deja pasar luz).
    """
    img = ImageOps.exif_transpose(Image.open(path)).convert("L")
    if p.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(p.brightness)
    if p.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(p.contrast)

    if wrap:   # cilindro: la imagen da la vuelta completa, sin marco en los lados
        cols = max(8, round(p.width_mm / p.mm_per_px))
    else:
        cols = max(2, round((p.width_mm - 2 * p.border_mm) / p.mm_per_px) + 1)
    rows = max(2, round(cols * img.height / img.width))
    img = img.resize((cols, rows), Image.LANCZOS)

    gray = np.asarray(img, dtype=np.float64) / 255.0
    if p.gamma != 1.0:
        gray = gray ** p.gamma
    if p.invert:
        gray = 1.0 - gray
    return gray


def thickness_map(gray: np.ndarray, p: FlatParams, wrap: bool = False) -> np.ndarray:
    """Oscuro = grueso, claro = fino. Añade el marco a grosor máximo.

    Con `wrap` (cilindro) el marco va solo arriba y abajo: los lados se cierran entre sí.
    """
    t = p.min_mm + (1.0 - gray) * (p.max_mm - p.min_mm)
    pad = round(p.border_mm / p.mm_per_px)
    if pad > 0:
        t = np.pad(t, ((pad, pad), (0, 0) if wrap else (pad, pad)), mode="constant", constant_values=p.max_mm)
    return t
