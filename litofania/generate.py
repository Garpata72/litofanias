"""Generación de litofanías completas, compartida por la línea de comandos y la API."""
from __future__ import annotations

from dataclasses import dataclass

import math

import numpy as np

from dataclasses import replace

from PIL import Image

from litofania.accessories import outline_loops
from litofania.contours import contour_mask, erode, load_mask
from litofania.heightmap import FlatParams, load_gray, sphere_gray, thickness_map
from litofania.shapes import build_solid, build_sphere, signed_volume, sphere_lats
from litofania.stl import write_stl
from litofania import text as engraving


@dataclass
class Result:
    width_mm: float
    height_mm: float
    depth_mm: float
    triangles: int
    radius_mm: float | None = None
    volume_mm3: float = 0.0
    outline: list | None = None      # plana recortada: contorno en mm, para la ventana de la caja de luz


def generate(image_path: str, out_path: str, p: FlatParams, shape: str = "plana", angle_deg: float = 120.0,
             contour: str = "rectangulo", mask_path: str | None = None, zoom: float = 1.0,
             center: tuple[float, float] = (0.5, 0.5), fill="liso", text: str = "",
             text_mm: float = 8.0) -> Result:
    """`p.width_mm` es el ancho desarrollado: el ancho de la plana, la longitud del arco o el perímetro del cilindro.

    `contour` recorta la plana (corazón, círculo… o «propia» con la máscara de `mask_path`, que fija la
    proporción de la pieza); el marco sigue entonces el contorno. En la plana, `zoom` y `center` encuadran
    la foto dentro de la pieza y `fill` rellena lo que la foto no tapa (liso o luna).

    `text` se graba con `text_mm` de alto: en una franja bajo la foto o, en la plana recortada, sobre la
    parte de abajo de la pieza."""
    text = text.strip()
    text_px = text_mm / p.mm_per_px
    wrap = shape == "cilindro"
    framing = {"zoom": zoom, "center": center, "fill": fill} if shape == "plana" else {}
    if shape == "plana" and contour != "rectangulo":
        no_frame = replace(p, border_mm=0)
        aspect = None
        if contour == "propia":
            with Image.open(mask_path) as m:
                aspect = m.width / m.height
        gray = load_gray(image_path, no_frame, aspect=aspect, **framing)
        mask = load_mask(mask_path, *gray.shape) if contour == "propia" else contour_mask(*gray.shape, contour)
        if text:
            rows, cols = gray.shape
            allowed = erode(mask, round(p.border_mm / p.mm_per_px) + 2)
            gray = engraving.overlay(gray, text, text_px, rows - 1, cols // 2, allowed=allowed, max_width=round(0.7 * cols))
        outline = outline_loops(mask, p.mm_per_px)
        t = thickness_map(gray, no_frame)
        t[mask & ~erode(mask, round(p.border_mm / p.mm_per_px))] = p.max_mm
        s = build_solid(t, p.mm_per_px, shape, mask=mask)
    else:
        outline = None
        gray = load_gray(image_path, p, wrap, **framing)
        if text:
            gray = engraving.add_below(gray, text, text_px)
        t = thickness_map(gray, p, wrap)
        s = build_solid(t, p.mm_per_px, shape, angle_deg)
    write_stl(out_path, s.verts, s.faces)
    used = s.verts[np.unique(s.faces)]
    w, h, d = (used.max(axis=0) - used.min(axis=0)).tolist()
    if shape != "plana":   # en las curvas la altura va en z (se imprimen de pie)
        w, h, d = w, d, h
    return Result(width_mm=w, height_mm=h, depth_mm=d, triangles=len(s.faces), radius_mm=s.radius_mm,
                  volume_mm3=signed_volume(s.verts, s.faces), outline=outline)


def generate_sphere(image_path: str, out_path: str, p: FlatParams, shape: str, diameter_mm: float,
                    hole_mm: float = 40.0, fit: str = "centrada", coverage_deg: float = 150.0,
                    fill="liso", text: str = "", text_mm: float = 8.0) -> Result:
    """Esfera con abertura abajo o cúpula (media esfera). `diameter_mm` es el diámetro exterior.

    `text` se graba delante, cerca de la base: justo encima de la abertura o del borde de la cúpula."""
    radius = diameter_mm / 2
    lat_top, lat_bottom = sphere_lats(radius, shape, hole_mm, p.mm_per_px)
    cols = max(16, round(2 * math.pi * radius / p.mm_per_px))
    rows = max(4, round(radius * (lat_top - lat_bottom) / p.mm_per_px) + 1)
    gray = sphere_gray(image_path, p, cols, rows, lat_top, lat_bottom, fit, coverage_deg, fill)
    if text.strip():
        lift = 3.0 / radius                                   # 3 mm por encima del borde de abajo
        bottom_lat = lat_bottom + lift
        mid_lat = bottom_lat + 0.5 * (1 + 2 * engraving.MARGIN) * text_mm / radius
        row = round((lat_top - bottom_lat) / (lat_top - lat_bottom) * (rows - 1))
        gray = engraving.overlay(gray, text.strip(), text_mm / p.mm_per_px, row, cols // 2,
                                 stretch=1 / max(0.2, math.cos(mid_lat)), max_width=cols // 3)
    t = p.min_mm + (1.0 - gray) * (p.max_mm - p.min_mm)
    s = build_sphere(t, radius, lat_top, lat_bottom)
    write_stl(out_path, s.verts, s.faces)
    w, d, h = (s.verts.max(axis=0) - s.verts.min(axis=0)).tolist()
    return Result(width_mm=w, height_mm=h, depth_mm=d, triangles=len(s.faces), radius_mm=radius,
                  volume_mm3=signed_volume(s.verts, s.faces))


def generate_flat(image_path: str, out_path: str, p: FlatParams) -> Result:
    return generate(image_path, out_path, p, "plana")
