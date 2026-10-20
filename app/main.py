"""API local de litofanías. Se sirve en 127.0.0.1 y no necesita internet."""
from __future__ import annotations

import io
import math
import threading
import time
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app import storage
from litofania.generate import generate_flat
from litofania.heightmap import FlatParams

STATIC = Path(__file__).resolve().parent / "static"
MAX_UPLOAD = 40 * 1024 * 1024
PREVIEW_TRIANGLES = 700_000

app = FastAPI(title="Litofanías")
storage.ensure_dirs()
SERVER = None  # lo pone run.py para poder cerrar la app desde el botón de apagado


class FlatRequest(BaseModel):
    imagen_id: str
    ancho: float = Field(150.0, ge=20, le=210)
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


@app.post("/api/imagenes")
async def upload_image(archivo: UploadFile) -> dict:
    data = await archivo.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "La imagen supera los 40 MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "El archivo no es una imagen válida")

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


@app.post("/api/litofanias/plana")
def make_flat(req: FlatRequest) -> dict:
    path = storage.image_path(req.imagen_id)
    if path is None:
        raise HTTPException(404, "Imagen no encontrada")
    if req.min >= req.max:
        raise HTTPException(422, "El grosor mínimo debe ser menor que el máximo")
    if req.ancho <= 2 * req.marco + 5:
        raise HTTPException(422, "El marco es demasiado ancho para ese tamaño")

    p = FlatParams(
        width_mm=req.ancho, min_mm=req.min, max_mm=req.max, mm_per_px=req.resolucion,
        border_mm=req.marco, brightness=req.brillo, contrast=req.contraste,
        gamma=req.gamma, invert=req.invertir,
    )
    r = generate_flat(str(path), str(storage.MODELS / f"{req.imagen_id}-plana.stl"), p)

    # Copia más ligera para el visor 3D: misma pieza con menos triángulos si la completa es muy grande.
    preview_res = max(p.mm_per_px, math.sqrt(4 * r.width_mm * r.height_mm / PREVIEW_TRIANGLES))
    preview = replace(p, mm_per_px=preview_res)
    generate_flat(str(path), str(storage.MODELS / f"{req.imagen_id}-plana-vista.stl"), preview)

    base = f"/api/litofanias/{req.imagen_id}"
    return {
        "stl": f"{base}/plana.stl",
        "vista": f"{base}/plana-vista.stl?v={time.time_ns()}",
        "medidas_mm": [round(r.width_mm, 1), round(r.height_mm, 1), round(r.depth_mm, 1)],
        "triangulos": r.triangles,
        "grosor_mm": [p.min_mm, p.max_mm],
    }


@app.get("/api/litofanias/{image_id}/plana.stl")
def download_flat(image_id: str) -> FileResponse:
    path = storage.MODELS / f"{image_id}-plana.stl"
    if not image_id.isalnum() or not path.exists():
        raise HTTPException(404, "Todavía no se ha generado esa litofanía")
    meta = storage.get_meta(image_id) or {}
    name = Path(meta.get("nombre", image_id)).stem
    return FileResponse(path, media_type="model/stl", filename=f"litofania-{name}.stl")


@app.get("/api/litofanias/{image_id}/plana-vista.stl")
def preview_flat(image_id: str) -> FileResponse:
    path = storage.MODELS / f"{image_id}-plana-vista.stl"
    if not image_id.isalnum() or not path.exists():
        raise HTTPException(404, "Todavía no se ha generado esa litofanía")
    return FileResponse(path, media_type="model/stl")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
