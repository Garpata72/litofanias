"""Sólidos cerrados de litofanía sobre distintas superficies.

Toda litofanía es la misma rejilla de grosores colocada sobre una superficie: plana, un arco
(segmento de cilindro) o un cilindro completo. La cara trasera es lisa y el relieve queda en la
cara delantera; en las piezas curvas la trasera es la cara exterior (convexa) y el relieve va
por dentro, donde está la luz.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SHAPES = ("plana", "arco", "cilindro", "cono", "esfera", "cupula")


@dataclass
class Lamp:
    """Cilindro o lámpara cónica: radios exteriores abajo y arriba y ondas opcionales en la pared
    (`waves` ondas en la vuelta, de `wave_mm` de amplitud)."""
    r_bottom: float | None = None     # None: el que sale del ancho desarrollado (cilindro)
    r_top: float | None = None
    waves: int = 0
    wave_mm: float = 0.0


@dataclass
class Solid:
    verts: np.ndarray
    faces: np.ndarray
    radius_mm: float | None = None   # radio exterior de las piezas curvas; eje en x = y = 0 (esfera: centro en el origen)


def cone_height(rows: int, mm_per_px: float, r_bottom: float, r_top: float) -> float:
    """Altura vertical del cono cuya pared (la generatriz) mide lo que la foto: (rows - 1) · mm_per_px."""
    slant = (rows - 1) * mm_per_px
    dr = abs(r_bottom - r_top)
    if slant <= dr * 1.05:
        raise ValueError("La lámpara es demasiado baja para tanta diferencia de diámetros: usa una foto más alta o diámetros más parecidos")
    return float(np.sqrt(slant**2 - dr**2))


def _place(t: np.ndarray, mm_per_px: float, shape: str, angle_deg: float, outside: bool = False,
           lamp: Lamp | None = None):
    """Devuelve las coordenadas (rows, cols, 3) de la cara delantera (la del relieve) y la trasera.

    En las curvas, `outside` lleva el relieve a la cara convexa y deja lisa la de dentro; `radius` es
    siempre el radio exterior máximo (en el cono, el de abajo)."""
    rows, cols = t.shape
    v = (rows - 1 - np.arange(rows))[:, None] * mm_per_px * np.ones((1, cols))
    if shape == "plana":
        u = np.arange(cols)[None, :] * mm_per_px * np.ones((rows, 1))
        front = np.stack([u, v, t], axis=-1)
        back = np.stack([u, v, np.zeros_like(t)], axis=-1)
        return front, back, None

    if shape in ("cilindro", "cono"):
        a = 2 * np.pi * np.arange(cols) / cols - np.pi   # centro de la imagen en +y, la costura detrás
        lamp = lamp or Lamp()
        r_b = lamp.r_bottom or cols * mm_per_px / (2 * np.pi)
        r_t = lamp.r_top or r_b
        if shape == "cono":
            s = (rows - 1 - np.arange(rows)) / (rows - 1)                 # 0 abajo, 1 arriba
            z = cone_height(rows, mm_per_px, r_b, r_t) * s
            k = (rows - 1) * mm_per_px / z.max()                           # el grosor se mide en horizontal
        else:
            s, z, k = (rows - 1 - np.arange(rows)) / (rows - 1), v[:, 0], 1.0
            r_t = r_b
        base = (r_b + (r_t - r_b) * s)[:, None] + lamp.wave_mm * np.sin(lamp.waves * a)[None, :]
        z = z[:, None] * np.ones((1, cols))
        aa = a[None, :] * np.ones((rows, 1))

        def wall(r):
            return np.stack([-r * np.sin(aa), r * np.cos(aa), z], axis=-1)

        if outside:
            inner = base - k * t.max()
            return wall(inner + k * t), wall(inner), r_b
        return wall(base - k * t), wall(base), r_b
    elif shape == "arco":
        width = (cols - 1) * mm_per_px
        radius = width / np.radians(angle_deg)
        a = (np.arange(cols) * mm_per_px - width / 2) / radius
    else:
        raise ValueError(f"Forma desconocida: {shape}")
    a = a[None, :] * np.ones((rows, 1))

    def ring(r):   # -sin: la imagen se lee bien mirando desde fuera (cara convexa), con la luz dentro
        return np.stack([-r * np.sin(a), r * np.cos(a), v], axis=-1)

    if outside:
        inner = radius - t.max()
        return ring(inner + t), ring(np.full_like(t, inner)), radius
    return ring(radius - t), ring(np.full_like(t, radius)), radius


def build_solid(t: np.ndarray, mm_per_px: float, shape: str = "plana", angle_deg: float = 120.0,
                mask: np.ndarray | None = None, outside: bool = False, lamp: Lamp | None = None) -> Solid:
    """`mask` (solo plana) recorta la pieza: se quedan los cuadros con sus cuatro esquinas dentro.
    `outside` (arco, cilindro y cono) pone el relieve por fuera; `lamp` da los radios y las ondas."""
    if mask is not None:
        return _masked_flat(t, mm_per_px, mask)
    rows, cols = t.shape
    closed = shape in ("cilindro", "cono")
    front, back, radius = _place(t, mm_per_px, shape, angle_deg, outside, lamp)
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


def sphere_lats(radius: float, shape: str, hole_mm: float, mm_per_px: float,
                top_hole_mm: float = 0.0) -> tuple[float, float]:
    """Latitudes (radianes) de la primera y la última fila. Arriba se deja una fila sin llegar al
    polo, que se cierra con una tapa (o el agujero de arriba, si `top_hole_mm`); abajo queda la abertura
    para la luz (la cúpula, en el ecuador)."""
    lat_top = np.pi / 2 - mm_per_px / radius
    if top_hole_mm > 0:
        lat_top = min(lat_top, float(np.arccos(min(1.0, top_hole_mm / (2 * radius)))))
    if shape == "cupula":
        return lat_top, 0.0
    return lat_top, -float(np.arccos(min(1.0, hole_mm / (2 * radius))))


def build_sphere(t: np.ndarray, radius: float, lat_top: float, lat_bottom: float, outside: bool = False,
                 top_open: bool = False, neck_mm: float = 0.0, mm_per_px: float = 0.5) -> Solid:
    """Esfera (o cúpula) con la trasera lisa por fuera y el relieve por dentro, como el cilindro; con
    `outside`, al revés: lisa por dentro y el relieve por fuera.

    Las columnas dan la vuelta completa (el centro de la imagen mira a +y y la costura queda detrás);
    la fila de arriba se cierra con una tapa en el polo (o queda abierta con `top_open`) y la de abajo
    deja la abertura. `neck_mm` alarga la abertura hacia abajo con un cilindro recto, a grosor máximo,
    que encaja en la ranura de la peana y da a la esfera una base plana.
    """
    n_neck = int(np.ceil(neck_mm / mm_per_px)) if neck_mm > 0 else 0
    if n_neck:
        t = np.vstack([t, np.full((n_neck, t.shape[1]), float(t.max()))])
    rows, cols = t.shape
    lat = np.concatenate([np.linspace(lat_top, lat_bottom, rows - n_neck), np.full(n_neck, lat_bottom)])
    drop = np.concatenate([np.zeros(rows - n_neck), neck_mm * np.arange(1, n_neck + 1) / max(1, n_neck)])
    lat = lat[:, None] * np.ones((1, cols))
    drop = drop[:, None] * np.ones((1, cols))
    lon = (2 * np.pi * np.arange(cols) / cols - np.pi)[None, :] * np.ones((rows, 1))
    neck = np.arange(rows)[:, None] >= rows - n_neck

    def shell(r):
        # En el cuello, recto hacia abajo: radio horizontal el de la abertura y el grosor medido en horizontal.
        h = np.where(neck, radius * np.cos(lat_bottom) - (radius - r), r * np.cos(lat))
        z = np.where(neck, radius * np.sin(lat_bottom) - drop, r * np.sin(lat))
        return np.stack([-h * np.sin(lon), h * np.cos(lon), z], axis=-1)

    n = rows * cols
    pole_t = float(t[0].mean())
    if outside:
        inner = radius - float(t.max())
        relief, smooth, poles = shell(inner + t), shell(np.full_like(t, inner)), [inner + pole_t, inner]
    else:
        relief, smooth, poles = shell(radius - t), shell(np.full_like(t, radius)), [radius - pole_t, radius]
    verts = np.vstack([
        relief.reshape(-1, 3),
        smooth.reshape(-1, 3),
        [[0.0, 0.0, poles[0]], [0.0, 0.0, poles[1]]],   # centros de las tapas: la del relieve y la lisa
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
    # Arriba: tapa del polo (abanicos que cierran la fila de arriba, por dentro y por fuera) o, con el
    # agujero de arriba, otra pared como la de abajo.
    a, b = right[0], idx[0]
    if top_open:
        caps = np.vstack([np.column_stack([b, a, a + n]), np.column_stack([b, a + n, b + n])])
    else:
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
