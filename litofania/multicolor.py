"""Foto en relieve multicolor (idea tipo HueForge) para una impresora de un solo extrusor.

Cada píxel se convierte en una altura. Se imprime con capas finas y se cambia de filamento solo a ciertas
alturas, de oscuro a claro. Los filamentos son algo translúcidos en capas finas, así que el color de abajo
se ve a través de las de arriba y salen degradados. Se mira desde arriba, no a contraluz.

Modelo de color lineal, como HueForge: un grosor t de un filamento tapa min(1, t/TD) del color que tiene
debajo. TD («transmission distance») son los mm de ese filamento a partir de los cuales ya no deja ver lo de
debajo. Valores orientativos de PLA: negro 0,3-0,6; colores oscuros 1-2; claros 2-4; blanco 2-5.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from litofania.contours import contour_mask, erode, fix_pinches
from litofania.heightmap import ROTATIONS
from litofania.shapes import Solid, _masked_flat

MAX_BRUTE = 3000        # combinaciones de cambios que se prueban todas; con más, búsqueda por coordenadas
MAX_FILAMENTS = 4
SAMPLE = 6000           # píxeles de muestra para elegir los cambios


@dataclass
class Filament:
    name: str
    color: str          # «#RRGGBB»
    td: float           # mm


DEFAULT_FILAMENTS = [Filament("negro", "#1b1b1b", 0.5), Filament("marron", "#a0602e", 1.6),
                     Filament("blanco", "#f2eee4", 3.0)]


@dataclass
class ColorParams:
    width_mm: float = 100.0
    mm_per_px: float = 0.25
    layer: float = 0.08            # altura de capa
    first: float = 0.16            # primera capa
    base_layers: int = 4           # capas de base del primer filamento, incluida la primera
    layers: int = 32               # capas máximas de relieve sobre la base
    color_weight: float = 2.0      # peso del tono (a, b de Lab) frente a la luz
    contrast: bool = False         # autocontraste
    contour: str = "rectangulo"
    contour_opts: dict = field(default_factory=dict)
    rotate: int = 0
    crop: tuple[float, float, float, float] | None = None
    starts: tuple[int, ...] | None = None   # capas de cambio puestas a mano (una por filamento, sin el primero)
    rim_mm: float = 0.0            # borde alrededor que contiene la resina UV (0 = sin borde)
    rim_up_mm: float = 0.8         # lo que sube el borde por encima del relieve más alto

    @property
    def z_base(self) -> float:
        return self.first + (self.base_layers - 1) * self.layer


@dataclass
class ColorRelief:
    z: np.ndarray                  # altura de cada vértice (mm)
    level: np.ndarray              # capas de relieve de cada vértice (0..layers)
    mask: np.ndarray
    starts: tuple[int, ...]        # capa (sobre la base) en la que empieza cada filamento; la del primero es 0
    stack_rgb: np.ndarray          # color visto desde arriba con 0..layers capas
    error: float                   # error medio en Lab (con el peso de color)
    solid: Solid

    def changes(self, p: ColorParams) -> list[tuple[float, int]]:
        """(z de arriba de la capa, filamento 1..) de cada cambio, como lo guarda Orca."""
        return [(round(p.z_base + s * p.layer, 4), i + 1) for i, s in enumerate(self.starts) if i > 0]

    def simulation(self) -> Image.Image:
        rgb = (self.stack_rgb[self.level] * 255).clip(0, 255).astype(np.uint8)
        return Image.fromarray(np.dstack([rgb, self.mask.astype(np.uint8) * 255]), "RGBA")


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255


def rgb_lab(rgb: np.ndarray, color_weight: float = 1.0) -> np.ndarray:
    """sRGB (0..1, …×3) → CIELAB, con a y b multiplicados por `color_weight`."""
    c = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, color_weight * 500 * (f[..., 0] - f[..., 1]),
                     color_weight * 200 * (f[..., 1] - f[..., 2])], -1)


def stack_colors(fils: list[Filament], starts: tuple[int, ...], layers: int, layer: float) -> np.ndarray:
    """Color visto desde arriba con 0..layers capas sobre la base. starts[i] = primera capa del filamento i."""
    rgb = [hex_rgb(f.color) for f in fils]
    k = np.arange(layers + 1, dtype=float)
    col = np.tile(rgb[0], (layers + 1, 1))      # base opaca del primer filamento
    for i in range(1, len(fils)):
        end = starts[i + 1] - 1 if i + 1 < len(fils) else layers
        t = (np.minimum(k, end) - starts[i] + 1) * layer
        o = np.clip(t / fils[i].td, 0, 1)[:, None]
        col = col * (1 - o) + rgb[i] * o
    return col


def _error(sample: np.ndarray, weights: np.ndarray, fils, starts, layers, layer, cw) -> float:
    stack = rgb_lab(stack_colors(fils, starts, layers, layer), cw)
    d = ((sample[:, None, :] - stack[None, :, :]) ** 2).sum(-1).min(1)
    return float((d * weights).sum() / weights.sum())


def choose_starts(sample: np.ndarray, weights: np.ndarray, fils, layers: int, layer: float, cw: float) -> tuple[int, ...]:
    """Las capas de cambio que mejor reproducen la muestra. Con pocas combinaciones las prueba todas; con
    muchas, mueve cada cambio por turnos a su mejor sitio (desde varios puntos de partida)."""
    k = len(fils) - 1
    err = lambda cuts: _error(sample, weights, fils, (0,) + tuple(cuts), layers, layer, cw)
    if math.comb(layers, k) <= MAX_BRUTE:
        best = min(itertools.combinations(range(1, layers + 1), k), key=err)
        return (0,) + tuple(best)
    best, best_e = None, math.inf
    for spread in (0.5, 0.75, 1.0):
        cuts = [max(1, round((i + 1) * spread * layers / (k + 1))) for i in range(k)]
        cuts = sorted(set(min(layers, c + j) for j, c in enumerate(cuts)))
        while len(cuts) < k:
            cuts.append(cuts[-1] + 1)
        e = err(cuts)
        for _ in range(12):
            moved = False
            for i in range(k):
                lo = cuts[i - 1] + 1 if i else 1
                hi = cuts[i + 1] - 1 if i + 1 < k else layers
                for c in range(lo, hi + 1):
                    if c == cuts[i]:
                        continue
                    trial = cuts[:i] + [c] + cuts[i + 1:]
                    te = err(trial)
                    if te < e - 1e-9:
                        cuts, e, moved = trial, te, True
            if not moved:
                break
        if e < best_e:
            best, best_e = tuple(cuts), e
    return (0,) + best


def load_rgb(path: str, p: ColorParams) -> np.ndarray:
    """Foto girada, recortada y escalada a la rejilla de la pieza (un píxel por vértice)."""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if p.rotate in ROTATIONS:
        img = img.transpose(ROTATIONS[p.rotate])
    if p.crop is not None:
        x, y, w, h = p.crop
        box = (round(x * img.width), round(y * img.height), round((x + w) * img.width), round((y + h) * img.height))
        if box[2] - box[0] >= 2 and box[3] - box[1] >= 2:
            img = img.crop(box)
    cols = max(8, int(round(p.width_mm / p.mm_per_px)) + 1)
    rows = max(8, int(round(cols * img.height / img.width)))
    img = img.resize((cols, rows), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    if p.contrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    return np.asarray(img, float) / 255


def nearest_level(lab: np.ndarray, stack_lab: np.ndarray, chunk: int = 200_000) -> np.ndarray:
    """Para cada píxel, la capa cuyo color simulado se le parece más (por trozos, para no gastar memoria)."""
    flat = lab.reshape(-1, 3)
    out = np.empty(len(flat), dtype=np.int64)
    for i in range(0, len(flat), chunk):
        d = ((flat[i:i + chunk, None, :] - stack_lab[None, :, :]) ** 2).sum(-1)
        out[i:i + chunk] = d.argmin(1)
    return out.reshape(lab.shape[:-1])


def build(path: str, fils: list[Filament], p: ColorParams) -> ColorRelief:
    if not 2 <= len(fils) <= MAX_FILAMENTS:
        raise ValueError(f"Hacen falta entre 2 y {MAX_FILAMENTS} filamentos")
    rgb = load_rgb(path, p)
    rows, cols = rgb.shape[:2]
    mask = np.ones((rows, cols), dtype=bool) if p.contour == "rectangulo" else \
        fix_pinches(contour_mask(rows, cols, p.contour, **p.contour_opts))
    lab = rgb_lab(rgb, p.color_weight)

    if p.starts is not None:
        starts = (0,) + tuple(p.starts)
        if len(starts) != len(fils) or any(b <= a for a, b in zip(starts, starts[1:])) or starts[-1] > p.layers:
            raise ValueError(f"Pon {len(fils) - 1} capas de cambio, de menor a mayor, entre 1 y {p.layers}")
    else:
        # Muestra: colores cuantizados con su peso, así cuentan igual los grandes fondos y pesa poco el cálculo.
        inside = lab[mask]
        q = np.round(inside / 3).astype(np.int64)
        _, idx, counts = np.unique(q, axis=0, return_index=True, return_counts=True)
        if len(idx) > SAMPLE:
            keep = np.random.default_rng(0).choice(len(idx), SAMPLE, replace=False, p=counts / counts.sum())
            idx, counts = idx[keep], np.ones(SAMPLE)
        starts = choose_starts(inside[idx], counts.astype(float), fils, p.layers, p.layer, p.color_weight)

    stack_lab = rgb_lab(stack_colors(fils, starts, p.layers, p.layer), p.color_weight)
    level = nearest_level(lab, stack_lab)
    d = ((lab - stack_lab[level]) ** 2).sum(-1)
    error = float(np.sqrt(d[mask].mean()))
    # Borde para la resina: un muro con el último filamento, por encima del relieve más alto.
    top = p.layers
    if p.rim_mm > 0:
        top = p.layers + max(1, round(p.rim_up_mm / p.layer))
        ring = mask & ~erode(mask, max(1, round(p.rim_mm / p.mm_per_px)))
        level = np.where(ring, top, level)
    stack = stack_colors(fils, starts, top, p.layer)
    z = p.z_base + level * p.layer
    solid = _masked_flat(z, p.mm_per_px, mask)
    return ColorRelief(z=z, level=level, mask=mask, starts=starts, stack_rgb=stack, error=error, solid=solid)
