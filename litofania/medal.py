"""Medalla o moneda en bajorrelieve: base plana, relieve de la foto, aro liso y pestaña opcional para colgar.

Parte de un relieve 0..1 (basrelief.compress, con el fondo ya liso) y devuelve el mapa de grosor y la
máscara de la forma, que cierra shapes._masked_flat. Todo en milímetros; la cara trasera queda plana en z=0.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from litofania.contours import add_tab, contour_mask, fix_pinches
from litofania.shapes import Solid, _masked_flat

SHAPES = ("circulo", "ovalo", "redondeado", "escudo")
RIM_OVER = 0.2          # el aro sobresale tanto por encima del relieve más alto, para protegerlo


@dataclass
class MedalParams:
    shape: str = "circulo"
    width_mm: float = 50.0
    height_mm: float = 50.0
    mm_per_px: float = 0.1
    base_mm: float = 2.0
    relief_mm: float = 1.6
    rim_mm: float = 2.5
    fade_mm: float = 1.0                       # el relieve baja hasta 0 en esta distancia antes del aro
    dish_mm: float = 0.0                       # campo ligeramente cóncavo, como las monedas reales
    zoom: float = 1.0                          # >1 acerca la foto
    center: tuple[float, float] = (0.5, 0.5)   # punto de la foto (fracciones x, y) que queda en el centro
    tab: tuple[float, float] | None = None     # (ancho, agujero) en mm de la pestaña para colgar


def shield_mask(rows: int, cols: int) -> np.ndarray:
    """Escudo: lados rectos arriba y fondo en punta suave; ocupa toda la rejilla."""
    u = np.linspace(-1, 1, cols)[None, :]
    v = np.linspace(1, -1, rows)[:, None]
    k = 1.5
    t = np.clip((0.15 - v) / 1.15, 0.0, 1.0)                 # 0 en la parte recta, 1 en la punta
    half = (1.0 - t**k) ** (1.0 / k)
    top = 1.0 - 0.06 * np.abs(u) ** 3                        # esquinas de arriba algo redondeadas
    return (np.abs(u) <= half) & (v <= top)


def shape_mask(shape: str, rows: int, cols: int) -> np.ndarray:
    if shape not in SHAPES:
        raise ValueError(f"Forma desconocida: {shape}")
    m = shield_mask(rows, cols) if shape == "escudo" else contour_mask(rows, cols, shape)
    return fix_pinches(m)


def _distance_exact(mask: np.ndarray, max_px: float) -> np.ndarray:
    """Distancia euclídea (en píxeles) de cada píxel de `mask` al borde, exacta hasta `max_px`; más lejos vale max_px+1."""
    R = int(np.ceil(max_px))
    outside = np.pad(~mask, R, constant_values=True)
    rows, cols = mask.shape
    offsets = sorted(((dy, dx) for dy in range(-R, R + 1) for dx in range(-R, R + 1) if 0 < dy * dy + dx * dx <= max_px**2 + 1),
                     key=lambda o: o[0] ** 2 + o[1] ** 2)
    dist = np.full(mask.shape, max_px + 1.0)
    todo = mask.copy()
    # Un píxel dista del borde lo que el píxel de fuera más cercano menos medio píxel; el contiguo al borde, 0,5.
    near = outside[R + 1:R + 1 + rows, R:R + cols] | outside[R - 1:R - 1 + rows, R:R + cols] \
        | outside[R:R + rows, R + 1:R + 1 + cols] | outside[R:R + rows, R - 1:R - 1 + cols]
    dist[todo & near] = 0.5
    todo &= ~near
    for dy, dx in offsets:
        if not todo.any():
            break
        hit = outside[R + dy:R + dy + rows, R + dx:R + dx + cols] & todo
        if hit.any():
            dist[hit] = np.hypot(dy, dx) - 0.5
            todo &= ~hit
    dist[~mask] = 0.0
    return dist


def distance_inside(mask: np.ndarray, max_px: float, budget: int = 40) -> np.ndarray:
    """Como _distance_exact, pero si el alcance pasa de `budget` píxeles se calcula en una rejilla más gruesa
    (el coste crece con el cuadrado del alcance) y se escala: el error es de unos pocos píxeles de la rejilla fina."""
    f = int(np.ceil(max_px / budget))
    if f <= 1:
        return _distance_exact(mask, max_px)
    rows, cols = mask.shape
    small = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize(
        (-(-cols // f), -(-rows // f)), Image.Resampling.BOX)) >= 128
    d = _distance_exact(small, max_px / f) * f
    full = np.asarray(Image.fromarray(d.astype(np.float32), mode="F").resize((cols, rows), Image.Resampling.BILINEAR))
    full = np.minimum(full, max_px + 1.0)
    full[~mask] = 0.0
    return full


def fit_photo(rel: np.ndarray, rows: int, cols: int, zoom: float = 1.0, center: tuple[float, float] = (0.5, 0.5)) -> np.ndarray:
    """Recorta `rel` a la proporción de la medalla (cubriéndola) y la escala a rows × cols."""
    h, w = rel.shape
    aspect = cols / rows
    cw, ch = (h * aspect, h) if w / h >= aspect else (w, w / aspect)
    cw, ch = cw / max(zoom, 1e-6), ch / max(zoom, 1e-6)
    x0 = min(max(center[0] * w - cw / 2, 0), w - cw)
    y0 = min(max(center[1] * h - ch / 2, 0), h - ch)
    img = Image.fromarray(rel.astype(np.float32), mode="F").crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch)))
    return np.asarray(img.resize((cols, rows), Image.Resampling.BICUBIC)).clip(0.0, 1.0)


def build(rel: np.ndarray, p: MedalParams) -> tuple[np.ndarray, np.ndarray, float]:
    """Mapa de grosor (mm), máscara de la forma y milímetros que la pestaña añade por arriba."""
    cols = int(round(p.width_mm / p.mm_per_px)) + 1
    rows = int(round(p.height_mm / p.mm_per_px)) + 1
    mask = shape_mask(p.shape, rows, cols)
    top = p.base_mm + p.relief_mm + RIM_OVER
    photo = fit_photo(rel, rows, cols, p.zoom, p.center)

    d_mm = distance_inside(mask, (p.rim_mm + p.fade_mm) / p.mm_per_px + 1) * p.mm_per_px
    fade = np.clip((d_mm - p.rim_mm) / max(p.fade_mm, 1e-6), 0.0, 1.0)
    t = p.base_mm + p.relief_mm * photo * fade
    if p.dish_mm > 0:
        far = distance_inside(mask, min(rows, cols) / 2 + 1) * p.mm_per_px
        rho = 1.0 - np.clip(far / max(far.max(), 1e-6), 0.0, 1.0)
        t = t - p.dish_mm * (1.0 - rho**2) * fade
    t = np.where(d_mm <= p.rim_mm, top, t)

    extra = 0.0
    if p.tab is not None:
        t, mask, extra = add_tab(t, mask, p.mm_per_px, p.tab[0], p.tab[1], top)
    return t, mask, extra


def medal(rel: np.ndarray, p: MedalParams) -> Solid:
    t, mask, _ = build(rel, p)
    return _masked_flat(t, p.mm_per_px, mask)
