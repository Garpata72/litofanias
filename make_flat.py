"""Fase 0: convierte una imagen en una litofanía plana STL.

Uso: python make_flat.py foto.jpg salida.stl --ancho 150
"""
from __future__ import annotations

import argparse
import time

from litofania.generate import generate_flat
from litofania.heightmap import FlatParams


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera una litofanía plana en STL.")
    ap.add_argument("imagen")
    ap.add_argument("salida")
    ap.add_argument("--ancho", type=float, default=150.0, help="ancho total en mm (con marco)")
    ap.add_argument("--min", type=float, default=0.8, help="grosor mínimo en mm (zonas claras)")
    ap.add_argument("--max", type=float, default=3.0, help="grosor máximo en mm (zonas oscuras)")
    ap.add_argument("--resolucion", type=float, default=0.2, help="mm por píxel")
    ap.add_argument("--marco", type=float, default=3.0, help="ancho del marco en mm (0 = sin marco)")
    ap.add_argument("--brillo", type=float, default=1.0)
    ap.add_argument("--contraste", type=float, default=1.0)
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--invertir", action="store_true")
    a = ap.parse_args()

    p = FlatParams(
        width_mm=a.ancho, min_mm=a.min, max_mm=a.max, mm_per_px=a.resolucion,
        border_mm=a.marco, brightness=a.brillo, contrast=a.contraste,
        gamma=a.gamma, invert=a.invertir,
    )
    t0 = time.perf_counter()
    r = generate_flat(a.imagen, a.salida, p)
    print(f"{a.salida}: {r.width_mm:.1f} x {r.height_mm:.1f} x {r.depth_mm:.1f} mm, "
          f"{r.triangles:,} triángulos, {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
