"""API local de litofanías. Se sirve en 127.0.0.1 y no necesita internet."""
from __future__ import annotations

import io
import json
import math
import threading
import time
from functools import lru_cache
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import numpy as np
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app import storage
from litofania.contours import prepare_mask
from litofania.generate import generate, generate_sphere
from litofania.heightmap import FlatParams
from litofania import printing
from litofania import text as engraving
from litofania import accessories
from litofania.shapes import SHAPES, signed_volume
from litofania.stl import write_stl
from litofania.textures import Fill, flat_fill, prepare_texture

STATIC = Path(__file__).resolve().parent / "static"
MAX_UPLOAD = 40 * 1024 * 1024
PREVIEW_TRIANGLES = 700_000

app = FastAPI(title="Litofanías")
storage.ensure_dirs()
SERVER = None  # lo pone run.py para poder cerrar la app desde el botón de apagado


class LitoRequest(BaseModel):
    imagen_id: str
    forma: Literal["plana", "arco", "cilindro", "esfera", "cupula"] = "plana"
    ancho: float = Field(150.0, ge=20, le=400)      # plana y arco: ancho desarrollado
    angulo: float = Field(120.0, ge=30, le=300)     # arco
    contorno: Literal["rectangulo", "redondeado", "circulo", "ovalo", "corazon", "propia"] = "rectangulo"   # plana
    mascara_id: str | None = None                   # plana con contorno «propia»
    zoom: float = Field(1.0, ge=0.2, le=8)            # plana: encuadre de la foto dentro de la pieza
    centro_x: float = Field(0.5, ge=0, le=1)
    centro_y: float = Field(0.5, ge=0, le=1)
    diametro: float = Field(80.0, ge=30, le=210)    # cilindro, esfera y cúpula: diámetro exterior
    agujero: float = Field(40.0, ge=10, le=200)     # esfera: diámetro de la abertura de abajo
    ajuste: Literal["centrada", "panoramica", "relleno"] = "centrada"   # esfera y cúpula; «relleno» = sin foto
    relleno: Literal["liso", "luna", "textura"] = "liso"   # plana, esfera y cúpula: lo que no tapa la foto
    textura_id: str | None = None                   # relleno «textura»
    textura_mm: float = Field(40.0, ge=5, le=300)   # ancho de cada repetición de la textura
    textura_relieve: float = Field(1.0, ge=0, le=3)  # 1 = como la imagen; más, más marcado
    textura_invertir: bool = False
    textura_bn: bool = False                        # blanco y negro en vez de grises
    cobertura: float = Field(150.0, ge=40, le=360)  # esfera y cúpula centradas: grados de ancho de la foto
    min: float = Field(0.8, ge=0.4, le=3.0)
    max: float = Field(3.0, ge=1.0, le=8.0)
    resolucion: float = Field(0.2, ge=0.05, le=1.0)
    marco: float = Field(3.0, ge=0, le=20)
    brillo: float = Field(1.0, ge=0.2, le=3.0)
    contraste: float = Field(1.0, ge=0.2, le=3.0)
    gamma: float = Field(1.0, ge=0.2, le=3.0)
    invertir: bool = False
    girar: Literal[0, 90, 180, 270] = 0             # giro de la foto en el sentido del reloj
    recorte: tuple[float, float, float, float] | None = None   # x, y, ancho, alto en fracciones (tras girar)
    relieve: Literal["dentro", "fuera"] = "dentro"   # curvas: cara del relieve (la otra queda lisa)
    texto: str = Field("", max_length=60)           # texto grabado (vacío = sin texto)
    texto_mm: float = Field(8.0, ge=3, le=40)       # alto de las letras


@app.get("/api/salud")
def health() -> dict:
    return {"ok": True, "app": "litofanias"}


@app.post("/api/apagar")
def shutdown() -> dict:
    if SERVER is None:
        raise HTTPException(409, "La app no se ha arrancado con run.py")
    threading.Timer(0.3, lambda: setattr(SERVER, "should_exit", True)).start()
    return {"ok": True}


async def _read_image(archivo: UploadFile) -> tuple[bytes, Image.Image]:
    data = await archivo.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "La imagen supera los 40 MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return data, Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "El archivo no es una imagen válida")


@app.post("/api/imagenes")
async def upload_image(archivo: UploadFile) -> dict:
    data, img = await _read_image(archivo)

    image_id = storage.new_id()
    ext = (img.format or "png").lower().replace("jpeg", "jpg")
    (storage.IMAGES / f"{image_id}.{ext}").write_bytes(data)
    meta = {
        "id": image_id,
        "nombre": archivo.filename or f"imagen.{ext}",
        "ancho": img.width,
        "alto": img.height,
        "creada": time.time(),
    }
    storage.save_meta(image_id, meta)
    return meta


@app.get("/api/imagenes")
def list_images() -> list[dict]:
    return storage.list_images()


@app.get("/api/imagenes/{image_id}/archivo")
def get_image(image_id: str) -> FileResponse:
    path = storage.image_path(image_id)
    if path is None:
        raise HTTPException(404, "Imagen no encontrada")
    return FileResponse(path)


@app.post("/api/mascaras")
async def upload_mask(archivo: UploadFile) -> dict:
    """Máscara propia para recortar la plana: una silueta (oscura sobre claro, clara sobre oscuro o PNG con transparencia)."""
    _, img = await _read_image(archivo)
    try:
        mask = prepare_mask(img)
    except ValueError as e:
        raise HTTPException(400, str(e))
    mask_id = storage.new_id()
    mask.save(storage.MASKS / f"{mask_id}.png")
    meta = {"id": mask_id, "nombre": archivo.filename or "mascara.png", "ancho": mask.width, "alto": mask.height,
            "creada": time.time()}
    storage.save_asset_meta(storage.MASKS, mask_id, meta)
    return meta


@app.get("/api/mascaras")
def list_masks() -> list[dict]:
    return storage.list_assets(storage.MASKS)


@app.get("/api/mascaras/{mask_id}/archivo")
def get_mask(mask_id: str) -> FileResponse:
    path = storage.mask_path(mask_id)
    if path is None:
        raise HTTPException(404, "Máscara no encontrada")
    return FileResponse(path, media_type="image/png")


@app.post("/api/texturas")
async def upload_texture(archivo: UploadFile) -> dict:
    """Textura propia para el relleno: se guarda en gris, con el contraste estirado y como mucho 1024 px."""
    _, img = await _read_image(archivo)
    tex = prepare_texture(img)
    tex_id = storage.new_id()
    tex.save(storage.TEXTURES / f"{tex_id}.png")
    meta = {"id": tex_id, "nombre": archivo.filename or "textura.png", "ancho": tex.width, "alto": tex.height,
            "creada": time.time()}
    storage.save_asset_meta(storage.TEXTURES, tex_id, meta)
    return meta


@app.get("/api/texturas")
def list_textures() -> list[dict]:
    return storage.list_assets(storage.TEXTURES)


@app.get("/api/texturas/{tex_id}/archivo")
def get_texture(tex_id: str) -> FileResponse:
    path = storage.asset_path(storage.TEXTURES, tex_id)
    if path is None:
        raise HTTPException(404, "Textura no encontrada")
    return FileResponse(path, media_type="image/png")


def _fill(req: "LitoRequest | FillQuery") -> Fill:
    if req.relleno != "textura":
        return Fill(req.relleno)
    path = storage.asset_path(storage.TEXTURES, req.textura_id or "")
    if path is None:
        raise HTTPException(422, "Elige o sube una textura para el relleno")
    return Fill("textura", str(path), req.textura_mm, req.textura_relieve, req.textura_invertir, req.textura_bn)


class FillQuery(BaseModel):
    relleno: Literal["liso", "luna", "textura"] = "luna"
    textura_id: str | None = None
    textura_mm: float = Field(40.0, ge=5, le=300)
    textura_relieve: float = Field(1.0, ge=0, le=3)
    textura_invertir: bool = False
    textura_bn: bool = False
    ancho: int = Field(400, ge=2, le=1000)          # píxeles de la vista previa
    alto: int = Field(300, ge=2, le=1000)
    mm_px: float = Field(0.4, gt=0, le=10)          # milímetros de pieza por píxel de la vista previa


@app.get("/api/relleno.png")
def fill_preview(q: Annotated[FillQuery, Query()]) -> Response:
    """Relleno para la vista previa de la plana: el mismo que lleva el STL, a la medida pedida."""
    return Response(_fill_png(_fill(q), q.ancho, q.alto, round(q.mm_px, 4)), media_type="image/png",
                    headers={"Cache-Control": "max-age=3600"})


@lru_cache(maxsize=16)
def _fill_png(fill: Fill, cols: int, rows: int, mm_px: float) -> bytes:
    buf = io.BytesIO()
    Image.fromarray((flat_fill(fill, rows, cols, mm_px) * 255).round().astype(np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def _crop(c: tuple[float, float, float, float] | None) -> tuple[float, float, float, float] | None:
    if c is None:
        return None
    x, y, w, h = c
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x + 1e-6 and 0 < h <= 1 - y + 1e-6):
        raise HTTPException(422, "El recorte de la foto no es válido")
    return None if (x, y, w, h) == (0, 0, 1, 1) else (x, y, w, h)


@app.post("/api/litofanias")
def make_lithophane(req: LitoRequest) -> dict:
    path = storage.image_path(req.imagen_id)
    if path is None:
        raise HTTPException(404, "Imagen no encontrada")
    if req.min >= req.max:
        raise HTTPException(422, "El grosor mínimo debe ser menor que el máximo")
    round_shape = req.forma in ("cilindro", "esfera", "cupula")
    width = math.pi * req.diametro if round_shape else req.ancho
    if not round_shape and width <= 2 * req.marco + 5:
        raise HTTPException(422, "El marco es demasiado ancho para ese tamaño")
    if round_shape and req.diametro <= 2 * req.max + 10:
        raise HTTPException(422, "El diámetro es demasiado pequeño para ese grosor")
    if req.forma == "esfera" and req.agujero >= req.diametro - 10:
        raise HTTPException(422, "La abertura debe ser al menos 10 mm menor que el diámetro")
    mask = None
    if req.forma == "plana" and req.contorno == "propia":
        mask = storage.mask_path(req.mascara_id or "")
        if mask is None:
            raise HTTPException(422, "Elige o sube una máscara para el contorno propio")

    uses_fill = req.forma == "plana" or (req.forma in ("esfera", "cupula") and req.ajuste != "panoramica")
    fill = _fill(req) if uses_fill else Fill()
    p = FlatParams(
        width_mm=width, min_mm=req.min, max_mm=req.max, mm_per_px=req.resolucion,
        border_mm=req.marco, brightness=req.brillo, contrast=req.contraste,
        gamma=req.gamma, invert=req.invertir, rotate=req.girar, crop=_crop(req.recorte),
    )
    name = f"{req.imagen_id}-{req.forma}"

    def build(out: Path, params: FlatParams):
        if req.forma in ("esfera", "cupula"):
            return generate_sphere(str(path), str(out), params, req.forma, req.diametro, req.agujero, req.ajuste, req.cobertura,
                                   fill, req.texto, req.texto_mm, req.relieve == "fuera")
        return generate(str(path), str(out), params, req.forma, req.angulo, req.contorno,
                        str(mask) if mask else None, req.zoom, (req.centro_x, req.centro_y), fill,
                        req.texto, req.texto_mm, req.relieve == "fuera")

    r = build(storage.MODELS / f"{name}.stl", p)
    # Copia más ligera para el visor 3D: misma pieza con menos triángulos si la completa es muy grande.
    preview_res = max(p.mm_per_px, math.sqrt(4 * width * (r.height_mm or width) / PREVIEW_TRIANGLES))
    build(storage.MODELS / f"{name}-vista.stl", replace(p, mm_per_px=preview_res))

    size = (r.width_mm, r.height_mm, r.depth_mm)
    (storage.MODELS / f"{name}-ajustes.txt").write_text(
        printing.settings(req.forma, size, p.min_mm, p.max_mm, r.volume_mm3), encoding="utf-8")
    # Lo que necesita la caja de luz o la base de esta pieza.
    (storage.MODELS / f"{name}.json").write_text(json.dumps({
        "forma": req.forma, "medidas_mm": size, "grosor_max": p.max_mm, "marco": req.marco,
        "radio_mm": r.radius_mm, "angulo": req.angulo, "agujero": req.agujero, "contorno": r.outline,
    }), encoding="utf-8")

    base = f"/api/litofanias/{req.imagen_id}/{req.forma}"
    return {
        "forma": req.forma,
        "stl": f"{base}.stl",
        "vista": f"{base}-vista.stl?v={time.time_ns()}",
        "medidas_mm": [round(r.width_mm, 1), round(r.height_mm, 1), round(r.depth_mm, 1)],
        "triangulos": r.triangles,
        "grosor_mm": [p.min_mm, p.max_mm],
        "radio_mm": r.radius_mm,
        "gramos": round(printing.grams(r.volume_mm3)),
        "relieve_fuera": req.relieve == "fuera" and req.forma != "plana",
        "ajustes": f"{base}-ajustes.txt",
    }


class AccessoryRequest(BaseModel):
    imagen_id: str
    forma: Literal["plana", "arco", "cilindro", "esfera", "cupula"]
    fondo: float = Field(30.0, ge=10, le=80)        # caja de luz: fondo de la cámara para la luz
    alto: float = Field(25.0, ge=12, le=60)         # bases: altura
    holgura: float = Field(0.4, ge=0.1, le=1.0)


@app.post("/api/accesorios")
def make_accessory(req: AccessoryRequest) -> dict:
    """Caja de luz o base para la última litofanía generada con esta imagen y forma."""
    meta_path = storage.MODELS / f"{req.imagen_id}-{req.forma}.json"
    if not req.imagen_id.isalnum() or not meta_path.exists():
        raise HTTPException(404, "Genera primero la litofanía")
    m = json.loads(meta_path.read_text(encoding="utf-8"))
    w, h, _ = m["medidas_mm"]
    t, c = m["grosor_max"], req.holgura
    if req.forma == "plana":
        a = accessories.light_box(w, h, t, m["marco"], req.fondo, c, m.get("contorno"))
    elif req.forma == "arco":
        a = accessories.arc_base(m["radio_mm"], m["angulo"], t, req.alto, c)
    elif req.forma == "esfera":
        a = accessories.sphere_stand(m["agujero"], req.alto, c)
    else:
        a = accessories.round_base(m["radio_mm"], t, req.alto, c, req.forma)
    name = f"{req.imagen_id}-{req.forma}"
    write_stl(str(storage.MODELS / f"{name}-accesorio.stl"), a.verts, a.faces)
    (storage.MODELS / f"{name}-accesorio-ajustes.txt").write_text(
        printing.accessory_settings(a.notes, a.size_mm, accessories_grams(a)), encoding="utf-8")
    base = f"/api/litofanias/{req.imagen_id}/{req.forma}"
    return {
        "nombre": {"caja": "Caja de luz", "base": "Base", "peana": "Peana"}[a.name],
        "stl": f"{base}-accesorio.stl",
        "vista": f"{base}-accesorio.stl?v={time.time_ns()}",
        "medidas_mm": [round(v, 1) for v in a.size_mm],
        "triangulos": len(a.faces),
        "gramos": round(accessories_grams(a)),
        "ajustes": f"{base}-accesorio-ajustes.txt",
    }


def accessories_grams(a) -> float:
    return printing.grams(signed_volume(a.verts, a.faces)) * printing.ACCESSORY_FILL


@app.post("/api/litofanias/plana")
def make_flat(req: LitoRequest) -> dict:
    return make_lithophane(req.model_copy(update={"forma": "plana"}))


def _model_path(image_id: str, shape: str, suffix: str = "") -> Path:
    path = storage.MODELS / f"{image_id}-{shape}{suffix}.stl"
    if not image_id.isalnum() or shape not in SHAPES or not path.exists():
        raise HTTPException(404, "Todavía no se ha generado esa litofanía")
    return path


@app.get("/api/litofanias/{image_id}/{shape}.stl")
def download_model(image_id: str, shape: str) -> FileResponse:
    if shape.endswith("-vista"):
        return FileResponse(_model_path(image_id, shape.removesuffix("-vista"), "-vista"), media_type="model/stl")
    meta = storage.get_meta(image_id) or {}
    name = Path(meta.get("nombre", image_id)).stem
    if shape.endswith("-accesorio"):
        shape = shape.removesuffix("-accesorio")
        return FileResponse(_model_path(image_id, shape, "-accesorio"), media_type="model/stl",
                            filename=f"accesorio-{shape}-{name}.stl")
    return FileResponse(_model_path(image_id, shape), media_type="model/stl", filename=f"litofania-{shape}-{name}.stl")


@app.get("/api/litofanias/{image_id}/{shape}-ajustes.txt")
def download_settings(image_id: str, shape: str) -> FileResponse:
    path = storage.MODELS / f"{image_id}-{shape}-ajustes.txt"
    if not image_id.isalnum() or shape.removesuffix("-accesorio") not in SHAPES or not path.exists():
        raise HTTPException(404, "Todavía no se ha generado esa litofanía")
    meta = storage.get_meta(image_id) or {}
    name = Path(meta.get("nombre", image_id)).stem
    return FileResponse(path, media_type="text/plain; charset=utf-8", filename=f"ajustes-{shape}-{name}.txt")


@app.get("/api/fuente.ttf")
def engraving_font() -> FileResponse:
    """La fuente del texto grabado, para que la vista previa use la misma letra que el STL."""
    return FileResponse(engraving.FONT, media_type="font/ttf")


# ───────── Plantillas: ajustes guardados con un nombre ─────────

@app.get("/api/plantillas")
def list_presets() -> list[dict]:
    return [{"nombre": k, "ajustes": v} for k, v in sorted(storage.load_presets().items(), key=lambda kv: kv[0].lower())]


@app.put("/api/plantillas/{nombre}")
def save_preset(nombre: str, ajustes: dict) -> dict:
    nombre = nombre.strip()
    if not nombre or len(nombre) > 40:
        raise HTTPException(422, "El nombre de la plantilla debe tener entre 1 y 40 caracteres")
    allowed = set(LitoRequest.model_fields) - {"imagen_id", "mascara_id"}
    clean = {k: v for k, v in ajustes.items() if k in allowed}
    presets = storage.load_presets()
    presets[nombre] = clean
    storage.save_presets(presets)
    return {"nombre": nombre, "ajustes": clean}


@app.delete("/api/plantillas/{nombre}")
def delete_preset(nombre: str) -> dict:
    presets = storage.load_presets()
    if presets.pop(nombre, None) is None:
        raise HTTPException(404, "No existe esa plantilla")
    storage.save_presets(presets)
    return {"ok": True}


@app.middleware("http")
async def no_cache(request, call_next):
    # Que el navegador vuelva a pedir la interfaz tras actualizar la app en vez de usar una copia vieja.
    response = await call_next(request)
    if not request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
