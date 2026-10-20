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


def _adjusted(path: str, p: FlatParams) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path)).convert("L")
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


def load_gray(path: str, p: FlatParams, wrap: bool = False) -> np.ndarray:
    """Carga la imagen, aplica ajustes básicos y la escala a la resolución de impresión.

    Devuelve valores 0..1 donde 1 es blanco (zona fina, deja pasar luz).
    """
    img = _adjusted(path, p)
    if wrap:   # cilindro: la imagen da la vuelta completa, sin marco en los lados
        cols = max(8, round(p.width_mm / p.mm_per_px))
    else:
        cols = max(2, round((p.width_mm - 2 * p.border_mm) / p.mm_per_px) + 1)
    rows = max(2, round(cols * img.height / img.width))
    return _finish(img.resize((cols, rows), Image.LANCZOS), p)


def sphere_gray(path: str, p: FlatParams, cols: int, rows: int, lat_top: float, lat_bottom: float,
                fit: str = "centrada", coverage_deg: float = 150.0, background: float = 0.85) -> np.ndarray:
    """Rejilla de grises (rows × cols) que cubre la esfera: longitudes completas, latitudes de arriba abajo.

    «panoramica» estira la imagen a toda la esfera (ideal para fotos 2:1). «centrada» coloca la foto
    delante, en el ecuador, ocupando `coverage_deg` grados de ancho y manteniendo su proporción; el
    resto queda con un fondo claro uniforme.
    """
    img = _adjusted(path, p)
    if fit == "panoramica":
        return _finish(img.resize((cols, rows), Image.LANCZOS), p)

    w = max(2, min(cols, round(cols * coverage_deg / 360)))
    h = max(2, min(rows, round(w * img.height / img.width)))
    photo = _finish(img.resize((w, h), Image.LANCZOS), p)
    gray = np.full((rows, cols), background)
    # Fila del ecuador: las filas van de lat_top a lat_bottom en pasos iguales.
    eq = round((lat_top / (lat_top - lat_bottom)) * (rows - 1)) if lat_bottom < 0 else rows - 1 - h // 2
    r0 = int(np.clip(eq - h // 2, 0, rows - h))
    c0 = (cols - w) // 2
    gray[r0:r0 + h, c0:c0 + w] = photo
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
