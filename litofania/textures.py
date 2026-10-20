"""Rellenos para la parte de la pieza que no tapa la foto: liso, superficie lunar (mares y cráteres) o una
textura propia subida como imagen.

Todo se calcula en el espacio 3D de la pieza, así la luna de la esfera no tiene costura ni se deforma
en los polos, y la textura sale igual a cualquier resolución (vista previa, visor y STL).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

FILLS = ("liso", "luna", "textura")
PLAIN = 0.85        # gris del relleno liso: claro, deja pasar bastante luz
SEED = 7


def _value_noise(p: np.ndarray, perm: np.ndarray, vals: np.ndarray) -> np.ndarray:
    """Ruido de valor 3D suave (0..1) en los puntos `p` (N × 3)."""
    i = np.floor(p).astype(np.int64)
    f = p - i
    f = f * f * (3 - 2 * f)

    def corner(dx, dy, dz):
        h = perm[(perm[(perm[(i[:, 0] + dx) & 255] + i[:, 1] + dy) & 255] + i[:, 2] + dz) & 255]
        return vals[h]

    x0 = corner(0, 0, 0) * (1 - f[:, 0]) + corner(1, 0, 0) * f[:, 0]
    x1 = corner(0, 1, 0) * (1 - f[:, 0]) + corner(1, 1, 0) * f[:, 0]
    x2 = corner(0, 0, 1) * (1 - f[:, 0]) + corner(1, 0, 1) * f[:, 0]
    x3 = corner(0, 1, 1) * (1 - f[:, 0]) + corner(1, 1, 1) * f[:, 0]
    y0 = x0 * (1 - f[:, 1]) + x1 * f[:, 1]
    y1 = x2 * (1 - f[:, 1]) + x3 * f[:, 1]
    return y0 * (1 - f[:, 2]) + y1 * f[:, 2]


def _fbm(p: np.ndarray, noise: tuple, octaves: int, scale: float) -> np.ndarray:
    total, amp, norm = np.zeros(len(p)), 1.0, 0.0
    for o in range(octaves):
        total += amp * _value_noise(p * scale * 2**o + 17.3 * o, *noise)
        norm += amp
        amp *= 0.5
    return total / norm


LIGHT = np.array([-0.55, 0.45, 0.70]) / np.linalg.norm([-0.55, 0.45, 0.70])


def _base(points: np.ndarray) -> np.ndarray:
    """Suelo lunar sin cráteres: grano fino y mares oscuros de baja frecuencia."""
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(256)
    noise = (np.concatenate([perm, perm]), rng.random(256))
    g = 0.76 + 0.20 * (_fbm(points, noise, 5, 4.0) - 0.5)
    maria = _fbm(points + 40.0, noise, 4, 0.9)
    return g - 0.26 * np.clip((maria - 0.47) / 0.10, 0, 1)


def _crater(pts: np.ndarray, c: np.ndarray, r: float, bright: bool) -> np.ndarray:
    """Cambio de gris de un cráter: hondonada con borde levantado, sombreada como si la luz viniera de un lado."""
    v = (pts - c) / r
    d = np.linalg.norm(v, axis=-1)
    u = v / np.maximum(d, 1e-6)[..., None]
    rim = np.exp(-(((d - 1.0) / 0.2) ** 2))
    # Perfil: hondonada 0,8·(d² - 1) dentro y borde 0,3·rim; su pendiente da el sombreado (n·L).
    slope = np.where(d < 1, 1.6 * d, 0.0) - 15.0 * (d - 1.0) * rim
    shade = -slope * (u @ LIGHT)
    delta = 0.09 * shade - np.where(d < 0.9, 0.05, 0.0)
    if bright:   # cráter joven: halo claro alrededor
        delta += 0.12 * np.exp(-((d / 2.2) ** 2))
    return delta * np.clip(r / 0.05, 0.4, 1.0)


def _crater_list(rng: np.random.Generator, n: int, rmin: float, rmax: float):
    """Tamaños en ley de potencia: muchos pequeños y pocos grandes, de mayor a menor."""
    r = rmin * (1 - rng.random(n)) ** (-1 / 1.4)
    r = np.sort(r[r < rmax])[::-1]
    return r, rng.random(len(r)) < 0.08


def sphere_moon(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Luna sobre la esfera: rejilla (len(lats) × len(lons)) en radianes, longitudes de -π a π."""
    la, lo = np.meshgrid(lats, lons, indexing="ij")
    pts = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    g = _base(pts.reshape(-1, 3)).reshape(la.shape)

    rng = np.random.default_rng(SEED + 1)
    radii, bright = _crater_list(rng, 1400, 0.012, 0.16)
    v = rng.normal(size=(len(radii), 3))
    centers = v / np.linalg.norm(v, axis=1, keepdims=True)
    for c, r, b in zip(centers, radii, bright):
        reach = 2.4 * r if b else 1.5 * r          # radio angular donde el cráter cambia algo
        clat, clon = np.arcsin(np.clip(c[2], -1, 1)), np.arctan2(c[1], c[0])
        ri = np.nonzero(np.abs(lats - clat) < reach)[0]
        if not len(ri):
            continue
        coslat = np.cos(np.clip(np.abs(clat) + reach, 0, np.pi / 2))
        dlon = np.pi if coslat < 1e-3 else reach / coslat
        ci = np.nonzero(np.abs((lons - clon + np.pi) % (2 * np.pi) - np.pi) < dlon)[0]
        win = np.ix_(ri, ci)
        g[win] += _crater(pts[win], c, r, b)
    return np.clip(g, 0.0, 1.0)


def flat_moon(rows: int, cols: int, span: float = 1.7, lon0: float = -0.9) -> np.ndarray:
    """Luna sobre una pieza plana: un trozo de la misma luna de la esfera, de `span` radianes en el lado
    mayor y centrado en la longitud `lon0`, una zona con mares."""
    half = (max(rows, cols) - 1) / 2
    k = span / 2 / half
    lats = (np.arange(rows) - (rows - 1) / 2)[::-1] * k
    lons = lon0 + (np.arange(cols) - (cols - 1) / 2) * k
    return sphere_moon(lats, lons)


TEXTURE_MAX_PX = 1024


@dataclass(frozen=True)
class Fill:
    """Relleno elegido. Para «textura»: `path` (PNG en gris ya preparado), `tile_mm` (ancho de cada repetición),
    `strength` (1 = relieve original, más = más marcado, 0 = liso), `invert` y `mono` (blanco y negro)."""
    kind: str = "liso"
    path: str | None = None
    tile_mm: float = 40.0
    strength: float = 1.0
    invert: bool = False
    mono: bool = False


def as_fill(fill: "Fill | str") -> Fill:
    return fill if isinstance(fill, Fill) else Fill(fill)


def prepare_texture(img: Image.Image) -> Image.Image:
    """Imagen subida → textura en gris: sin transparencia (sobre blanco), contraste estirado y como mucho
    TEXTURE_MAX_PX de lado. Lo mejor es una imagen cuadrada «sin costuras» (seamless) de 512 a 1024 px."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(white, rgba)
    gray = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    if max(gray.size) > TEXTURE_MAX_PX:
        k = TEXTURE_MAX_PX / max(gray.size)
        gray = gray.resize((max(1, round(gray.width * k)), max(1, round(gray.height * k))), Image.LANCZOS)
    return gray


def _texture(fill: Fill) -> np.ndarray:
    t = np.asarray(Image.open(fill.path).convert("L"), dtype=np.float64) / 255.0
    if fill.invert:
        t = 1.0 - t
    if fill.mono:
        t = (t >= t.mean()).astype(np.float64)
    return t


def _sample(tex: np.ndarray, u_mm: np.ndarray, v_mm: np.ndarray, tile_mm: float) -> np.ndarray:
    """Muestra la textura repetida (bilineal) en coordenadas en mm; `tile_mm` es el ancho de una repetición."""
    h, w = tex.shape
    x = (u_mm / tile_mm * w) % w
    y = (v_mm / (tile_mm * h / w) * h) % h
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    x0, y0 = x0 % w, y0 % h
    top = tex[y0, x0] * (1 - fx) + tex[y0, x1] * fx
    bottom = tex[y1, x0] * (1 - fx) + tex[y1, x1] * fx
    return top * (1 - fy) + bottom * fy


def _relief(g: np.ndarray, tex: np.ndarray, strength: float) -> np.ndarray:
    """Aumenta o reduce el relieve alrededor del gris medio de la textura."""
    m = tex.mean()
    return np.clip(m + (g - m) * strength, 0.0, 1.0)


def texture_flat(fill: Fill, rows: int, cols: int, mm_per_px: float) -> np.ndarray:
    tex = _texture(fill)
    u = np.arange(cols)[None, :] * mm_per_px * np.ones((rows, 1))
    v = np.arange(rows)[:, None] * mm_per_px * np.ones((1, cols))
    return _relief(_sample(tex, u, v, fill.tile_mm), tex, fill.strength)


def texture_sphere(fill: Fill, lats: np.ndarray, lons: np.ndarray, radius: float) -> np.ndarray:
    """Textura sobre la esfera con proyección triplanar: sin costura ni estiramiento en los polos."""
    tex = _texture(fill)
    la, lo = np.meshgrid(lats, lons, indexing="ij")
    n = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    p = n * radius
    w = np.abs(n) ** 4
    w /= w.sum(axis=-1, keepdims=True)
    g = (w[..., 0] * _sample(tex, p[..., 1], -p[..., 2], fill.tile_mm)
         + w[..., 1] * _sample(tex, p[..., 0], -p[..., 2], fill.tile_mm)
         + w[..., 2] * _sample(tex, p[..., 0], p[..., 1], fill.tile_mm))
    return _relief(g, tex, fill.strength)


def flat_fill(fill: "Fill | str", rows: int, cols: int, mm_per_px: float = 0.2) -> np.ndarray:
    fill = as_fill(fill)
    if fill.kind == "luna":
        return flat_moon(rows, cols)
    if fill.kind == "textura" and fill.path:
        return texture_flat(fill, rows, cols, mm_per_px)
    return np.full((rows, cols), PLAIN)


def sphere_fill(fill: "Fill | str", lats: np.ndarray, lons: np.ndarray, radius: float) -> np.ndarray:
    fill = as_fill(fill)
    if fill.kind == "luna":
        return sphere_moon(lats, lons)
    if fill.kind == "textura" and fill.path:
        return texture_sphere(fill, lats, lons, radius)
    return np.full((len(lats), len(lons)), PLAIN)
