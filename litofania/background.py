"""Máscara del motivo (quitar el fondo) con BiRefNet lite en ONNX, local y sin internet tras la descarga."""
from __future__ import annotations

import numpy as np
from PIL import Image

SIZE = 1024
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def subject_mask(session, rgb: Image.Image, size: tuple[int, int]) -> np.ndarray:
    """Probabilidad 0..1 de que cada píxel sea el motivo, a `size` (ancho, alto)."""
    x = np.asarray(rgb.convert("RGB").resize((SIZE, SIZE), Image.Resampling.BICUBIC), dtype=np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    logit = session.run(None, {session.get_inputs()[0].name: x})[0][0, 0]
    prob = 1.0 / (1.0 + np.exp(-logit))
    return np.asarray(Image.fromarray(prob.astype(np.float32), mode="F").resize(size, Image.Resampling.BICUBIC)).clip(0, 1)


def dominant(mask: np.ndarray, grid: int = 120) -> tuple[bool, float, float]:
    """¿Hay un motivo claro? Devuelve (sí o no, fracción de la foto que ocupa, fracción que es el trozo mayor).

    Un retrato, un animal o un objeto dan un solo trozo que ocupa entre el 3 % y el 85 % de la foto. Una foto
    que ya es un relieve (un panel con muchas figuras) da trozos sueltos o casi todo el cuadro: ahí quitar el
    fondo estropea la pieza, y es mejor dejarla entera."""
    b = np.asarray(Image.fromarray((mask > 0.5).astype(np.uint8) * 255).resize((grid, grid), Image.Resampling.BILINEAR)) > 127
    coverage = float(b.mean())
    total = int(b.sum())
    if total == 0:
        return False, coverage, 0.0
    seen = np.zeros_like(b)
    best = 0
    for y, x in zip(*np.nonzero(b)):
        if seen[y, x]:
            continue
        stack, size = [(y, x)], 0
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            size += 1
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < grid and 0 <= nx < grid and b[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        best = max(best, size)
    share = best / total
    return 0.03 <= coverage <= 0.85 and share >= 0.8, coverage, share
