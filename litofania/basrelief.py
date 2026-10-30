"""Bajorrelieve a partir de un mapa de profundidad: compresión en el gradiente y vista con luz rasante.

Un mapa de profundidad no se puede escalar sin más a 2 mm de alto: la forma global (una cabeza entera)
se come toda la altura y el detalle (ojos, pelo) desaparece. Aquí se atenúan las pendientes grandes con
una curva logarítmica, se conservan las pequeñas y se reconstruye la superficie resolviendo una ecuación
de Poisson con la FFT. Solo usa numpy.
"""
from __future__ import annotations

import numpy as np


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Desenfoque gaussiano de `sigma` píxeles (FFT con bordes en espejo)."""
    if sigma <= 0:
        return a.copy()
    rows, cols = a.shape
    pad = min(int(3 * sigma) + 1, rows - 1, cols - 1)
    big = np.pad(a, pad, mode="reflect")
    fy = np.fft.fftfreq(big.shape[0])[:, None]
    fx = np.fft.rfftfreq(big.shape[1])[None, :]
    kernel = np.exp(-2 * (np.pi * sigma) ** 2 * (fx**2 + fy**2))
    out = np.fft.irfft2(np.fft.rfft2(big) * kernel, s=big.shape)
    return out[pad:pad + rows, pad:pad + cols]


def normalize(a: np.ndarray, lo: float = 1.0, hi: float = 99.0, mask: np.ndarray | None = None) -> np.ndarray:
    """Lleva `a` a 0..1 recortando por los percentiles `lo`-`hi` (dentro de `mask` si se da)."""
    vals = a[mask] if mask is not None else a
    p0, p1 = np.percentile(vals, [lo, hi])
    return np.clip((a - p0) / max(p1 - p0, 1e-9), 0.0, 1.0)


def poisson(div: np.ndarray) -> np.ndarray:
    """Superficie cuyo laplaciano es `div`, con bordes de derivada nula (reflejo + FFT)."""
    rows, cols = div.shape
    big = np.block([[div, div[:, ::-1]], [div[::-1, :], div[::-1, ::-1]]])
    ky = 2 * np.cos(2 * np.pi * np.arange(2 * rows) / (2 * rows))[:, None] - 2
    kx = 2 * np.cos(2 * np.pi * np.arange(2 * cols) / (2 * cols))[None, :] - 2
    denom = kx + ky
    denom[0, 0] = 1.0
    spec = np.fft.fft2(big) / denom
    spec[0, 0] = 0.0
    return np.real(np.fft.ifft2(spec))[:rows, :cols]


def compress(depth: np.ndarray, depth_px: float = 60.0, alpha: float = 4.0, cut: float = 3.0,
             detail: float = 0.0, detail_src: np.ndarray | None = None) -> np.ndarray:
    """Relieve 0..1 a partir de `depth` (0..1, 1 = cerca).

    `depth_px` es la profundidad total de la escena medida en píxeles (cuánto «sobresale» la cara frente
    al fondo a esta resolución); `alpha` la fuerza de la compresión (0 = ninguna); las pendientes
    mayores que `cut` (saltos de silueta) se anulan. `detail` (0..1) suma el paso alto de `detail_src`
    (normalmente la foto en grises) para recuperar pelo, tela o grabados que el modelo suaviza.
    """
    h = depth * depth_px
    gx = np.zeros_like(h)
    gy = np.zeros_like(h)
    gx[:, :-1] = h[:, 1:] - h[:, :-1]
    gy[:-1, :] = h[1:, :] - h[:-1, :]
    for g in (gx, gy):
        g[np.abs(g) > cut] = 0.0
        if alpha > 0:
            g[:] = np.sign(g) * np.log1p(alpha * np.abs(g)) / alpha
    div = gx.copy()
    div[:, 1:] -= gx[:, :-1]
    div += gy
    div[1:, :] -= gy[:-1, :]
    rel = normalize(poisson(div), 0.5, 99.5)
    if detail > 0 and detail_src is not None:
        sigma = max(depth.shape) / 200
        hp = detail_src - blur(detail_src, sigma)
        rel = rel + detail * hp / max(np.percentile(np.abs(hp), 99), 1e-9) * 0.1
        rel = normalize(rel, 0.2, 99.8)
    return rel


def shade(height_mm: np.ndarray, mm_per_px: float, azimuth_deg: float = 135.0, elevation_deg: float = 30.0,
          tint: tuple[float, float, float] = (0.86, 0.68, 0.42)) -> np.ndarray:
    """Imagen RGB 0..255 del relieve iluminado con luz rasante (por defecto desde arriba a la izquierda)."""
    dzdx = np.gradient(height_mm, axis=1) / mm_per_px
    dzdy = np.gradient(height_mm, axis=0) / mm_per_px
    n = np.stack([-dzdx, dzdy, np.ones_like(dzdx)], axis=-1)      # y de la imagen hacia abajo → hacia arriba
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    az, el = np.radians(azimuth_deg), np.radians(elevation_deg)
    light = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    lum = 0.18 + 0.82 * np.clip(n @ light, 0.0, 1.0)
    rgb = lum[..., None] * np.array(tint)[None, None, :]
    return np.clip(rgb * 255, 0, 255).astype(np.uint8)
