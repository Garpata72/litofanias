"""Marigold v1.1 (profundidad por difusión) como proceso aparte: la app lo lanza con el Python de .venv-marigold.

    python marigold_worker.py foto.png salida.npy [--pasos 10] [--conjunto 3] [--resolucion 768]
    python marigold_worker.py --descargar            (solo baja el modelo, unos 2,6 GB)

Escribe un mapa float32 con 1 = lo más cercano a la cámara. Solo necesita torch, diffusers, numpy y Pillow."""
from __future__ import annotations

import argparse
import sys

import numpy as np

REPO = "prs-eth/marigold-depth-v1-1"


def load(cpu: bool = False):
    import torch
    from diffusers import MarigoldDepthPipeline
    dev = "cpu" if cpu or not torch.cuda.is_available() else "cuda"
    dtype = torch.float16 if dev == "cuda" else torch.float32
    kw = {"variant": "fp16"} if dtype == torch.float16 else {}
    pipe = MarigoldDepthPipeline.from_pretrained(REPO, torch_dtype=dtype, **kw).to(dev)
    pipe.set_progress_bar_config(disable=True)
    return pipe, dev


def predict(pipe, img, steps: int = 10, ensemble: int = 3, res: int = 768) -> np.ndarray:
    """Mapa del tamaño de `img` con 1 = cerca (Marigold da 0 = cerca)."""
    import torch
    with torch.no_grad():
        out = pipe(img, num_inference_steps=steps, ensemble_size=ensemble, processing_resolution=res,
                   match_input_resolution=True, output_type="np")
    return 1.0 - np.asarray(out.prediction[0, ..., 0], dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("foto", nargs="?")
    ap.add_argument("salida", nargs="?")
    ap.add_argument("--pasos", type=int, default=10)
    ap.add_argument("--conjunto", type=int, default=3)
    ap.add_argument("--resolucion", type=int, default=768)
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--descargar", action="store_true")
    a = ap.parse_args()
    pipe, dev = load(a.cpu)
    if a.descargar:
        print(f"Marigold listo ({dev}).")
        return 0
    from PIL import Image
    d = predict(pipe, Image.open(a.foto).convert("RGB"), a.pasos, a.conjunto, a.resolucion)
    np.save(a.salida, d)
    print(dev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
