"""Generación de litofanías completas, compartida por la línea de comandos y la API."""
from __future__ import annotations

from dataclasses import dataclass

import math

import numpy as np

from dataclasses import replace

from PIL import Image

from litofania.contours import contour_mask, erode, load_mask
from litofania.heightmap import FlatParams, load_gray, sphere_gray, thickness_map
from litofania.shapes import build_solid, build_sphere, sphere_lats
from litofania.stl import write_stl


@dataclass
class Result:
    width_mm: float
    height_mm: float
    depth_mm: float
    triangles: int
    radius_mm: float | None = None


def generate(image_path: str, out_path: str, p: FlatParams, shape: str = "plana", angle_deg: float = 120.0,
             contour: str = "rectangulo", mask_path: str | None = None, zoom: float = 1.0,
             center: tuple[float, float] = (0.5, 0.5)) -> Result:
    """`p.width_mm` es el ancho desarrollado: el ancho de la plana, la longitud del arco o el perímetro del cilindro.

    `contour` recorta la plana (corazón, círculo… o «propia» con la máscara de `mask_path`, que fija la
    proporción de la pieza); el marco sigue entonces el contorno. En la plana, `zoom` y `center` encuadran
    la foto dentro de la pieza."""
    wrap = shape == "cilindro"
    framing = {"zoom": zoom, "center": center} if shape == "plana" else {}
    if shape == "plana" and contour != "rectangulo":
        no_frame = replace(p, border_mm=0)
        aspect = None
        if contour == "propia":
            with Image.open(mask_path) as m:
                aspect = m.width / m.height
        t = thickness_map(load_gray(image_path, no_frame, aspect=aspect, **framing), no_frame)
        mask = load_mask(mask_path, *t.shape) if contour == "propia" else contour_mask(*t.shape, contour)
        t[mask & ~erode(mask, round(p.border_mm / p.mm_per_px))] = p.max_mm
        s = build_solid(t, p.mm_per_px, shape, mask=mask)
    else:
        t = thickness_map(load_gray(image_path, p, wrap, **framing), p, wrap)
        s = build_solid(t, p.mm_per_px, shape, angle_deg)
    write_stl(out_path, s.verts, s.faces)
    used = s.verts[np.unique(s.faces)]
    w, h, d = (used.max(axis=0) - used.min(axis=0)).tolist()
    if shape != "plana":   # en las curvas la altura va en z (se imprimen de pie)
        w, h, d = w, d, h
    return Result(width_mm=w, height_mm=h, depth_mm=d, triangles=len(s.faces), radius_mm=s.radius_mm)


def generate_sphere(image_path: str, out_path: str, p: FlatParams, shape: str, diameter_mm: float,
                    hole_mm: float = 40.0, fit: str = "centrada", coverage_deg: float = 150.0) -> Result:
    """Esfera con abertura abajo o cúpula (media esfera). `diameter_mm` es el diámetro exterior."""
    radius = diameter_mm / 2
    lat_top, lat_bottom = sphere_lats(radius, shape, hole_mm, p.mm_per_px)
    cols = max(16, round(2 * math.pi * radius / p.mm_per_px))
    rows = max(4, round(radius * (lat_top - lat_bottom) / p.mm_per_px) + 1)
    gray = sphere_gray(image_path, p, cols, rows, lat_top, lat_bottom, fit, coverage_deg)
    t = p.min_mm + (1.0 - gray) * (p.max_mm - p.min_mm)
    s = build_sphere(t, radius, lat_top, lat_bottom)
    write_stl(out_path, s.verts, s.faces)
    w, d, h = (s.verts.max(axis=0) - s.verts.min(axis=0)).tolist()
    return Result(width_mm=w, height_mm=h, depth_mm=d, triangles=len(s.faces), radius_mm=radius)


def generate_flat(image_path: str, out_path: str, p: FlatParams) -> Result:
    return generate(image_path, out_path, p, "plana")
