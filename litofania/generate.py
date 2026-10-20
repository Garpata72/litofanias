"""Generación de litofanías completas, compartida por la línea de comandos y la API."""
from __future__ import annotations

from dataclasses import dataclass

from litofania.flat import flat_mesh
from litofania.heightmap import FlatParams, load_gray, thickness_map
from litofania.stl import write_stl


@dataclass
class Result:
    width_mm: float
    height_mm: float
    depth_mm: float
    triangles: int


def generate_flat(image_path: str, out_path: str, p: FlatParams) -> Result:
    t = thickness_map(load_gray(image_path, p), p)
    verts, faces = flat_mesh(t, p.mm_per_px)
    write_stl(out_path, verts, faces)
    return Result(
        width_mm=(t.shape[1] - 1) * p.mm_per_px,
        height_mm=(t.shape[0] - 1) * p.mm_per_px,
        depth_mm=p.max_mm,
        triangles=len(faces),
    )
