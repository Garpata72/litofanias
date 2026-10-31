"""Bajorrelieve a partir de una foto: recorte, mapa de profundidad (IA local), fondo y medalla lista para imprimir.

El mapa de profundidad y la máscara del fondo se guardan en una caché para que cambiar el tamaño, el grosor o la
forma de la pieza sea instantáneo: solo cambiar el recorte, el giro o el método vuelve a llamar a la IA."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from litofania import background, depth, models
from litofania.basrelief import aislar, compress
from litofania.heightmap import ROTATIONS, crop_window
from litofania.medal import MedalParams

WORK_PX = 800          # resolución de trabajo validada: la compresión del gradiente depende de ella
BACKGROUND = ("auto", "si", "no")


@dataclass
class ReliefParams:
    method: str = "large"          # large | small | sin-ia
    background: str = "auto"       # auto | si | no
    aspect: float = 1.0            # ancho / alto de la pieza
    rotate: int = 0
    zoom: float = 1.0
    center: tuple[float, float] = (0.5, 0.5)
    compress: float = 4.0
    detail: float = 0.15


@dataclass
class ReliefMap:
    rel: np.ndarray                # relieve 0..1, fondo liso
    depth: np.ndarray              # profundidad 0..1 (sin comprimir)
    mask: np.ndarray | None        # máscara del motivo si se ha quitado el fondo
    note: str
    device: str
    seconds: float


def default_method() -> str:
    if models.ort_available():
        for key in ("large", "small"):
            if models.installed(key):
                return key
    return "sin-ia"


def _crop(path: Path, p: ReliefParams) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if p.rotate in ROTATIONS:
        img = img.transpose(ROTATIONS[p.rotate])
    x, y, w, h = crop_window(img.width, img.height, p.aspect, max(p.zoom, 1.0), p.center)
    x = min(max(x, 0.0), img.width - w)
    y = min(max(y, 0.0), img.height - h)
    img = img.crop((round(x), round(y), round(x + w), round(y + h)))
    k = WORK_PX / max(img.size)
    return img.resize((max(8, round(img.width * k)), max(8, round(img.height * k))), Image.Resampling.LANCZOS)


def _key(path: Path, p: ReliefParams, *extra: str) -> str:
    st = path.stat()
    raw = "|".join([path.name, str(st.st_size), str(st.st_mtime_ns), str(p.rotate), f"{p.aspect:.4f}",
                    f"{max(p.zoom, 1.0):.3f}", f"{p.center[0]:.3f},{p.center[1]:.3f}", *extra])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _cached(file: Path, make) -> np.ndarray:
    if file.exists():
        try:
            return np.load(file)
        except Exception:
            pass
    a = make()
    file.parent.mkdir(parents=True, exist_ok=True)
    np.save(file, a.astype(np.float32))
    return a


def compute(path: Path, p: ReliefParams, cache_dir: Path) -> ReliefMap:
    """Relieve 0..1 de la foto recortada a la proporción de la pieza."""
    import time
    t0 = time.perf_counter()
    method = p.method
    if method != "sin-ia" and not (models.ort_available() and models.installed(method)):
        raise FileNotFoundError("Falta el modelo de profundidad: instálalo en el panel o elige «Sin IA»")
    img = _crop(path, p)
    size = img.size
    gray = np.asarray(img.convert("L"), dtype=np.float32) / 255.0

    dev = {"device": "procesador"}

    def make_depth():
        d, dev["device"], _, _ = depth.estimate(method, img, gray, size)
        return d
    d = _cached(cache_dir / f"{_key(path, p, 'depth', method)}.npy", make_depth)

    mask, note = None, ""
    if p.background != "no" and models.ort_available() and models.installed("birefnet"):
        def make_mask():
            s, _ = models.session("birefnet", False)      # en el procesador: en la gráfica compite con la profundidad
            return background.subject_mask(s, img, size)
        m = _cached(cache_dir / f"{_key(path, p, 'mask')}.npy", make_mask)
        ok, coverage, share = background.dominant(m)
        if p.background == "si" or ok:
            mask = m
            note = "fondo quitado"
        else:
            note = "sin motivo claro: se deja la foto entera"
    elif p.background == "si":
        note = "no se ha podido quitar el fondo: falta el modelo (BiRefNet)"

    rel = compress(d, depth_px=max(d.shape) / 8, alpha=p.compress, detail=p.detail, detail_src=gray)
    if mask is not None:
        rel = aislar(rel, mask)
    return ReliefMap(rel, d, mask, note, dev["device"], time.perf_counter() - t0)


def medal_params(shape: str, width: float, height: float, mm_per_px: float, base: float, relief: float,
                 rim: float, dish: float, tab: tuple[float, float] | None) -> MedalParams:
    return MedalParams(shape=shape, width_mm=width, height_mm=height, mm_per_px=mm_per_px, base_mm=base,
                       relief_mm=relief, rim_mm=rim, dish_mm=dish, tab=tab)
