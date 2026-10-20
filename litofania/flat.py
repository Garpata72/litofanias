"""Malla cerrada de una litofanía plana a partir de un mapa de grosor."""
from __future__ import annotations

import numpy as np

from litofania.shapes import build_solid


def flat_mesh(t: np.ndarray, mm_per_px: float) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (vértices Nx3, caras Mx3) de un sólido estanco.

    La cara trasera está en z=0 y el relieve en z=t. La fila 0 de la imagen queda arriba (y máxima).
    """
    s = build_solid(t, mm_per_px, "plana")
    return s.verts, s.faces
