"""Prueba de Marigold (profundidad por difusión) frente a Depth Anything V3 con tus fotos.

Marigold v1.1 (prs-eth, basado en Stable Diffusion 2) corre con PyTorch: en una GTX 1060 de 6 GB va en media precisión,
tarda decenas de segundos por foto y descarga unos 2,6 GB la primera vez. Marigold v2 está construido sobre Qwen-Image-Edit
(más de 20 GB de modelo) y no cabe en esa tarjeta, por eso aquí se prueba la v1.1.

    python prueba_marigold.py fotos/ [--pasos 10] [--conjunto 3] [--resolucion 768] [--stl] [--cpu]

Deja en resultados_marigold/<foto>/ una hoja comparativa.png (original, DA3 y Marigold: mapa y relieve con luz rasante) y los
tiempos en tiempos.txt. Con --stl guarda también la moneda de prueba de cada método."""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

import marigold_worker
from litofania import background, depth, models, relief
from litofania.basrelief import aislar, blur, compress, normalize, shade, sharpen
from litofania.medal import MedalParams, build as medal_build
from litofania.shapes import _masked_flat
from litofania.stl import write_stl

EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def fotos(entradas: list[str]) -> list[Path]:
    out: list[Path] = []
    for e in entradas:
        p = Path(e)
        out += sorted(f for f in p.rglob("*") if f.suffix.lower() in EXT) if p.is_dir() else [p]
    return out


class Marigold:
    def __init__(self, cpu: bool):
        self.pipe, self.dev = marigold_worker.load(cpu)

    def __call__(self, img: Image.Image, pasos: int, conjunto: int, res: int, size: tuple[int, int]) -> np.ndarray:
        d = marigold_worker.predict(self.pipe, img, pasos, conjunto, res)
        return normalize(depth.resize(d, size), 0.5, 99.95)


def relieve(d: np.ndarray, gray: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    rel = compress(d, depth_px=max(d.shape) / 8, alpha=4.0, detail=0.15, detail_src=gray)
    rel = sharpen(normalize(rel + 0.4 * normalize(blur(d, max(d.shape) / 100), 0.5, 99.5), 0.2, 99.8), 0.3)
    return aislar(rel, mask) if mask is not None else rel


def moneda(rel: np.ndarray, path: Path) -> Image.Image:
    t, mask, _ = medal_build(rel, MedalParams(shape="circulo", width_mm=50, height_mm=50, mm_per_px=0.1))
    s = _masked_flat(t, 0.1, mask)
    write_stl(str(path), s.verts, s.faces)
    return Image.fromarray(shade(np.where(mask, t, 0.0), 0.1))


def vista(rel: np.ndarray, stl: Path, guardar: bool) -> Image.Image:
    return moneda(rel, stl) if guardar else Image.fromarray(shade(rel * 1.6, 0.0625))


def hoja(foto: Image.Image, cols: list[tuple[str, Image.Image, Image.Image]], path: Path) -> None:
    cell = 380
    fit = lambda im: ImageOps.contain(im.convert("RGB"), (cell, cell))   # noqa: E731
    w = cell * (1 + len(cols)) + 20 * (2 + len(cols))
    sheet = Image.new("RGB", (w, 2 * cell + 120), (20, 22, 28))
    d = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    sheet.paste(fit(foto), (20, 60))
    d.text((20, 40), "Foto original", font=font, fill=(230, 230, 230))
    for i, (titulo, mapa, rel) in enumerate(cols):
        x = 40 + cell * (i + 1)
        d.text((x, 40), titulo, font=font, fill=(230, 230, 230))
        sheet.paste(fit(mapa), (x, 60))
        sheet.paste(fit(rel), (x, 60 + cell + 20))
    sheet.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fotos", nargs="+")
    ap.add_argument("--salida", default="resultados_marigold")
    ap.add_argument("--pasos", type=int, default=10, help="pasos de difusión (más = más fino y más lento)")
    ap.add_argument("--conjunto", type=int, default=3, help="repeticiones que se promedian")
    ap.add_argument("--resolucion", type=int, default=768, help="lado de trabajo de Marigold")
    ap.add_argument("--stl", action="store_true")
    ap.add_argument("--cpu", action="store_true", help="no usar la tarjeta gráfica (muy lento)")
    a = ap.parse_args()

    lista = fotos(a.fotos)
    if not lista:
        print("No hay fotos.")
        return 1
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    print("Cargando Marigold (la primera vez descarga unos 2,6 GB)...")
    mg = Marigold(a.cpu)
    print(f"Marigold en {mg.dev}")
    metodo = next((m for m in ("da3", "large", "small") if models.installed(m) and models.ort_available()), None)
    tiempos, errores = [], []
    for f in lista:
        try:
            carpeta = out / f.stem
            carpeta.mkdir(exist_ok=True)
            img = relief._crop(f, relief.ReliefParams())              # recorte cuadrado a 800 px, como la app
            size = img.size
            gray = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
            mask = None
            if models.installed("birefnet") and models.ort_available():
                m = background.subject_mask(models.session("birefnet", False)[0], img, size)
                mask = m if background.dominant(m)[0] else None
            cols = []
            if metodo:
                d, _, _, seg = depth.estimate(metodo, img, gray, size, gpu=False)
                r = relieve(d, gray, mask)
                cols.append((f"{models.MODELOS[metodo].nombre} ({seg:.1f} s)", Image.fromarray((d * 255).astype(np.uint8)),
                             vista(r, carpeta / f"{f.stem}-{metodo}.stl", a.stl)))
            t = time.perf_counter()
            d = mg(img, a.pasos, a.conjunto, a.resolucion, size)
            seg = time.perf_counter() - t
            r = relieve(d, gray, mask)
            Image.fromarray((d * 255).astype(np.uint8)).save(carpeta / "marigold-profundidad.png")
            cols.append((f"Marigold v1.1 ({seg:.0f} s)", Image.fromarray((d * 255).astype(np.uint8)),
                         vista(r, carpeta / f"{f.stem}-marigold.stl", a.stl)))
            hoja(img, cols, carpeta / "comparativa.png")
            tiempos.append(f"{f.name}: Marigold {seg:.1f} s ({a.pasos} pasos x {a.conjunto}, {mg.dev})")
            print(tiempos[-1])
        except Exception:
            errores.append(f"{f.name}\n{traceback.format_exc()}")
            print(f"Fallo con {f.name}; sigo con la siguiente.")
    (out / "tiempos.txt").write_text("\n".join(tiempos) + "\n", encoding="utf-8")
    (out / "errores.txt").write_text("\n".join(errores), encoding="utf-8")
    return 0 if not errores else 2


if __name__ == "__main__":
    sys.exit(main())
