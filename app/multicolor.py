"""API de las piezas multicolor: foto en relieve de colores (tipo HueForge) y posavasos.

Las dos generan un proyecto 3MF de OrcaSlicer con el perfil de la Ender 3 V3 KE, los filamentos y los
cambios de filamento ya puestos, más el STL y un texto con las instrucciones de impresión y de acabado."""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import storage
from litofania import coaster as coasters
from litofania import multicolor as mc
from litofania import orca, svgmotif
from litofania.accessories import _mesh
from litofania.printing_color import coaster_settings, photo_settings
from litofania.shapes import signed_volume
from litofania.stl import write_stl

router = APIRouter()
HEX = r"^#[0-9A-Fa-f]{6}$"
PREVIEW_TRIANGLES = 700_000
CONTOURS = {"rectangulo": ("rectangulo", {}), "redondeado": ("redondeado", {}), "circulo": ("circulo", {}),
            "ovalo": ("ovalo", {}), "triangulo": ("poligono", {"sides": 3}), "hexagono": ("poligono", {"sides": 6})}


def _template() -> Path:
    return orca.template_path(storage.ROOT / "plantilla_orca.3mf")


def _title(image_id: str) -> str:
    return Path((storage.get_meta(image_id) or {}).get("nombre", image_id)).stem


def _file(stem: str, tail: str) -> Path:
    path = storage.MODELS / f"{stem}{tail}"
    if not stem.replace("-", "").isalnum() or not path.exists():
        raise HTTPException(404, "Todavía no se ha generado esa pieza")
    return path


# ───────── Foto en relieve multicolor ─────────

class FilamentIn(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=30)
    color: str = Field(..., pattern=HEX)
    td: float = Field(..., ge=0.05, le=20)


class ColorPhotoRequest(BaseModel):
    imagen_id: str
    filamentos: list[FilamentIn] = Field(..., min_length=2, max_length=mc.MAX_FILAMENTS)
    ancho: float = Field(100.0, ge=20, le=220)
    resolucion: float = Field(0.25, ge=0.1, le=1.0)
    capa: float = Field(0.08, ge=0.04, le=0.3)
    primera: float = Field(0.16, ge=0.08, le=0.4)
    base: int = Field(4, ge=1, le=30)
    capas: int = Field(32, ge=4, le=80)
    peso_color: float = Field(2.0, ge=0, le=6)
    contraste: bool = False
    contorno: Literal["rectangulo", "redondeado", "circulo", "ovalo", "triangulo", "hexagono"] = "rectangulo"
    borde: float = Field(0.0, ge=0, le=10)           # borde para la resina UV (mm de ancho, 0 = sin borde)
    borde_alto: float = Field(0.8, ge=0.2, le=4)
    girar: Literal[0, 90, 180, 270] = 0
    recorte: tuple[float, float, float, float] | None = None
    cambios: list[int] | None = None                 # capas de cambio (sobre la base); None = automático


def _crop(c):
    if c is None or tuple(c) == (0, 0, 1, 1):
        return None
    x, y, w, h = c
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 - x + 1e-6 and 0 < h <= 1 - y + 1e-6):
        raise HTTPException(422, "El recorte de la foto no es válido")
    return (x, y, w, h)


@router.post("/api/multicolor/foto")
def make_color_photo(req: ColorPhotoRequest) -> dict:
    path = storage.image_path(req.imagen_id)
    if path is None:
        raise HTTPException(404, "Imagen no encontrada")
    fils = [mc.Filament(f.nombre.strip(), f.color.upper(), f.td) for f in req.filamentos]
    contour, opts = CONTOURS[req.contorno]
    p = mc.ColorParams(width_mm=req.ancho, mm_per_px=req.resolucion, layer=req.capa, first=req.primera,
                       base_layers=req.base, layers=req.capas, color_weight=req.peso_color, contrast=req.contraste,
                       contour=contour, contour_opts=opts, rotate=req.girar, crop=_crop(req.recorte),
                       starts=tuple(req.cambios) if req.cambios is not None else None,
                       rim_mm=req.borde, rim_up_mm=req.borde_alto)
    try:
        r = mc.build(str(path), fils, p)
    except ValueError as e:
        raise HTTPException(422, str(e))
    stem = f"{req.imagen_id}-color"
    out = storage.MODELS
    s = r.solid
    write_stl(str(out / f"{stem}.stl"), s.verts, s.faces)
    if len(s.faces) > PREVIEW_TRIANGLES:     # copia ligera para el visor, con los mismos cambios
        k = math.sqrt(len(s.faces) / PREVIEW_TRIANGLES)
        lite = mc.build(str(path), fils, mc.ColorParams(**{**p.__dict__, "mm_per_px": p.mm_per_px * k, "starts": r.starts[1:]}))
        write_stl(str(out / f"{stem}-vista.stl"), lite.solid.verts, lite.solid.faces)
    else:
        write_stl(str(out / f"{stem}-vista.stl"), s.verts, s.faces)
    changes = r.changes(p)
    orca.write_project(str(out / f"{stem}.3mf"), [("relieve", 1, s.verts, s.faces)], [f.color for f in fils],
                       p.layer, p.first, changes, "relieve", _template())
    r.simulation().save(out / f"{stem}-simulacion.png")
    used = s.verts[np.unique(s.faces)]
    size = tuple((used.max(0) - used.min(0)).tolist())
    volume = signed_volume(s.verts, s.faces)
    info = [{"capa": p.base_layers + st, "z": round(p.z_base + st * p.layer, 3), "filamento": i + 1, "nombre": fils[i].name}
            for i, st in enumerate(r.starts) if i > 0]
    (out / f"{stem}-ajustes.txt").write_text(
        photo_settings(size, fils, info, p.layer, p.first, p.base_layers, volume, req.borde > 0), encoding="utf-8")
    root = f"/api/multicolor/foto/{req.imagen_id}"
    v = time.time_ns()
    return {
        "stl": f"{root}.stl", "vista": f"{root}-vista.stl?v={v}", "tresmf": f"{root}.3mf", "ajustes": f"{root}-ajustes.txt",
        "simulacion": f"{root}-simulacion.png?v={v}", "medidas_mm": [round(x, 1) for x in size],
        "gramos": round(volume / 1000 * 1.24), "triangulos": len(s.faces), "cambios": info,
        "inicio": list(r.starts[1:]), "error": round(r.error, 1),
        "capas_color": {"z0": p.z_base, "h": p.layer,
                        "colores": ["#%02x%02x%02x" % tuple(int(round(c * 255)) for c in col) for col in r.stack_rgb]},
    }


@router.get("/api/multicolor/foto/{image_id}.stl")
def color_photo_stl(image_id: str) -> FileResponse:
    if image_id.endswith("-vista"):
        return FileResponse(_file(f"{image_id.removesuffix('-vista')}-color", "-vista.stl"), media_type="model/stl")
    return FileResponse(_file(f"{image_id}-color", ".stl"), media_type="model/stl", filename=f"color-{_title(image_id)}.stl")


@router.get("/api/multicolor/foto/{image_id}.3mf")
def color_photo_3mf(image_id: str) -> FileResponse:
    return FileResponse(_file(f"{image_id}-color", ".3mf"), media_type="model/3mf", filename=f"color-{_title(image_id)}-orca.3mf")


@router.get("/api/multicolor/foto/{image_id}-ajustes.txt")
def color_photo_settings(image_id: str) -> FileResponse:
    return FileResponse(_file(f"{image_id}-color", "-ajustes.txt"), media_type="text/plain; charset=utf-8",
                        filename=f"instrucciones-color-{_title(image_id)}.txt")


@router.get("/api/multicolor/foto/{image_id}-simulacion.png")
def color_photo_png(image_id: str) -> FileResponse:
    return FileResponse(_file(f"{image_id}-color", "-simulacion.png"), media_type="image/png")


# ───────── Posavasos ─────────

class CoasterRequest(BaseModel):
    modo: Literal["relieve", "incrustado"] = "relieve"
    colores: Literal[2, 3] = 3
    forma: Literal[coasters.SHAPES] = "redondo"   # type: ignore[valid-type]
    tamano: float = Field(100.0, ge=50, le=200)
    esquinas: float = Field(6.0, ge=0, le=30)
    grosor: float = Field(4.0, ge=2, le=10)
    margen: float = Field(5.0, ge=0, le=30)
    incrustacion: Literal[0.3, 0.5] = 0.3
    alto2: float = Field(1.0, ge=0.4, le=4)
    alto3: float = Field(0.8, ge=0.4, le=4)
    borde: float = Field(3.0, ge=0, le=10)
    borde_alto: float = Field(0.6, ge=0, le=3)
    motivo: Literal["demo", "texto", "silueta", "svg"] = "demo"
    texto2: str = Field("CASA", max_length=40)
    texto3: str = Field("", max_length=40)
    texto_mm: float = Field(16.0, ge=4, le=60)
    mascara2_id: str | None = None
    mascara3_id: str | None = None
    motivo_mm: float = Field(0.0, ge=0, le=200)
    svg_id: str | None = None
    svg_mapa: dict[str, Literal[0, 2, 3]] | None = None
    ajuste: Literal["encajar", "rellenar"] = "encajar"
    motivo_giro: float = Field(0.0, ge=-360, le=360)
    motivo_dx: float = Field(0.0, ge=-100, le=100)
    motivo_dy: float = Field(0.0, ge=-100, le=100)
    paleta: list[str] = Field(["#2B3A55", "#F2C14E", "#E4572E"], min_length=3, max_length=3)
    nombres: list[str] = Field(["fondo", "motivo", "detalle"], min_length=3, max_length=3)


# El posavasos no necesita ser macizo como la foto en color (la plantilla trae relleno al 100 %).
COASTER_PROCESS = {"sparse_infill_density": "20%", "sparse_infill_pattern": "gyroid", "wall_loops": "3",
                   "top_shell_layers": "5", "bottom_shell_layers": "5",
                   # Z-hop: al viajar, la boquilla sube por encima del motivo ya impreso en vez de rozarlo.
                   "z_hop": "0.4", "z_hop_types": "Normal Lift"}


def _mask(mid: str | None) -> str | None:
    if not mid:
        return None
    path = storage.mask_path(mid)
    if path is None:
        raise HTTPException(404, "Silueta no encontrada")
    return str(path)


def _svg(sid: str | None) -> str | None:
    if not sid:
        return None
    path = storage.svg_path(sid)
    if path is None:
        raise HTTPException(404, "SVG no encontrado")
    return str(path)


def _coaster_params(req: CoasterRequest) -> coasters.CoasterParams:
    return coasters.CoasterParams(
        mode=req.modo, colors=req.colores, shape=req.forma, size_mm=req.tamano, corner_mm=req.esquinas,
        thickness_mm=req.grosor, margin_mm=req.margen, inlay_mm=req.incrustacion, relief2_mm=req.alto2,
        relief3_mm=req.alto3, rim_mm=req.borde, rim_up_mm=req.borde_alto, motif=req.motivo, text2=req.texto2,
        text3=req.texto3, text_mm=req.texto_mm, mask2=_mask(req.mascara2_id), mask3=_mask(req.mascara3_id),
        motif_mm=req.motivo_mm, svg=_svg(req.svg_id) if req.motivo == "svg" else None, svg_map=req.svg_mapa,
        fit=req.ajuste, rotate=req.motivo_giro, dx=req.motivo_dx, dy=req.motivo_dy)


@router.post("/api/posavasos")
def make_coaster(req: CoasterRequest) -> dict:
    for c in req.paleta:
        if not (len(c) == 7 and c.startswith("#")):
            raise HTTPException(422, "Los colores van en formato #RRGGBB")
    p = _coaster_params(req)
    try:
        c = coasters.build(p)
    except ValueError as e:
        raise HTTPException(422, str(e))
    cid = storage.new_id()
    stem = f"posavasos-{cid}"
    out = storage.MODELS
    n = req.colores
    names = [x.strip() or f"color {i + 1}" for i, x in enumerate(req.nombres)]
    whole_v, whole_f = _mesh(c.whole)
    write_stl(str(out / f"{stem}.stl"), whole_v, whole_f)
    # Proyecto de Orca: relieve = una pieza con cambios por altura; incrustado = una parte por color.
    lo = np.asarray(c.whole.bounding_box()[:3])
    if c.face_down:
        filcolors = [None] * n
        parts = []
        for name, fil, m in c.parts:
            v, f = _mesh_at(m, lo)
            idx = int(name[-1]) - 1
            filcolors[fil - 1] = req.paleta[idx]
            parts.append((f"{name} ({names[idx]})", fil, v, f))
        # Primera capa lenta: los detalles finos del motivo se pegan mejor a la cama.
        orca.write_project(str(out / f"{stem}.3mf"), parts, filcolors, 0.2, c.first_layer, [], "posavasos", _template(),
                           {**COASTER_PROCESS, "initial_layer_speed": "15", "initial_layer_infill_speed": "30",
                            # Primera capa: motivo primero (filamento 1…) y el fondo el último, que sigue hasta arriba.
                            "first_layer_print_sequence": [str(i + 1) for i in range(n)]})
    else:
        rim = req.borde > 0
        orca.write_project(str(out / f"{stem}.3mf"), [("posavasos", 1, whole_v, whole_f)], req.paleta[:n], 0.2, 0.2,
                           c.changes, "posavasos", _template(),
                           {**COASTER_PROCESS, **({} if rim else {"ironing_type": "top"})})
    # Vista: una STL por color, con la cara vista hacia arriba.
    views = []
    for name, fil, m in c.parts:
        shown = m.rotate((0, 180, 0)) if c.face_down else m
        v, f = _mesh_at(shown, np.asarray((c.whole.rotate((0, 180, 0)) if c.face_down else c.whole).bounding_box()[:3]))
        write_stl(str(out / f"{stem}-{name}.stl"), v, f)
        views.append({"url": f"/api/posavasos/{cid}-{name}.stl", "color": req.paleta[int(name[-1]) - 1]})
    b = c.whole.bounding_box()
    size = (b[3] - b[0], b[4] - b[1], b[5] - b[2])
    resin = coasters.resin_ml(p, c)
    (out / f"{stem}-ajustes.txt").write_text(
        coaster_settings(req.modo, n, req.forma, size, req.paleta, names, c.changes, c.first_layer, req.incrustacion,
                         c.whole.volume(), resin, req.modo == "relieve" and req.borde > 0), encoding="utf-8")
    root = f"/api/posavasos/{cid}"
    layers = None
    if not c.face_down:   # relieve: el color de cada altura, para el visor (el borde sale con el último color)
        bands = [0.0] + [z - coasters.LAYER for z, _ in c.changes]
        layers = {"z0": 0.0, "h": coasters.LAYER, "colores": [
            req.paleta[sum(1 for zb in bands[1:] if k * coasters.LAYER > zb + 1e-6)] for k in range(int(round(size[2] / coasters.LAYER)) + 1)]}
    return {"id": cid, "stl": f"{root}.stl", "capas_color": layers, "tresmf": f"{root}.3mf", "ajustes": f"{root}-ajustes.txt", "partes": views,
            "medidas_mm": [round(x, 1) for x in size], "gramos": round(c.whole.volume() / 1000 * 1.24 * 0.5),
            "resina_ml": round(resin, 1), "cambios": [{"z": z, "color": e} for z, e in c.changes]}


def _mesh_at(m, origin) -> tuple[np.ndarray, np.ndarray]:
    mesh = m.to_mesh()
    return np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3] - origin, np.asarray(mesh.tri_verts, dtype=np.int64)


@router.get("/api/posavasos/{name}.stl")
def coaster_stl(name: str) -> FileResponse:
    return FileResponse(_file(f"posavasos-{name}", ".stl"), media_type="model/stl", filename=f"posavasos-{name}.stl")


@router.get("/api/posavasos/{cid}.3mf")
def coaster_3mf(cid: str) -> FileResponse:
    return FileResponse(_file(f"posavasos-{cid}", ".3mf"), media_type="model/3mf", filename=f"posavasos-{cid}-orca.3mf")


@router.get("/api/posavasos/{cid}-ajustes.txt")
def coaster_settings_txt(cid: str) -> FileResponse:
    return FileResponse(_file(f"posavasos-{cid}", "-ajustes.txt"), media_type="text/plain; charset=utf-8",
                        filename=f"instrucciones-posavasos-{cid}.txt")


@router.post("/api/posavasos/vista")
def coaster_preview(req: CoasterRequest) -> dict:
    """Las regiones de cada color, vistas desde arriba (mm, y hacia arriba), para la vista previa al momento."""
    p = _coaster_params(req)
    report: dict = {}
    try:
        c2, c3 = coasters.motifs(p, report)
    except ValueError as e:
        raise HTTPException(422, str(e))
    poly = lambda cs: [[[round(x, 2), round(y, 2)] for x, y in loop] for loop in cs.to_polygons()]
    rim = req.modo == "relieve" and req.borde > 0
    return {"contorno": poly(coasters.outline(p)), "interior": poly(coasters.outline(p, req.borde)) if rim else None,
            "c2": poly(c2 - c3), "c3": poly(c3), "vacio": c2.is_empty() and c3.is_empty(), "perdido": round(report.get("perdido", 0.0), 3)}


# ───────── SVG para el motivo del posavasos ─────────

def svg_info(sid: str, nombre: str) -> dict:
    path = storage.svg_path(sid)
    sv = svgmotif.read_cached(str(path), path.stat().st_mtime)
    mapping = svgmotif.default_map(sv.areas)
    total = sum(sv.areas.values())
    return {"id": sid, "nombre": nombre, "proporcion": round(sv.width / sv.height, 3), "avisos": sv.warnings,
            "colores": [{"color": c, "area": round(100 * a / total, 1), "asignado": mapping[c]}
                        for c, a in sorted(sv.areas.items(), key=lambda kv: -kv[1])]}


@router.post("/api/svgs")
async def upload_svg(archivo: UploadFile) -> dict:
    data = await archivo.read()
    if len(data) > svgmotif.MAX_BYTES:
        raise HTTPException(413, "El SVG pesa más de 5 MB")
    if b"<svg" not in data[:4096].lower() and b"<svg" not in data.lower():
        raise HTTPException(400, "El archivo no es un SVG")
    sid = storage.new_id()
    path = storage.SVGS / f"{sid}.svg"
    path.write_bytes(data)
    try:
        info = svg_info(sid, archivo.filename or "motivo.svg")
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    storage.save_asset_meta(storage.SVGS, sid, {**info, "creada": time.time()})
    return info


@router.get("/api/svgs")
def list_svgs() -> list[dict]:
    return storage.list_assets(storage.SVGS)


@router.get("/api/svgs/{sid}/archivo")
def svg_file(sid: str) -> FileResponse:
    path = storage.svg_path(sid)
    if path is None:
        raise HTTPException(404, "SVG no encontrado")
    return FileResponse(path, media_type="image/svg+xml")
