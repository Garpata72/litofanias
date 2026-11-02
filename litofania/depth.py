"""Mapa de profundidad de una foto: Depth Anything V2 (Small o Large) o Depth Pro en ONNX, o un método sin IA.

Todos devuelven un mapa 0..1 del tamaño pedido en el que lo más cercano a la cámara vale más."""
from __future__ import annotations

import time

import numpy as np
from PIL import Image

from litofania import models
from litofania.basrelief import blur, normalize

METHODS = ("large", "small", "sin-ia")      # de más a menos calidad; el primero instalado es el que se propone


def resize(a: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(Image.fromarray(a.astype(np.float32), mode="F").resize(size, Image.Resampling.BICUBIC))


def da2(s, rgb: Image.Image, short: int = 518, max_long: int = 2016) -> np.ndarray:
    """Depth Anything V2: lado corto a `short` px (múltiplo de 14); devuelve profundidad inversa (cerca = alto)."""
    w, h = rgb.size
    k = short / min(w, h)
    if max(w, h) * k > max_long:
        k = max_long / max(w, h)
    nw, nh = max(14, round(w * k / 14) * 14), max(14, round(h * k / 14) * 14)
    x = np.asarray(rgb.resize((nw, nh), Image.Resampling.BICUBIC), dtype=np.float32) / 255.0
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    return s.run(None, {s.get_inputs()[0].name: x})[0][0]


def depthpro(s, rgb: Image.Image) -> np.ndarray:
    """Depth Pro trabaja a 1536x1536 y da profundidad métrica (lejos = alto): se invierte."""
    x = np.asarray(rgb.resize((1536, 1536), Image.Resampling.BICUBIC), dtype=np.float32) / 255.0
    x = ((x - 0.5) / 0.5).transpose(2, 0, 1)[None].astype(np.float32)
    inp = s.get_inputs()[0]
    if "16" in inp.type:
        x = x.astype(np.float16)
    d = np.asarray(s.run(None, {inp.name: x})[0], dtype=np.float32).squeeze()
    return 1.0 / np.maximum(d, 1e-3)


def sin_ia(gray: np.ndarray) -> np.ndarray:
    """Luminancia como altura, con contraste local (tipo CLAHE) y el detalle fino realzado."""
    s = max(gray.shape) / 25
    local = (gray - blur(gray, s)) / np.sqrt(np.maximum(blur((gray - blur(gray, s)) ** 2, s), 1e-4))
    return normalize(0.6 * blur(gray, 1.0) + 0.4 * normalize(local))


def _run(clave: str, s, rgb: Image.Image) -> np.ndarray:
    return depthpro(s, rgb) if clave == "depthpro" else da2(s, rgb)


def estimate(clave: str, rgb: Image.Image, gray: np.ndarray, size: tuple[int, int], gpu: bool = True,
             evict: bool = True, warm: bool = False) -> tuple[np.ndarray, str, float, float]:
    """(mapa 0..1 de `size`, dispositivo, segundos de carga del modelo, segundos de cálculo).

    `clave` es «sin-ia» o la de un modelo instalado. Si la gráfica falla se repite en el procesador."""
    if clave == "sin-ia":
        t = time.perf_counter()
        d = normalize(resize(sin_ia(gray), size))
        return d, "procesador", 0.0, time.perf_counter() - t
    if not models.installed(clave):
        raise FileNotFoundError(f"Falta el modelo {models.MODELOS[clave].nombre}")
    t = time.perf_counter()
    for use_gpu in ((gpu, False) if gpu else (False,)):
        try:
            s, provider = models.session(clave, use_gpu, evict)
            load = time.perf_counter() - t
            if warm:
                _run(clave, s, rgb.resize((140, 140)))
            t = time.perf_counter()
            d = resize(_run(clave, s, rgb), size)
            return normalize(d), models.DEVICE_NAMES.get(provider, provider), load, time.perf_counter() - t
        except Exception:
            if not use_gpu:
                raise
            t = time.perf_counter()     # la gráfica falló: se prueba con el procesador
    raise RuntimeError("sin proveedor de cálculo")
