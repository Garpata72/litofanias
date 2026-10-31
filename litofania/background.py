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
