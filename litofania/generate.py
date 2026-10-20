"""Generación de litofanías completas, compartida por la línea de comandos y la API."""
from __future__ import annotations

from dataclasses import dataclass

from litofania.heightmap import FlatParams, load_gray, thickness_map
from litofania.shapes import build_solid
from litofania.stl import write_stl


@dataclass
class Result:
    width_mm: float
    height_mm: float
    depth_mm: float
    triangles: int
    radius_mm: float | None = None


def generate(image_path: str, out_path: str, p: FlatParams, shape: str = "plana", angle_deg: float = 120.0) -> Result:
    """`p.width_mm` es el ancho desarrollado: el ancho de la plana, la longitud del arco o el perímetro del cilindro."""
    wrap = shape == "cilindro"
    t = thickness_map(load_gray(image_path, p, wrap), p, wrap)
    s = build_solid(t, p.mm_per_px, shape, angle_deg)
    write_stl(out_path, s.verts, s.faces)
    w, h, d = (s.verts.max(axis=0) - s.verts.min(axis=0)).tolist()
    if shape != "plana":   # en las curvas la altura va en z (se imprimen de pie)
        w, h, d = w, d, h
    return Result(width_mm=w, height_mm=h, depth_mm=d, triangles=len(s.faces), radius_mm=s.radius_mm)


def generate_flat(image_path: str, out_path: str, p: FlatParams) -> Result:
    return generate(image_path, out_path, p, "plana")
