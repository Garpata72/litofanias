"""Malla cerrada de una litofanía plana a partir de un mapa de grosor."""
from __future__ import annotations

import numpy as np


def flat_mesh(t: np.ndarray, mm_per_px: float) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (vértices Nx3, caras Mx3) de un sólido estanco.

    La cara trasera está en z=0 y el relieve en z=t. La fila 0 de la imagen queda arriba (y máxima).
    """
    rows, cols = t.shape
    n = rows * cols
    ys = (rows - 1 - np.arange(rows)) * mm_per_px
    xs = np.arange(cols) * mm_per_px
    gx, gy = np.meshgrid(xs, ys)
    top = np.column_stack([gx.ravel(), gy.ravel(), t.ravel()])
    bottom = top.copy()
    bottom[:, 2] = 0.0
    verts = np.vstack([top, bottom])

    idx = np.arange(n).reshape(rows, cols)
    v00 = idx[:-1, :-1].ravel()
    v01 = idx[:-1, 1:].ravel()
    v10 = idx[1:, :-1].ravel()
    v11 = idx[1:, 1:].ravel()
    top_faces = np.vstack([
        np.column_stack([v10, v11, v01]),
        np.column_stack([v10, v01, v00]),
    ])
    bottom_faces = top_faces[:, ::-1] + n

    # Contorno recorrido en sentido antihorario visto desde +z.
    loop = np.concatenate([
        idx[-1, :],            # borde inferior, izquierda a derecha
        idx[-2::-1, -1],       # borde derecho, hacia arriba
        idx[0, -2::-1],        # borde superior, derecha a izquierda
        idx[1:-1, 0],          # borde izquierdo, hacia abajo
    ])
    a = loop
    b = np.roll(loop, -1)
    walls = np.vstack([
        np.column_stack([b, a, a + n]),
        np.column_stack([b, a + n, b + n]),
    ])

    faces = np.vstack([top_faces, bottom_faces, walls]).astype(np.int64)
    return verts, faces
