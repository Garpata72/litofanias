"""Marigold desde la app: se ejecuta en su propio entorno (.venv-marigold) para no cargar la app con PyTorch."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
WORKER = BASE / "marigold_worker.py"
TIMEOUT = 1800        # la primera vez incluye la descarga del modelo (2,6 GB)


def python() -> Path | None:
    """Python del entorno de Marigold, si está preparado (con instalar_marigold.bat o probar_marigold.bat)."""
    env = os.environ.get("LITOFANIAS_MARIGOLD")
    for p in ([Path(env)] if env else []) + [BASE / ".venv-marigold" / "Scripts" / "python.exe", BASE / ".venv-marigold" / "bin" / "python"]:
        if p.exists():
            return p
    return None


def available() -> bool:
    return python() is not None and WORKER.exists()


def run(img: Image.Image, steps: int = 10, ensemble: int = 3, res: int = 768) -> tuple[np.ndarray, str]:
    """(mapa 0..1 con 1 = cerca, dispositivo)."""
    py = python()
    if py is None:
        raise FileNotFoundError("Marigold no está instalado: ejecuta instalar_marigold.bat una vez")
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "foto.png", Path(tmp) / "mapa.npy"
        img.convert("RGB").save(src)
        r = subprocess.run([str(py), str(WORKER), str(src), str(dst), "--pasos", str(steps), "--conjunto", str(ensemble),
                            "--resolucion", str(res)], capture_output=True, text=True, timeout=TIMEOUT)
        if r.returncode != 0 or not dst.exists():
            raise RuntimeError("Marigold ha fallado: " + (r.stderr.strip().splitlines() or ["sin mensaje"])[-1][:200])
        device = (r.stdout.strip().splitlines() or ["cpu"])[-1]
        return np.load(dst), "gráfica (CUDA)" if device == "cuda" else "procesador"
