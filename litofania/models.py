"""Modelos de IA locales (ONNX): dónde están, descarga única con SHA-256 y sesiones de ONNX Runtime.

Los modelos viven en la carpeta «modelos» junto a la app (o en LITOFANIAS_MODELOS). Tras descargarlos una vez,
nada necesita internet. En Windows, onnxruntime-directml usa la tarjeta gráfica sin instalar CUDA.
"""
from __future__ import annotations

import hashlib
import os
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MODELOS_DIR = Path(os.environ.get("LITOFANIAS_MODELOS", BASE / "modelos"))
HF = "https://huggingface.co/onnx-community"


@dataclass(frozen=True)
class Modelo:
    clave: str
    nombre: str
    archivo: str
    url: str
    sha256: str
    mb: int
    licencia: str
    uso: str                 # "profundidad" o "fondo": de cada uso se mantiene un solo modelo cargado en la app


MODELOS = {
    "small": Modelo("small", "Depth Anything V2 Small", "da2-small.onnx",
                    f"{HF}/depth-anything-v2-small/resolve/main/onnx/model.onnx",
                    "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c", 99, "Apache-2.0", "profundidad"),
    "large": Modelo("large", "Depth Anything V2 Large", "da2-large.onnx",
                    f"{HF}/depth-anything-v2-large/resolve/main/onnx/model.onnx",
                    "a93aa89b5e92e30e0afbe0f7c3ec692b35cfca791ae9004a190fb0ca2010e905", 1337, "CC-BY-NC-4.0 (uso personal)",
                    "profundidad"),
    "depthpro": Modelo("depthpro", "Apple Depth Pro (q4f16)", "dp-q4f16.onnx",
                       f"{HF}/DepthPro-ONNX/resolve/main/onnx/model_q4f16.onnx",
                       "714842d1e17986a6ae6bac18a7c66bd6e041aa88acf714e7b494a206cce5c2dc", 600, "Apple ML Research (uso personal)",
                       "profundidad"),
    "birefnet": Modelo("birefnet", "BiRefNet lite (quitar el fondo)", "birefnet-lite.onnx",
                       f"{HF}/BiRefNet_lite-ONNX/resolve/main/onnx/model.onnx",
                       "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333", 224, "MIT", "fondo"),
}


def path(clave: str) -> Path:
    return MODELOS_DIR / MODELOS[clave].archivo


def installed(clave: str) -> bool:
    return path(clave).exists()


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ───────── Descarga ─────────

_DOWNLOADS: dict[str, dict] = {}
_LOCK = threading.Lock()


def install(clave: str, progress=None) -> Path:
    """Descarga el modelo (si falta) y comprueba que el archivo es el esperado. Bloquea hasta terminar."""
    m = MODELOS[clave]
    dest = path(clave)
    if dest.exists():
        return dest
    MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".parcial")
    with urllib.request.urlopen(m.url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if sha256(tmp) != m.sha256:
        tmp.unlink()
        raise RuntimeError(f"El archivo descargado de {m.nombre} no coincide (SHA-256). Vuelve a intentarlo.")
    tmp.replace(dest)
    return dest


def install_async(clave: str) -> bool:
    """Empieza la descarga en segundo plano. Devuelve False si ya estaba instalado o descargándose."""
    with _LOCK:
        if installed(clave) or _DOWNLOADS.get(clave, {}).get("activo"):
            return False
        _DOWNLOADS[clave] = {"activo": True, "hecho": 0, "total": MODELOS[clave].mb << 20, "error": ""}

    def run() -> None:
        def progress(done: int, total: int) -> None:
            _DOWNLOADS[clave].update(hecho=done, total=total or _DOWNLOADS[clave]["total"])
        try:
            install(clave, progress)
        except Exception as e:  # el error se enseña en la interfaz
            _DOWNLOADS[clave]["error"] = f"{type(e).__name__}: {e}"[:200]
        finally:
            _DOWNLOADS[clave]["activo"] = False

    threading.Thread(target=run, daemon=True).start()
    return True


def state(clave: str) -> dict:
    m = MODELOS[clave]
    d = _DOWNLOADS.get(clave, {})
    return {
        "clave": clave, "nombre": m.nombre, "mb": m.mb, "licencia": m.licencia, "uso": m.uso,
        "instalado": installed(clave), "descargando": bool(d.get("activo")),
        "hecho": d.get("hecho", 0), "total": d.get("total", 0), "error": d.get("error", ""),
    }


# ───────── ONNX Runtime ─────────

def ort_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def gpu_providers() -> list[str]:
    import onnxruntime as ort
    disponibles = ort.get_available_providers()
    return [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in disponibles]


DEVICE_NAMES = {"CPUExecutionProvider": "procesador", "DmlExecutionProvider": "gráfica (DirectML)",
                "CUDAExecutionProvider": "gráfica (CUDA)"}

_SESSIONS: dict[tuple[str, bool], tuple] = {}


def session(clave: str, gpu: bool = True, evict: bool = True):
    """(sesión, proveedor) del modelo, creada una vez. Con `evict` se descarta el otro modelo del mismo uso
    (así en la app solo hay un modelo de profundidad y uno de fondo en memoria)."""
    import onnxruntime as ort
    gpu = gpu and bool(gpu_providers())
    key = (clave, gpu)
    with _LOCK:
        if key in _SESSIONS:
            return _SESSIONS[key]
        if evict:
            uso = MODELOS[clave].uso
            for k in [k for k in _SESSIONS if k != key and MODELOS[k[0]].uso == uso]:
                del _SESSIONS[k]
    so = ort.SessionOptions()
    so.log_severity_level = 3
    providers = ["CPUExecutionProvider"]
    if gpu:
        providers = gpu_providers()[:1] + providers
        so.enable_mem_pattern = False                       # lo pide DirectML
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    s = ort.InferenceSession(str(path(clave)), so, providers=providers)
    with _LOCK:
        _SESSIONS[key] = (s, s.get_providers()[0])
        return _SESSIONS[key]
