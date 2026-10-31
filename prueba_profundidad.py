"""Fase 0 de los bajorrelieves: compara métodos de mapa de profundidad con tus propias fotos.

    python prueba_profundidad.py foto1.jpg foto2.jpg ...        (o una carpeta con fotos)
    python prueba_profundidad.py --depthpro --stl fotos/

En Windows basta con arrastrar las fotos (o una carpeta) sobre probar_profundidad.bat.

Por cada foto deja en «resultados_profundidad/<foto>/» una hoja comparativa (comparativa.png) con, para
cada método, el mapa de profundidad y cómo se vería el bajorrelieve con luz rasante, más los tiempos.
Con --stl genera además una moneda de prueba de 50 mm por método para imprimir.

Los modelos se descargan una sola vez a la carpeta «modelos» (comprobando su SHA-256); después todo
funciona sin internet. Con una tarjeta gráfica en Windows se usa DirectML (onnxruntime-directml).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from litofania.background import subject_mask  # noqa: E402
from litofania.basrelief import aislar, blur, compress, normalize, shade  # noqa: E402
from litofania.contours import contour_mask  # noqa: E402
from litofania.shapes import _masked_flat  # noqa: E402
from litofania.stl import write_stl  # noqa: E402
from litofania.text import FONT  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")  # consola de Windows
    except (AttributeError, OSError):
        pass

MODELOS_DIR = BASE / "modelos"
HF = "https://huggingface.co/onnx-community"


@dataclass
class Modelo:
    nombre: str
    archivo: str
    url: str
    sha256: str
    mb: int
    licencia: str


MODELOS = {
    "small": Modelo("Depth Anything V2 Small", "da2-small.onnx",
                    f"{HF}/depth-anything-v2-small/resolve/main/onnx/model.onnx",
                    "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c", 99, "Apache-2.0"),
    "large": Modelo("Depth Anything V2 Large", "da2-large.onnx",
                    f"{HF}/depth-anything-v2-large/resolve/main/onnx/model.onnx",
                    "a93aa89b5e92e30e0afbe0f7c3ec692b35cfca791ae9004a190fb0ca2010e905", 1337, "CC-BY-NC-4.0 (uso personal)"),
    "depthpro": Modelo("Apple Depth Pro (q4f16)", "dp-q4f16.onnx",
                       f"{HF}/DepthPro-ONNX/resolve/main/onnx/model_q4f16.onnx",
                       "714842d1e17986a6ae6bac18a7c66bd6e041aa88acf714e7b494a206cce5c2dc", 600, "Apple ML Research (uso personal)"),
    "birefnet": Modelo("BiRefNet lite (quitar fondo)", "birefnet-lite.onnx",
                       f"{HF}/BiRefNet_lite-ONNX/resolve/main/onnx/model.onnx",
                       "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333", 224, "MIT"),
}

WORK_PX = 800          # lado mayor de la profundidad que se compara
COIN_MM = 50.0         # moneda de prueba
COIN_PX_MM = 0.1       # resolución de la moneda de prueba
BASE_MM, RELIEF_MM, RIM_MM = 2.0, 1.6, 2.5


# ---------------------------------------------------------------- modelos

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def asegurar_modelo(clave: str) -> Path:
    """Ruta del modelo; lo descarga la primera vez y comprueba que el archivo es el esperado."""
    m = MODELOS[clave]
    path = MODELOS_DIR / m.archivo
    if path.exists():
        return path
    MODELOS_DIR.mkdir(exist_ok=True)
    print(f"Descargando {m.nombre} ({m.mb} MB, licencia {m.licencia}). Solo esta vez...")
    tmp = path.with_suffix(".parcial")
    with urllib.request.urlopen(m.url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, -1
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            pct = done * 100 // total if total else 0
            if pct // 10 != last:
                last = pct // 10
                print(f"  {pct:3d} %  ({done >> 20} MB)", flush=True)
    if sha256(tmp) != m.sha256:
        tmp.unlink()
        raise RuntimeError(f"El archivo descargado de {m.nombre} no coincide (SHA-256). Vuelve a intentarlo.")
    tmp.replace(path)
    return path


def proveedores_gpu() -> list[str]:
    import onnxruntime as ort
    disponibles = ort.get_available_providers()
    return [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in disponibles]


def sesion(path: Path, gpu: bool):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    providers = ["CPUExecutionProvider"]
    if gpu and proveedores_gpu():
        providers = proveedores_gpu()[:1] + providers
        so.enable_mem_pattern = False                       # lo pide DirectML
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    s = ort.InferenceSession(str(path), so, providers=providers)
    return s, s.get_providers()[0]


# ---------------------------------------------------------------- métodos

@dataclass
class Resultado:
    clave: str
    titulo: str
    depth: np.ndarray | None = None
    carga_s: float = 0.0
    calculo_s: float = 0.0
    dispositivo: str = ""
    error: str = ""
    notas: list[str] = field(default_factory=list)


def _resize(a: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(Image.fromarray(a.astype(np.float32), mode="F").resize(size, Image.Resampling.BICUBIC))


def _da2(s, rgb: Image.Image, short: int, max_long: int = 2016) -> np.ndarray:
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


def _depthpro(s, rgb: Image.Image) -> np.ndarray:
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


def ejecutar(clave: str, rgb: Image.Image, gray: np.ndarray, size: tuple[int, int], cache: dict) -> Resultado:
    titulos = {
        "sin-ia": "Detalle sin IA (luminancia)",
        "small-cpu": "IA rápida: Small, procesador",
        "small-gpu": "IA rápida: Small, gráfica",
        "large": "IA calidad: Large",
        "depthpro": "Depth Pro (Apple)",
    }
    r = Resultado(clave, titulos[clave])
    try:
        if clave == "sin-ia":
            t = time.perf_counter()
            r.depth = sin_ia(gray)
            r.calculo_s, r.dispositivo = time.perf_counter() - t, "procesador"
            return r
        modelo = {"small-cpu": "small", "small-gpu": "small"}.get(clave, clave)
        gpu = clave != "small-cpu"
        key = (modelo, gpu)
        t = time.perf_counter()
        if key not in cache:
            cache[key] = sesion(asegurar_modelo(modelo), gpu)
            r.carga_s = time.perf_counter() - t
        s, prov = cache[key]
        r.dispositivo = {"CPUExecutionProvider": "procesador", "DmlExecutionProvider": "gráfica (DirectML)",
                         "CUDAExecutionProvider": "gráfica (CUDA)"}.get(prov, prov)
        if gpu and prov == "CPUExecutionProvider":
            r.notas.append("sin gráfica disponible")
        if clave == "depthpro":
            t = time.perf_counter()
            d = _resize(_depthpro(s, rgb), size)
        else:
            _da2(s, rgb.resize((140, 140)), 140)               # calentamiento, no cuenta en el tiempo
            t = time.perf_counter()
            d = _resize(_da2(s, rgb, 518), size)
        r.calculo_s = time.perf_counter() - t
        r.depth = normalize(d)
    except Exception as e:  # una prueba que falla no debe parar las demás
        r.error = f"{type(e).__name__}: {e}"[:300]
    return r


# ---------------------------------------------------------------- salida

def relieve(depth: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Relieve 0..1 con la compresión de bajorrelieve y un poco de textura de la foto."""
    return compress(depth, depth_px=max(depth.shape) / 8, alpha=4.0, detail=0.15, detail_src=gray)


def moneda(rel: np.ndarray, path: Path) -> None:
    """Moneda de prueba: círculo de 50 mm, base de 2 mm, relieve de 1,6 mm y aro liso de 2,5 mm."""
    n = int(round(COIN_MM / COIN_PX_MM)) + 1
    rows, cols = rel.shape
    side = min(rows, cols)
    sq = rel[(rows - side) // 2:(rows - side) // 2 + side, (cols - side) // 2:(cols - side) // 2 + side]
    sq = _resize(sq, (n, n))
    yy, xx = np.mgrid[0:n, 0:n]
    r_mm = np.hypot(xx - (n - 1) / 2, yy - (n - 1) / 2) * COIN_PX_MM
    radius = COIN_MM / 2
    inner = radius - RIM_MM
    fade = np.clip((inner - r_mm) / 1.0, 0, 1)                    # el relieve baja en 1 mm antes del aro
    t = BASE_MM + RELIEF_MM * np.clip(sq, 0, 1) * fade
    t = np.where(r_mm > inner, BASE_MM + RELIEF_MM + 0.2, t)
    mask = contour_mask(n, n, "circulo")
    s = _masked_flat(t, COIN_PX_MM, mask)
    write_stl(str(path), s.verts, s.faces)


def _font(size: int):
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default()


def hoja(foto: Image.Image, filas: list[tuple[Resultado, Image.Image | None, Image.Image | None]], path: Path) -> None:
    cell = 420
    th = lambda im: ImageOps.contain(im, (cell, cell))  # noqa: E731
    head = 64
    row_h = cell + 56
    W = 24 + 2 * (cell + 16) + 8
    H = head + row_h * (len(filas) + 1)
    sheet = Image.new("RGB", (W, H), (28, 28, 30))
    d = ImageDraw.Draw(sheet)
    big, small = _font(24), _font(16)
    d.text((24, 18), "Profundidad y bajorrelieve con luz rasante", font=big, fill=(240, 200, 120))
    d.text((24, head + 8), "Foto original", font=small, fill=(230, 230, 230))
    sheet.paste(th(foto.convert("RGB")), (24, head + 36))
    y = head + row_h
    for r, dep, rel in filas:
        texto = r.titulo
        if r.error:
            texto += "  ·  ERROR"
        else:
            texto += f"  ·  {r.calculo_s:.1f} s en {r.dispositivo}"
            if r.carga_s:
                texto += f" (+{r.carga_s:.1f} s de carga)"
        d.text((24, y + 8), texto, font=small, fill=(230, 230, 230))
        if r.error:
            d.text((24, y + 40), r.error[:90], font=small, fill=(240, 120, 110))
        else:
            sheet.paste(th(dep), (24, y + 36))
            sheet.paste(th(rel), (24 + cell + 16, y + 36))
        y += row_h
    sheet.save(path)


def mascara(rgb: Image.Image, size: tuple[int, int], cache: dict) -> np.ndarray | None:
    key = ("birefnet", True)
    try:
        if key not in cache:
            cache[key] = sesion(asegurar_modelo("birefnet"), True)
        t = time.perf_counter()
        m = subject_mask(cache[key][0], rgb, size)
        print(f"  fondo... {time.perf_counter() - t:.1f} s ({cache[key][1]})")
        return m
    except Exception as e:  # sin máscara se sigue con el fondo, como antes
        print(f"  fondo... ERROR: {type(e).__name__}: {e}"[:200])
        return None


def procesar(foto_path: Path, metodos: list[str], salida: Path, stl: bool, cache: dict,
             quitar_fondo: bool = False) -> list[Resultado]:
    img = ImageOps.exif_transpose(Image.open(foto_path))
    rgb = img.convert("RGB")
    if max(rgb.size) > 4096:
        rgb = ImageOps.contain(rgb, (4096, 4096))
    k = WORK_PX / max(rgb.size)
    size = (round(rgb.width * k), round(rgb.height * k))
    gray = np.asarray(rgb.convert("L").resize(size, Image.Resampling.LANCZOS), dtype=np.float64) / 255.0
    out = salida / foto_path.stem
    out.mkdir(parents=True, exist_ok=True)
    mm_px = COIN_MM / max(size)

    fondo = mascara(rgb, size, cache) if quitar_fondo else None
    if fondo is not None:
        Image.fromarray((fondo * 255).astype(np.uint8)).save(out / "mascara-motivo.png")

    filas, resultados = [], []
    for m in metodos:
        print(f"  {m}...", end=" ", flush=True)
        r = ejecutar(m, rgb, gray, size, cache)
        resultados.append(r)
        if r.error:
            print("ERROR:", r.error)
            filas.append((r, None, None))
            continue
        print(f"{r.calculo_s:.1f} s ({r.dispositivo}{', ' + ', '.join(r.notas) if r.notas else ''})")
        rel = relieve(r.depth, gray)
        if fondo is not None:
            rel = aislar(rel, fondo)
        dep_img = Image.fromarray((r.depth * 255).astype(np.uint8))
        Image.fromarray((r.depth * 65535).astype(np.uint16)).save(out / f"{m}-profundidad.png")
        rel_img = Image.fromarray(shade(rel * RELIEF_MM, mm_px))
        rel_img.save(out / f"{m}-relieve.png")
        filas.append((r, dep_img, rel_img))
        if stl:
            moneda(rel, out / f"{m}-moneda-50mm.stl")
    hoja(rgb, filas, out / "comparativa.png")
    return resultados


def main() -> int:
    ap = argparse.ArgumentParser(description="Compara métodos de mapa de profundidad para bajorrelieves.")
    ap.add_argument("fotos", nargs="+", help="fotos o carpetas con fotos")
    ap.add_argument("--depthpro", action="store_true", help="probar también Apple Depth Pro (descarga 600 MB)")
    ap.add_argument("--sin-large", action="store_true", help="no probar Depth Anything V2 Large (descarga 1,3 GB)")
    ap.add_argument("--quitar-fondo", action="store_true",
                    help="dejar liso el fondo con BiRefNet lite (descarga 224 MB); mejor para retratos y objetos")
    ap.add_argument("--stl", action="store_true", help="generar una moneda de prueba de 50 mm por método")
    ap.add_argument("--salida", default=str(BASE / "resultados_profundidad"))
    a = ap.parse_args()

    fotos: list[Path] = []
    for f in map(Path, a.fotos):
        if f.is_dir():
            fotos += sorted(p for p in f.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"))
        elif f.exists():
            fotos.append(f)
    if not fotos:
        print("No hay fotos que probar.")
        return 1

    try:
        gpu = proveedores_gpu()
    except ImportError:
        print("Falta onnxruntime: instala requirements-ia.txt (probar_profundidad.bat lo hace solo).")
        return 1
    metodos = ["sin-ia", "small-cpu"] + (["small-gpu"] if gpu else [])
    if not a.sin_large:
        metodos.append("large")
    if a.depthpro:
        metodos.append("depthpro")
    print("Tarjeta gráfica:", ", ".join(gpu) if gpu else "no disponible, todo irá por el procesador")

    salida = Path(a.salida)
    cache: dict = {}
    tabla = []
    for foto in fotos:
        print(f"\n{foto.name}")
        for r in procesar(foto, metodos, salida, a.stl, cache, a.quitar_fondo):
            tabla.append(f"{foto.name}\t{r.clave}\t{r.dispositivo}\t"
                         f"{'ERROR ' + r.error if r.error else f'{r.calculo_s:.2f}'}\t{r.carga_s:.2f}")
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "tiempos.txt").write_text("foto\tmetodo\tdispositivo\tcalculo_s\tcarga_s\n" + "\n".join(tabla) + "\n",
                                        encoding="utf-8")
    print(f"\nListo. Mira las hojas comparativa.png en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
