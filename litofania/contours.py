"""Contornos para recortar la litofanía plana: rectángulo, esquinas redondeadas, círculo, óvalo y corazón.

Las mismas fórmulas están en app/static/app.js para la vista previa; si se cambia una, cambiar la otra.
"""
from __future__ import annotations

import numpy as np

CONTOURS = ("rectangulo", "redondeado", "circulo", "ovalo", "corazon")


def contour_mask(rows: int, cols: int, contour: str) -> np.ndarray:
    """Máscara booleana (rows × cols): True dentro de la pieza. La fila 0 es la de arriba."""
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
        y = (v + 1) / 2 * 2.27 - 1.02
        return (x**2 + y**2 - 1) ** 3 - x**2 * y**3 <= 0
    raise ValueError(f"Contorno desconocido: {contour}")


def erode(mask: np.ndarray, steps: int) -> np.ndarray:
    """Encoge la máscara `steps` píxeles (fuera de la rejilla cuenta como vacío)."""
    m = mask.copy()
    for _ in range(steps):
        inner = np.zeros_like(m)
        inner[1:-1, 1:-1] = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
        m = inner
    return m
