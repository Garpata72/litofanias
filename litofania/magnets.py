"""Imanes de nevera de acrílico: hoja de fotos en PDF para recortar y útiles de corte y montaje.

Los kits «hazlo tú mismo» traen un acrílico transparente cuadrado con las esquinas redondeadas (50 mm por
defecto), cinta de doble cara y una lámina magnética. La foto, impresa en papel, se pega por detrás del
acrílico y se ve a través de él, así que no se imprime en espejo.

- PDF: cada foto va con 2 mm de sangrado alrededor del corte, la línea de corte (gris y discontinua) y dos
  cruces de registro a ±`sep` mm del centro, en el eje horizontal. Las cruces se pinchan en los pines de la
  base de corte. La maquetación se calcula para cada papel (A4, 10×15, 13×18 y 15×20) probando las dos
  orientaciones, y lleva una regla de control de 50 mm si cabe.
- Útiles (manifold3d, mallas cerradas): base de corte con dos pines, marco de corte con la ventana que guía
  el cúter y plantilla de montaje con el hueco donde se apilan las capas. Lado, radio y `sep` son los mismos
  que en el PDF; si no coinciden, las cruces no caen en los pines.

Todo en mm. En el PDF el origen está abajo a la izquierda.
"""
from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold
from PIL import Image, ImageOps

BLEED = 2.0          # imagen de más alrededor del corte, para que no quede borde blanco
CROSS = 3.0          # brazo de las cruces de registro
CROSS_R = 1.2        # círculo de las cruces
MARGIN = 5.0         # borde del papel que no se usa (casi todas las impresoras imprimen a partir de 3-5 mm)
HEADER = 7.0         # franja de arriba con el título y el aviso de imprimir al 100 %
RULER = 50.0         # regla de control
RULER_BAND = 8.0     # franja que ocupa la regla (abajo, o de pie en un lado)
GAP_MIN = 1.0        # separación mínima entre celdas (se corta a lo bruto por ahí)
GAP_PREF = 6.0       # separación cómoda cuando sobra papel
TARGET_DPI = 300     # por debajo, se avisa de baja resolución
MAX_DPI = 1200       # por encima no se gana nada al imprimir: se reduce para que el PDF no sea enorme
SEGMENTS = 96
TEMPLATE_SCAD = Path(__file__).resolve().parent / "plantillas" / "plantilla_imanes.scad"

# Papeles: nombre, ancho, alto (mm). Los de foto son los de pulgadas (4×6, 5×7 y 6×8).
PAPERS: dict[str, tuple[str, float, float]] = {
    "a4": ("A4", 210.0, 297.0),
    "10x15": ("10 × 15", 101.6, 152.4),
    "13x18": ("13 × 18", 127.0, 177.8),
    "15x20": ("15 × 20", 152.4, 203.2),
}


@dataclass
class Kit:
    """Medidas del imán y de los útiles. Las mismas para el PDF y para las piezas impresas."""
    lado: float = 50.0             # lado del acrílico
    radio: float = 4.0             # radio de las esquinas
    sep: float | None = None       # del centro de la foto a cada cruz (y a cada pin); None = lado/2 + 10
    grosor_acrilico: float = 3.0
    grosor_papel: float = 0.25     # foto + cinta de doble cara
    grosor_iman: float = 0.8       # lámina magnética
    holgura: float = 0.3           # juego del hueco de montaje, por lado
    margen_corte: float = 0.2      # la foto queda este tanto más pequeña por lado que el acrílico

    @property
    def separacion(self) -> float:
        return self.sep if self.sep is not None else self.lado / 2 + 10

    def check(self) -> None:
        if not 15 <= self.lado <= 150:
            raise ValueError("El lado del imán tiene que estar entre 15 y 150 mm")
        if not 0 <= self.radio <= self.lado / 2:
            raise ValueError(f"El radio de las esquinas tiene que estar entre 0 y {self.lado / 2:g} mm (la mitad del lado)")
        min_sep = sep_min(self.lado)
        if self.separacion < min_sep:
            raise ValueError(f"Con {self.lado:g} mm de lado, la distancia del centro a las cruces tiene que ser al menos "
                             f"{min_sep:g} mm; si no, las cruces caen dentro de la foto")
        if self.separacion > self.lado / 2 + 60:
            raise ValueError("Las cruces quedan demasiado lejos de la foto (más de 60 mm del borde)")


def sep_min(lado: float) -> float:
    """Distancia mínima del centro a las cruces: fuera del sangrado y con 1 mm de aire."""
    return round(lado / 2 + BLEED + CROSS + 1, 1)


# ───────────────────────── Maquetación ─────────────────────────

@dataclass
class Layout:
    paper: str
    name: str
    width: float                  # mm, ya en la orientación elegida
    height: float
    landscape: bool
    cols: int
    rows: int
    cell_w: float                 # lo que ocupa una foto con sus cruces
    cell_h: float
    gap_x: float
    gap_y: float
    centers: list[tuple[float, float]] = field(default_factory=list)   # centro de cada foto, en orden de lectura
    ruler: tuple[float, float, bool] | None = None    # (x, y, de pie) del origen de la regla
    title_y: float = 0.0

    @property
    def per_sheet(self) -> int:
        return self.cols * self.rows

    def summary(self) -> dict:
        return {
            "papel": self.paper, "nombre": self.name, "ancho_mm": self.width, "alto_mm": self.height,
            "horizontal": self.landscape, "columnas": self.cols, "filas": self.rows, "por_hoja": self.per_sheet,
            "celda_mm": [round(self.cell_w, 1), round(self.cell_h, 1)],
            "separacion_mm": [round(self.gap_x, 1), round(self.gap_y, 1)],
            "regla": self.ruler is not None,
            "centros_mm": [[round(x, 2), round(y, 2)] for x, y in self.centers],
            "regla_mm": None if self.ruler is None else [round(self.ruler[0], 2), round(self.ruler[1], 2), self.ruler[2]],
        }


class DoesNotFit(ValueError):
    pass


def _count(length: float, cell: float) -> int:
    return max(0, int((length + GAP_MIN + 1e-9) // (cell + GAP_MIN)))


def _gap(length: float, cell: float, n: int) -> float:
    return 0.0 if n < 2 else min(GAP_PREF, (length - n * cell) / (n - 1))


def layout(paper: str, kit: Kit) -> Layout:
    """La maquetación con más fotos por hoja. A igualdad, la que lleva regla y, después, la vertical."""
    if paper not in PAPERS:
        raise ValueError(f"Papel desconocido: {paper}")
    kit.check()
    name, pw, ph = PAPERS[paper]
    cw = 2 * (kit.separacion + CROSS)          # de la punta de una cruz a la de la otra
    ch = kit.lado + 2 * BLEED                  # la foto con su sangrado
    best = None
    for landscape in (False, True):
        W, H = (ph, pw) if landscape else (pw, ph)
        aw, ah = W - 2 * MARGIN, H - 2 * MARGIN - HEADER
        cols = _count(aw, cw)
        options = [(cols * _count(ah - RULER_BAND, ch), "abajo")]
        spare = aw - cols * cw - max(0, cols - 1) * GAP_MIN
        if spare >= RULER_BAND and ah >= RULER + 4:
            options.append((cols * _count(ah, ch), "lado"))
        options.append((cols * _count(ah, ch), None))
        for n, ruler in options:
            key = (n, ruler is not None, not landscape)
            if n and (best is None or key > best[0]):
                best = (key, landscape, ruler)
    if best is None:
        raise DoesNotFit(
            f"Un imán de {kit.lado:g} mm no cabe en papel {name} ({pw:g} × {ph:g} mm): con el sangrado y las cruces "
            f"ocupa {cw:.0f} × {ch:.0f} mm y el papel deja {pw - 2 * MARGIN:.0f} × {ph - 2 * MARGIN - HEADER:.0f} mm útiles. "
            "Elige un papel mayor, un imán más pequeño o acerca las cruces.")
    _, landscape, ruler = best
    W, H = (ph, pw) if landscape else (pw, ph)
    aw, ah = W - 2 * MARGIN, H - 2 * MARGIN - HEADER
    if ruler == "lado":
        aw -= RULER_BAND
    if ruler == "abajo":
        ah -= RULER_BAND
    cols, rows = _count(aw, cw), _count(ah, ch)
    gx, gy = _gap(aw, cw, cols), _gap(ah, ch, rows)
    grid_w, grid_h = cols * cw + (cols - 1) * gx, rows * ch + (rows - 1) * gy
    x0 = MARGIN + (aw - grid_w) / 2
    top = H - MARGIN - HEADER                        # borde de arriba de la zona de fotos
    y_top = top - (ah - grid_h) / 2
    centers = [(x0 + c * (cw + gx) + cw / 2, y_top - r * (ch + gy) - ch / 2) for r in range(rows) for c in range(cols)]
    ruler_pos = None
    if ruler == "abajo":
        ruler_pos = (MARGIN + 2, MARGIN + 2.5, False)
    elif ruler == "lado":
        ruler_pos = (W - MARGIN - RULER_BAND + 2.5, top - (ah - RULER) / 2 - RULER, True)
    return Layout(paper, name, W, H, landscape, cols, rows, cw, ch, gx, gy, centers, ruler_pos, H - MARGIN - 2.6)


def layouts(kit: Kit) -> dict[str, dict]:
    """Resumen de todos los papeles para la interfaz: cuántos caben o por qué no caben."""
    out = {}
    for key, (name, w, h) in PAPERS.items():
        try:
            out[key] = layout(key, kit).summary()
        except DoesNotFit as e:
            out[key] = {"papel": key, "nombre": name, "ancho_mm": w, "alto_mm": h, "por_hoja": 0, "error": str(e)}
    return out


# ───────────────────────── Fotos ─────────────────────────

@dataclass
class Photo:
    path: str
    girar: int = 0               # grados en el sentido del reloj
    zoom: float = 1.0            # 1 = el cuadrado más grande que cabe en la foto
    centro_x: float = 0.5        # centro del cuadrado, en fracciones de la foto girada
    centro_y: float = 0.5
    copias: int = 1


def open_photo(path: str, girar: int = 0) -> Image.Image:
    """Foto con la orientación del móvil (EXIF) y el giro pedido."""
    img = ImageOps.exif_transpose(Image.open(path))
    if girar % 360:
        img = img.rotate(-girar, expand=True)
    return img


def crop_box(size: tuple[int, int], zoom: float, cx: float, cy: float) -> tuple[int, int, int, int]:
    """El cuadrado de la foto que se imprime (con el sangrado). Igual que el encuadre de la interfaz."""
    w, h = size
    side = max(1, round(min(w, h) / max(1.0, zoom)))
    x = min(max(cx * w - side / 2, 0), w - side)
    y = min(max(cy * h - side / 2, 0), h - side)
    x, y = round(x), round(y)
    return x, y, x + side, y + side


def dpi(side_px: int, kit: Kit) -> float:
    """Resolución al tamaño impreso (lado + sangrado)."""
    return side_px / ((kit.lado + 2 * BLEED) / 25.4)


def _photo_reader(p: Photo, kit: Kit):
    from reportlab.lib.utils import ImageReader

    img = open_photo(p.path, p.girar)
    fmt = Image.open(p.path).format
    box = crop_box(img.size, p.zoom, p.centro_x, p.centro_y)
    sq = img.crop(box)
    max_px = round(MAX_DPI * (kit.lado + 2 * BLEED) / 25.4)
    if sq.width > max_px:
        sq = sq.resize((max_px, max_px), Image.LANCZOS)
    has_alpha = sq.mode in ("RGBA", "LA") or (sq.mode == "P" and "transparency" in sq.info)
    if has_alpha:   # lo transparente, en blanco (papel)
        sq = sq.convert("RGBA")
        bg = Image.new("RGB", sq.size, "white")
        bg.paste(sq, mask=sq.split()[-1])
        sq = bg
    elif sq.mode not in ("RGB", "L", "CMYK"):
        sq = sq.convert("RGB")
    if fmt == "JPEG":
        # La foto ya venía en JPEG: se vuelve a guardar casi sin pérdida (calidad 95, sin submuestrear el color).
        buf = io.BytesIO()
        sq.save(buf, "JPEG", quality=95, subsampling=0, optimize=True)
        buf.seek(0)
        return ImageReader(buf), box[2] - box[0]
    return ImageReader(sq.convert("RGB") if sq.mode == "CMYK" else sq), box[2] - box[0]   # PNG y demás: sin pérdida


def _cross(c, x, y) -> None:
    from reportlab.lib.units import mm

    c.setLineWidth(0.15 * mm)
    c.line(x - CROSS * mm, y, x + CROSS * mm, y)
    c.line(x, y - CROSS * mm, x, y + CROSS * mm)
    c.circle(x, y, CROSS_R * mm)


def _ruler(c, x, y, vertical: bool) -> None:
    from reportlab.lib.units import mm

    c.saveState()
    c.translate(x * mm, y * mm)
    if vertical:
        c.rotate(90)
        c.translate(0, -3 * mm)   # que las marcas queden dentro de la franja
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.2 * mm)
    c.line(0, 0, RULER * mm, 0)
    for t in range(int(RULER // 5) + 1):
        c.line(5 * t * mm, 0, 5 * t * mm, (2 if t % 2 == 0 else 1) * mm)
    c.setFont("Helvetica", 5.5)
    c.drawString((RULER + 2) * mm, -0.6 * mm, "50 mm")
    c.restoreState()


def sheet_slots(photos: list[Photo], per_sheet: int, fill: bool) -> list[Photo | None]:
    """Una entrada por hueco: cada foto tantas veces como copias. Con `fill`, la última hoja se completa
    repitiendo las fotos en orden. Sin fotos, una hoja de recuadros vacíos (prueba de los útiles)."""
    slots: list[Photo | None] = [p for p in photos for _ in range(max(1, p.copias))]
    if not slots:
        return [None] * per_sheet
    if fill and len(slots) % per_sheet:
        i = 0
        while len(slots) % per_sheet:
            slots.append(photos[i % len(photos)])
            i += 1
    return slots


def build_pdf(out, paper: str, kit: Kit, photos: list[Photo], fill: bool = False) -> dict:
    """Escribe el PDF (ruta o archivo abierto) y devuelve un resumen: hojas, fotos y avisos."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    lay = layout(paper, kit)
    slots = sheet_slots(photos, lay.per_sheet, fill)
    sheets = math.ceil(len(slots) / lay.per_sheet)
    c = canvas.Canvas(out, pagesize=(lay.width * mm, lay.height * mm), pageCompression=1)
    c.setTitle(f"Imanes de nevera {kit.lado:g} mm - papel {lay.name}")
    c.setAuthor("Litofanías")
    c.setCreator("Litofanías")
    readers: dict[int, tuple] = {}
    low: dict[int, float] = {}
    L, S, sep = kit.lado * mm, (kit.lado + 2 * BLEED) * mm, kit.separacion * mm
    for i, photo in enumerate(slots):
        k = i % lay.per_sheet
        if k == 0:
            if i:
                c.showPage()
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(MARGIN * mm, lay.title_y * mm,
                         f"Imanes {kit.lado:g} mm - papel {lay.name} - cruces a {kit.separacion:g} mm del centro (pines)")
            c.setFont("Helvetica", 5.5)
            c.drawString(MARGIN * mm, (lay.title_y - 2.6) * mm,
                         "Imprimir al 100 % (tamaño real, sin ajustar a la página)."
                         + (" Comprueba la regla de 50 mm." if lay.ruler else ""))
            if lay.ruler:
                _ruler(c, *lay.ruler)
        cx, cy = (v * mm for v in lay.centers[k])
        if photo is not None:
            key = id(photo)
            if key not in readers:   # cada foto se incrusta una sola vez aunque tenga copias
                readers[key] = _photo_reader(photo, kit)
                d = dpi(readers[key][1], kit)
                if d < TARGET_DPI:
                    low[key] = d
            c.drawImage(readers[key][0], cx - S / 2, cy - S / 2, S, S)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.1 * mm)
        c.setDash(1, 1)
        c.roundRect(cx - L / 2, cy - L / 2, L, L, kit.radio * mm)
        c.setDash()
        c.setStrokeColorRGB(0, 0, 0)
        _cross(c, cx - sep, cy)
        _cross(c, cx + sep, cy)
    c.save()
    return {
        "hojas": sheets, "fotos": sum(s is not None for s in slots), "por_hoja": lay.per_sheet,
        "maquetacion": lay.summary(),
        "baja_resolucion": [{"ruta": p.path, "ppp": round(low[id(p)])} for p in photos if id(p) in low],
    }


# ───────────────────────── Útiles impresos ─────────────────────────

BORDER = 8.0         # material alrededor de ventanas y huecos
PLATE = 3.0          # grosor de la base y del marco
OUTER_R = 4.0        # radio de las esquinas de fuera
PIN_D, PIN_H, PIN_TIP = 2.0, 4.0, 1.2
PIN_CLEAR = 0.4      # juego de los agujeros del marco (en diámetro)
GROOVE_W, GROOVE_D = 1.2, 0.8   # ranura de la base bajo la línea de corte


def _rrect(a: float, b: float, r: float) -> CrossSection:
    r = max(0.01, min(r, a / 2 - 0.01, b / 2 - 0.01))
    return CrossSection.square((a - 2 * r, b - 2 * r), True).offset(r, JoinType.Round, circular_segments=SEGMENTS)


def _slab(cs: CrossSection, z0: float, z1: float) -> Manifold:
    return Manifold.extrude(cs, z1 - z0).translate((0, 0, z0))


def plate_size(kit: Kit) -> tuple[float, float]:
    return 2 * kit.separacion + 2 * BORDER, kit.lado + 2 * BORDER


def pocket_depth(kit: Kit) -> float:
    """El hueco de montaje: acrílico + papel y la lámina magnética sobresaliendo 0,3 mm para poder apretarla."""
    return kit.grosor_acrilico + kit.grosor_papel + max(kit.grosor_iman - 0.3, 0.2)


def base_corte(kit: Kit) -> Manifold:
    w, h = plate_size(kit)
    solid = _slab(_rrect(w, h, OUTER_R), 0, PLATE)
    lc = kit.lado - 2 * kit.margen_corte
    groove = _rrect(lc + GROOVE_W, lc + GROOVE_W, kit.radio + GROOVE_W / 2) - _rrect(lc - GROOVE_W, lc - GROOVE_W, max(kit.radio - GROOVE_W / 2, 0.1))
    solid -= _slab(groove, PLATE - GROOVE_D, PLATE + 1)
    for s in (-1, 1):
        pin = Manifold.cylinder(PIN_H - PIN_TIP, PIN_D / 2, PIN_D / 2, 32) + \
            Manifold.cylinder(PIN_TIP, PIN_D / 2, 0.2, 32).translate((0, 0, PIN_H - PIN_TIP))
        solid += pin.translate((s * kit.separacion, 0, PLATE))
    return solid


def marco_corte(kit: Kit) -> Manifold:
    w, h = plate_size(kit)
    lc = kit.lado - 2 * kit.margen_corte
    solid = _slab(_rrect(w, h, OUTER_R), 0, PLATE)
    solid -= _slab(_rrect(lc, lc, kit.radio - kit.margen_corte), -1, PLATE + 1)
    for s in (-1, 1):
        solid -= Manifold.cylinder(PLATE + 2, (PIN_D + PIN_CLEAR) / 2, (PIN_D + PIN_CLEAR) / 2, 32).translate((s * kit.separacion, 0, -1))
    arrow = CrossSection([[(-2.5, -1.5), (2.5, -1.5), (0, 1.8)]]).translate((0, h / 2 - BORDER / 2))
    solid -= _slab(arrow, PLATE - 0.4, PLATE + 1)   # flecha «arriba» grabada
    return solid


def montaje(kit: Kit) -> Manifold:
    lh = kit.lado + 2 * kit.holgura
    le = lh + 2 * BORDER
    depth = pocket_depth(kit)
    t = depth + 2
    solid = _slab(_rrect(le, le, OUTER_R), 0, t)
    solid -= _slab(_rrect(lh, lh, kit.radio + kit.holgura), t - depth, t + 1)
    notch = Manifold.cylinder(depth + 1, 7, 7, SEGMENTS).scale((1, 1.6, 1))
    for s in (-1, 1):   # muescas para sacar el imán con el dedo
        solid -= notch.translate((s * lh / 2, 0, t - depth + 0.01))
    return solid


TOOLS = {"base_corte": base_corte, "marco_corte": marco_corte, "montaje": montaje}
TOOL_NAMES = {"base_corte": "Base de corte", "marco_corte": "Marco de corte", "montaje": "Plantilla de montaje"}


def mesh(solid: Manifold) -> tuple[np.ndarray, np.ndarray]:
    m = solid.to_mesh()
    verts = np.asarray(m.vert_properties, dtype=np.float64)[:, :3]
    verts = verts - [verts[:, 0].min(), verts[:, 1].min(), 0]
    return verts, np.asarray(m.tri_verts, dtype=np.int64)


def tool_mesh(piece: str, kit: Kit) -> tuple[np.ndarray, np.ndarray]:
    kit.check()
    return mesh(TOOLS[piece](kit))


def all_tools(kit: Kit) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Las tres piezas colocadas una junto a otra (para el visor y el 3MF)."""
    kit.check()
    out, y = [], 0.0
    w, h = plate_size(kit)
    for piece in ("base_corte", "marco_corte"):
        v, f = mesh(TOOLS[piece](kit))
        v[:, 1] += y
        out.append((TOOL_NAMES[piece], v, f))
        y += h + 8
    v, f = mesh(montaje(kit))
    v[:, 0] += w + 8
    out.append((TOOL_NAMES["montaje"], v, f))
    return out


def scad(kit: Kit) -> str:
    """El .scad original con estas medidas, para retocarlo en OpenSCAD."""
    text = TEMPLATE_SCAD.read_text(encoding="utf-8")
    values = {"lado": kit.lado, "radio": kit.radio, "grosor_acrilico": kit.grosor_acrilico,
              "grosor_papel": kit.grosor_papel, "grosor_iman": kit.grosor_iman, "holgura": kit.holgura,
              "margen_corte": kit.margen_corte, "sep_pines": kit.separacion}
    for name, value in values.items():
        text = re.sub(rf"^({re.escape(name)}\s*=\s*)[^;]+;", lambda m: f"{m.group(1)}{value:g};", text, count=1, flags=re.M)
    return text


def tool_notes(kit: Kit) -> str:
    lc = kit.lado - 2 * kit.margen_corte
    w, h = plate_size(kit)
    return "\n".join([
        f"Útiles para imanes de {kit.lado:g} mm (radio {kit.radio:g} mm)",
        "",
        f"- Cruces y pines a {kit.separacion:g} mm del centro ({2 * kit.separacion:g} mm entre pines). Usa el PDF hecho con estas mismas medidas.",
        f"- Base y marco de corte: {w:g} × {h:g} × {PLATE:g} mm. Ventana del marco: {lc:g} mm (la foto queda {kit.margen_corte:g} mm más pequeña por lado).",
        f"- Plantilla de montaje: hueco de {kit.lado + 2 * kit.holgura:g} mm y {pocket_depth(kit):.2f} mm de fondo "
        f"(acrílico {kit.grosor_acrilico:g} + papel y cinta {kit.grosor_papel:g} + imán {kit.grosor_iman:g} mm, que sobresale 0,3 mm).",
        "",
        "Impresión: PLA, capa de 0,2 mm, sin soportes, cada pieza plana tal cual sale.",
        "",
        "Uso",
        "1. Imprime el PDF al 100 % (tamaño real) y comprueba la regla de 50 mm.",
        "2. Recorta cada foto a lo bruto dejando las dos cruces.",
        "3. Ponla boca arriba en la base de corte y pincha cada cruz en su pin.",
        "4. Pon el marco de corte encima (flecha hacia arriba) y corta con el cúter por dentro de la ventana.",
        "5. Montaje: acrílico boca abajo en el hueco, cinta de doble cara, foto boca abajo y presiona;",
        "   después la lámina magnética y presiona otra vez. Sácalo por las muescas.",
        "",
        "No hace falta imprimir la foto en espejo: se ve de frente a través del acrílico.",
        "Las medidas del kit son estimadas: mide el tuyo con un calibre y ajusta grosores y holguras.",
    ]) + "\n"
