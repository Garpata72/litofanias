"""API local de litofanías. Se sirve en 127.0.0.1 y no necesita internet."""
from __future__ import annotations

import io
import math
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app import storage
from litofania.contours import prepare_mask
from litofania.generate import generate, generate_sphere
from litofania.heightmap import FlatParams
from litofania.shapes import SHAPES

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
    zoom: float = Field(1.0, ge=1, le=8)            # plana: encuadre de la foto dentro de la pieza
    centro_x: float = Field(0.5, ge=0, le=1)
    centro_y: float = Field(0.5, ge=0, le=1)
    diametro: float = Field(80.0, ge=30, le=210)    # cilindro, esfera y cúpula: diámetro exterior
    agujero: float = Field(40.0, ge=10, le=200)     # esfera: diámetro de la abertura de abajo
    ajuste: Literal["centrada", "panoramica"] = "centrada"   # esfera y cúpula
    cobertura: float = Field(150.0, ge=40, le=360)  # esfera y cúpula centradas: grados de ancho de la foto
    min: float = Field(0.8, ge=0.4, le=3.0)
    max: float = Field(3.0, ge=1.0, le=8.0)
    resolucion: float = Field(0.2, ge=0.05, le=1.0)
    marco: float = Field(3.0, ge=0, le=20)
    brillo: float = Field(1.0, ge=0.2, le=3.0)
    contraste: float = Field(1.0, ge=0.2, le=3.0)
    gamma: float = Field(1.0, ge=0.2, le=3.0)
    invertir: bool = False


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
    storage.save_mask_meta(mask_id, meta)
    return meta


@app.get("/api/mascaras")
def list_masks() -> list[dict]:
    return storage.list_masks()


@app.get("/api/mascaras/{mask_id}/archivo")
def get_mask(mask_id: str) -> FileResponse:
    path = storage.mask_path(mask_id)
    if path is None:
        raise HTTPException(404, "Máscara no encontrada")
    return FileResponse(path, media_type="image/png")


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

    p = FlatParams(
        width_mm=width, min_mm=req.min, max_mm=req.max, mm_per_px=req.resolucion,
        border_mm=req.marco, brightness=req.brillo, contrast=req.contraste,
        gamma=req.gamma, invert=req.invertir,
    )
    name = f"{req.imagen_id}-{req.forma}"

    def build(out: Path, params: FlatParams):
        if req.forma in ("esfera", "cupula"):
            return generate_sphere(str(path), str(out), params, req.forma, req.diametro, req.agujero, req.ajuste, req.cobertura)
        return generate(str(path), str(out), params, req.forma, req.angulo, req.contorno,
                        str(mask) if mask else None, req.zoom, (req.centro_x, req.centro_y))

    r = build(storage.MODELS / f"{name}.stl", p)
    # Copia más ligera para el visor 3D: misma pieza con menos triángulos si la completa es muy grande.
    preview_res = max(p.mm_per_px, math.sqrt(4 * width * (r.height_mm or width) / PREVIEW_TRIANGLES))
    build(storage.MODELS / f"{name}-vista.stl", replace(p, mm_per_px=preview_res))

    base = f"/api/litofanias/{req.imagen_id}/{req.forma}"
    return {
        "forma": req.forma,
        "stl": f"{base}.stl",
        "vista": f"{base}-vista.stl?v={time.time_ns()}",
        "medidas_mm": [round(r.width_mm, 1), round(r.height_mm, 1), round(r.depth_mm, 1)],
        "triangulos": r.triangles,
        "grosor_mm": [p.min_mm, p.max_mm],
        "radio_mm": r.radius_mm,
    }


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
    return FileResponse(_model_path(image_id, shape), media_type="model/stl", filename=f"litofania-{shape}-{name}.stl")


@app.middleware("http")
async def no_cache(request, call_next):
    # Que el navegador vuelva a pedir la interfaz tras actualizar la app en vez de usar una copia vieja.
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
