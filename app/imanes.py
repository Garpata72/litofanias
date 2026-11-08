"""API de los imanes de nevera: hoja de fotos en PDF y útiles de corte y montaje (STL, 3MF y .scad)."""
from __future__ import annotations

import time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app import storage
from litofania import magnets
from litofania.stl import write_stl
from litofania.threemf import write_3mf

router = APIRouter(prefix="/api/imanes")
Paper = Literal["a4", "10x15", "13x18", "15x20"]


class KitQuery(BaseModel):
    """Medidas del imán. Las mismas para el PDF y para los útiles: si no, las cruces no caen en los pines."""
    lado: float = Field(50.0, ge=15, le=150)
    radio: float = Field(4.0, ge=0, le=75)
    sep: float | None = Field(None, ge=10, le=140)     # vacío = lado/2 + 10
    grosor_acrilico: float = Field(3.0, ge=0.5, le=10)
    grosor_papel: float = Field(0.25, ge=0.05, le=2)
    grosor_iman: float = Field(0.8, ge=0.2, le=5)
    holgura: float = Field(0.3, ge=0, le=1.5)
    margen_corte: float = Field(0.2, ge=0, le=1.5)

    def kit(self) -> magnets.Kit:
        kit = magnets.Kit(**self.model_dump(include=set(KitQuery.model_fields)))
        try:
            kit.check()
        except ValueError as e:
            raise HTTPException(422, str(e))
        return kit


class MagnetPhoto(BaseModel):
    imagen_id: str
    girar: Literal[0, 90, 180, 270] = 0
    zoom: float = Field(1.0, ge=1, le=10)
    centro_x: float = Field(0.5, ge=0, le=1)
    centro_y: float = Field(0.5, ge=0, le=1)
    copias: int = Field(1, ge=1, le=100)


class SheetRequest(KitQuery):
    papel: Paper = "a4"
    rellenar: bool = False                      # completar la última hoja repitiendo las fotos
    fotos: list[MagnetPhoto] = Field(default_factory=list, max_length=60)


def _folder():
    folder = storage.ROOT / "imanes"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


@router.get("/papeles")
def papers(q: Annotated[KitQuery, Query()]) -> dict:
    """Cuántos imanes caben en cada papel con estas medidas (o por qué no caben)."""
    kit = q.kit()
    return {"sep": kit.separacion, "sep_min": magnets.sep_min(kit.lado), "sangrado": magnets.BLEED,
            "ppp_minimo": magnets.TARGET_DPI, "papeles": magnets.layouts(kit)}


@router.post("/pdf")
def make_pdf(req: SheetRequest) -> dict:
    kit = req.kit()
    photos, names = [], {}
    for f in req.fotos:
        path = storage.image_path(f.imagen_id)
        if path is None:
            raise HTTPException(404, "Una de las fotos ya no está en la app")
        names[str(path)] = (storage.get_meta(f.imagen_id) or {}).get("nombre", path.name)
        photos.append(magnets.Photo(str(path), f.girar, f.zoom, f.centro_x, f.centro_y, f.copias))
    name = f"imanes-{kit.lado:g}mm-{req.papel}.pdf"
    try:
        info = magnets.build_pdf(str(_folder() / name), req.papel, kit, photos, req.rellenar)
    except magnets.DoesNotFit as e:
        raise HTTPException(422, str(e))
    for low in info["baja_resolucion"]:
        low["nombre"] = names.get(low.pop("ruta"), "")
    info["pdf"] = f"/api/imanes/{name}?v={time.time_ns()}"
    return info


@router.get("/{name}.pdf")
def download_pdf(name: str) -> FileResponse:
    path = _folder() / f"{name}.pdf"
    if not name.replace("-", "").replace(".", "").isalnum() or not path.exists():
        raise HTTPException(404, "Genera primero el PDF")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


def _stl_bytes(verts, faces) -> bytes:
    folder = _folder()
    tmp = folder / f"tmp-{storage.new_id()}.stl"
    try:
        write_stl(str(tmp), verts, faces)
        return tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)


def _attachment(data: bytes, filename: str, media: str) -> Response:
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/utiles/{pieza}.stl")
def tool_stl(pieza: Literal["base_corte", "marco_corte", "montaje", "todo"], q: Annotated[KitQuery, Query()]):
    kit = q.kit()
    if pieza == "todo":
        import numpy as np
        parts = magnets.all_tools(kit)
        offset, faces = 0, []
        for _, v, f in parts:
            faces.append(f + offset)
            offset += len(v)
        verts = np.vstack([v for _, v, _ in parts])
        data = _stl_bytes(verts, np.vstack(faces))
    else:
        data = _stl_bytes(*magnets.tool_mesh(pieza, kit))
    return _attachment(data, f"iman-{kit.lado:g}mm-{pieza}.stl", "model/stl")


@router.get("/utiles.3mf")
def tool_3mf(q: Annotated[KitQuery, Query()]):
    kit = q.kit()
    tmp = _folder() / f"tmp-{storage.new_id()}.3mf"
    try:
        write_3mf(str(tmp), magnets.all_tools(kit))
        data = tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
    return _attachment(data, f"iman-{kit.lado:g}mm-utiles.3mf", "model/3mf")


@router.get("/utiles.scad")
def tool_scad(q: Annotated[KitQuery, Query()]):
    kit = q.kit()
    return _attachment(magnets.scad(kit).encode("utf-8"), f"plantilla_imanes-{kit.lado:g}mm.scad", "text/plain; charset=utf-8")


@router.get("/utiles.txt")
def tool_notes(q: Annotated[KitQuery, Query()]):
    kit = q.kit()
    return _attachment(magnets.tool_notes(kit).encode("utf-8"), f"iman-{kit.lado:g}mm-instrucciones.txt", "text/plain; charset=utf-8")
