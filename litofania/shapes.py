"""Sólidos cerrados de litofanía sobre distintas superficies.

Toda litofanía es la misma rejilla de grosores colocada sobre una superficie: plana, un arco
(segmento de cilindro) o un cilindro completo. La cara trasera es lisa y el relieve queda en la
cara delantera; en las piezas curvas la trasera es la cara exterior (convexa) y el relieve va
por dentro, donde está la luz.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SHAPES = ("plana", "arco", "cilindro", "esfera", "cupula")


@dataclass
class Solid:
    verts: np.ndarray
    faces: np.ndarray
    radius_mm: float | None = None   # radio exterior de las piezas curvas; eje en x = y = 0 (esfera: centro en el origen)


def _place(t: np.ndarray, mm_per_px: float, shape: str, angle_deg: float):
    """Devuelve las coordenadas (rows, cols, 3) de la cara delantera y la trasera."""
    rows, cols = t.shape
    v = (rows - 1 - np.arange(rows))[:, None] * mm_per_px * np.ones((1, cols))
    if shape == "plana":
        u = np.arange(cols)[None, :] * mm_per_px * np.ones((rows, 1))
        front = np.stack([u, v, t], axis=-1)
        back = np.stack([u, v, np.zeros_like(t)], axis=-1)
        return front, back, None

    if shape == "cilindro":
        radius = cols * mm_per_px / (2 * np.pi)
        a = 2 * np.pi * np.arange(cols) / cols - np.pi   # centro de la imagen en +y, la costura detrás
    elif shape == "arco":
        width = (cols - 1) * mm_per_px
        radius = width / np.radians(angle_deg)
        a = (np.arange(cols) * mm_per_px - width / 2) / radius
    else:
        raise ValueError(f"Forma desconocida: {shape}")
    a = a[None, :] * np.ones((rows, 1))

    def ring(r):   # -sin: la imagen se lee bien mirando desde fuera (cara convexa), con la luz dentro
        return np.stack([-r * np.sin(a), r * np.cos(a), v], axis=-1)

    return ring(radius - t), ring(np.full_like(t, radius)), radius


def build_solid(t: np.ndarray, mm_per_px: float, shape: str = "plana", angle_deg: float = 120.0,
                mask: np.ndarray | None = None) -> Solid:
    """`mask` (solo plana) recorta la pieza: se quedan los cuadros con sus cuatro esquinas dentro."""
    if mask is not None:
        return _masked_flat(t, mm_per_px, mask)
    rows, cols = t.shape
    closed = shape == "cilindro"
    front, back, radius = _place(t, mm_per_px, shape, angle_deg)
    n = rows * cols
    verts = np.vstack([front.reshape(-1, 3), back.reshape(-1, 3)])

    idx = np.arange(n).reshape(rows, cols)
    right = np.roll(idx, -1, axis=1) if closed else idx[:, 1:]
    left = idx if closed else idx[:, :-1]
    v00, v01 = left[:-1].ravel(), right[:-1].ravel()
    v10, v11 = left[1:].ravel(), right[1:].ravel()
    front_faces = np.vstack([
        np.column_stack([v10, v11, v01]),
        np.column_stack([v10, v01, v00]),
    ])
    back_faces = front_faces[:, ::-1] + n

    # Paredes: cada arista del borde de la cara delantera (en el sentido en que la recorren sus
    # triángulos) se une con su copia trasera. En el cilindro solo hay borde arriba y abajo.
    a = [left[-1], right[0]]          # abajo de izquierda a derecha, arriba de derecha a izquierda
    b = [right[-1], left[0]]
    if not closed:
        a += [idx[1:, -1], idx[:-1, 0]]   # lado derecho hacia arriba, izquierdo hacia abajo
        b += [idx[:-1, -1], idx[1:, 0]]
    a, b = np.concatenate(a), np.concatenate(b)
    walls = np.vstack([
        np.column_stack([b, a, a + n]),
        np.column_stack([b, a + n, b + n]),
    ])

    faces = np.vstack([front_faces, back_faces, walls]).astype(np.int64)
    if signed_volume(verts, faces) < 0:
        faces = faces[:, ::-1].copy()
    return Solid(verts, faces, radius)


def signed_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    tri = verts[faces]
    return float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6)


def sphere_lats(radius: float, shape: str, hole_mm: float, mm_per_px: float) -> tuple[float, float]:
    """Latitudes (radianes) de la primera y la última fila. Arriba se deja una fila sin llegar al
    polo, que se cierra con una tapa; abajo queda la abertura para la luz (la cúpula, en el ecuador)."""
    lat_top = np.pi / 2 - mm_per_px / radius
    if shape == "cupula":
        return lat_top, 0.0
    return lat_top, -float(np.arccos(min(1.0, hole_mm / (2 * radius))))


def build_sphere(t: np.ndarray, radius: float, lat_top: float, lat_bottom: float) -> Solid:
    """Esfera (o cúpula) con la trasera lisa por fuera y el relieve por dentro, como el cilindro.

    Las columnas dan la vuelta completa (el centro de la imagen mira a +y y la costura queda detrás);
    la fila de arriba se cierra con una tapa en el polo y la de abajo deja la abertura.
    """
    rows, cols = t.shape
    lat = np.linspace(lat_top, lat_bottom, rows)[:, None] * np.ones((1, cols))
    lon = (2 * np.pi * np.arange(cols) / cols - np.pi)[None, :] * np.ones((rows, 1))

    def shell(r):
        return np.stack([-r * np.cos(lat) * np.sin(lon), r * np.cos(lat) * np.cos(lon), r * np.sin(lat)], axis=-1)

    n = rows * cols
    pole_t = float(t[0].mean())
    verts = np.vstack([
        shell(radius - t).reshape(-1, 3),
        shell(np.full_like(t, radius)).reshape(-1, 3),
        [[0.0, 0.0, radius - pole_t], [0.0, 0.0, radius]],   # centros de las tapas: delantera y trasera
    ])
    cf, cb = 2 * n, 2 * n + 1

    idx = np.arange(n).reshape(rows, cols)
    right = np.roll(idx, -1, axis=1)
    v00, v01 = idx[:-1].ravel(), right[:-1].ravel()
    v10, v11 = idx[1:].ravel(), right[1:].ravel()
    front_faces = np.vstack([
        np.column_stack([v10, v11, v01]),
        np.column_stack([v10, v01, v00]),
    ])
    back_faces = front_faces[:, ::-1] + n

    # Abertura de abajo: pared entre la cara delantera y la trasera.
    a, b = idx[-1], right[-1]
    walls = np.vstack([np.column_stack([b, a, a + n]), np.column_stack([b, a + n, b + n])])
    # Tapa del polo: abanicos que cierran la fila de arriba, por dentro y por fuera.
    a, b = right[0], idx[0]
    caps = np.vstack([
        np.column_stack([b, a, np.full(cols, cf)]),
        np.column_stack([a + n, b + n, np.full(cols, cb)]),
    ])

    faces = np.vstack([front_faces, back_faces, walls, caps]).astype(np.int64)
    if signed_volume(verts, faces) < 0:
        faces = faces[:, ::-1].copy()
    return Solid(verts, faces, radius)


def _masked_flat(t: np.ndarray, mm_per_px: float, mask: np.ndarray) -> Solid:
    rows, cols = t.shape
    front, back, _ = _place(t, mm_per_px, "plana", 0)
    n = rows * cols
    verts = np.vstack([front.reshape(-1, 3), back.reshape(-1, 3)])

    idx = np.arange(n).reshape(rows, cols)
    keep = (mask[:-1, :-1] & mask[:-1, 1:] & mask[1:, :-1] & mask[1:, 1:]).ravel()
    v00, v01 = idx[:-1, :-1].ravel()[keep], idx[:-1, 1:].ravel()[keep]
    v10, v11 = idx[1:, :-1].ravel()[keep], idx[1:, 1:].ravel()[keep]
    front_faces = np.vstack([
        np.column_stack([v10, v11, v01]),
        np.column_stack([v10, v01, v00]),
    ])
    back_faces = front_faces[:, ::-1] + n

    # Borde del recorte: aristas de la cara delantera cuya inversa no está en ningún triángulo.
    edges = np.vstack([front_faces[:, [0, 1]], front_faces[:, [1, 2]], front_faces[:, [2, 0]]]).astype(np.int64)
    keys = edges[:, 0] * n + edges[:, 1]
    reverse = edges[:, 1] * n + edges[:, 0]
    a, b = edges[~np.isin(keys, reverse)].T
    walls = np.vstack([np.column_stack([b, a, a + n]), np.column_stack([b, a + n, b + n])])

    faces = np.vstack([front_faces, back_faces, walls]).astype(np.int64)
    if signed_volume(verts, faces) < 0:
        faces = faces[:, ::-1].copy()
    return Solid(verts, faces, None)
