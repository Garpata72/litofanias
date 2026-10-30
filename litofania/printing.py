"""Ajustes de impresión recomendados para la Creality Ender 3 V3 KE, en un texto que acompaña al STL.

El texto dice qué opción cambiar, con su nombre y su valor, en Orca Slicer, Bambu Studio y Cura."""
from __future__ import annotations

PRINTER = "Creality Ender 3 V3 KE"
BED = (220.0, 220.0, 240.0)
PLA_DENSITY = 1.24          # g/cm³
ACCESSORY_FILL = 0.45       # paredes + 15 % de relleno: fracción aproximada del volumen macizo

NAMES = {"plana": "plana", "arco": "arco", "cilindro": "cilindro", "cono": "lámpara cónica", "esfera": "esfera", "cupula": "cúpula"}

ORIENTATION = {
    "plana": [
        "Imprímela DE PIE: en el laminador gírala 90° para que el lado largo quede sobre la cama.",
        "Así cada capa recorre la imagen y el relieve sale mucho más fino que tumbada.",
        "Añade un borde de adherencia (brim) de 6-8 mm por los dos lados para que no se mueva.",
    ],
    "arco": [
        "Imprímelo de pie, tal como sale del STL (el borde de abajo sobre la cama).",
        "Borde de adherencia (brim) de 5 mm.",
    ],
    "cilindro": [
        "Imprímelo de pie, tal como sale del STL.",
        "Borde de adherencia (brim) de 5 mm si es alto y estrecho.",
    ],
    "cono": [
        "Imprímela de pie, tal como sale del STL (la boca ancha o la estrecha abajo, según la hayas diseñado).",
        "Si la pared se inclina más de 30° hacia fuera, baja la velocidad de las paredes a 30 mm/s.",
        "Borde de adherencia (brim) de 5 mm.",
    ],
    "esfera": [
        "Imprímela con la abertura hacia abajo, apoyada en la cama, tal como sale del STL.",
        "La parte baja vuela hacia fuera: activa soportes de árbol SOLO desde la cama (no sobre la pieza).",
        "Si el laminador lo permite, limita los soportes a ángulos de más de 50°.",
    ],
    "cupula": [
        "Imprímela con la parte abierta hacia abajo, tal como sale del STL.",
        "Cerca de la cima las capas cierran hacia dentro: si el diámetro pasa de 60 mm, usa soportes de árbol",
        "solo desde la cama, o baja la velocidad de las paredes a 30 mm/s.",
    ],
}


def grams(volume_mm3: float) -> float:
    return volume_mm3 / 1000 * PLA_DENSITY


# Valores comunes de las litofanías (PLA blanco, macizas): se escriben con los nombres de cada laminador.
LAYER = "0,12"
FACE = {"brim": {"plana": 7, "arco": 5, "cilindro": 5, "cono": 5, "esfera": 5, "cupula": 5}}


def _slicer_blocks(rows: list[tuple]) -> list[str]:
    """Una sección por laminador. Cada fila es (pestaña de Orca/Bambu, opción de Orca/Bambu, opción de Cura, valor);
    el valor puede ser una pareja (valor en Orca/Bambu, valor en Cura) cuando difieren."""
    lines: list[str] = []
    for title, cura in (("EN ORCA SLICER Y BAMBU STUDIO (los dos usan los mismos nombres)", False), ("EN CURA", True)):
        lines.append(title)
        for tab, orca, name, value in rows:
            if isinstance(value, tuple):
                value = value[1 if cura else 0]
            lines.append(f"- {name}: {value}" if cura else f"- {tab} › {orca}: {value}")
        lines.append("")
    return lines


def _rows(shape: str, w: float, accessory: bool = False, box: bool = False, bridges: bool = False) -> list[tuple]:
    """Filas (pestaña, opción Orca/Bambu, opción Cura, valor). `box`: la caja de luz y su marco; `bridges`: la caja
    con ranura, que lleva puentes."""
    if accessory:
        layer, walls, infill, outer, inner, support = "0,2", "3", "15 %", "60", "80", None
        brim = 0
    else:
        layer, walls, infill, outer, inner = LAYER, "5 (o más)", "100 %", "40", "60"
        brim = FACE["brim"].get(shape, 5)
        tree = shape == "esfera" or (shape == "cupula" and w > 60)
        support = "tree" if tree else None
    pct = lambda v: v.replace(" ", "")
    rows = [
        ("Filament", "Nozzle temperature", "Printing Temperature", "205-210 °C"),
        ("Filament", "Bed temperature (Textured/Smooth PEI)", "Build Plate Temperature", "60 °C"),
        ("Filament › Cooling", "Part cooling fan: Min/Max fan speed", "Fan Speed", "100 %"),
        ("Filament › Cooling", "Full fan speed at layer", "Regular Fan Speed at Layer", "3"),
        ("Quality", "Layer height", "Layer Height", f"{layer} mm" + ("" if accessory else " (0,08 mm para el máximo detalle)")),
        ("Strength", "Wall loops", "Wall Line Count", walls),
        ("Strength", "Sparse infill density", "Infill Density", infill),
        ("Speed", "Outer wall", "Outer Wall Speed", f"{outer} mm/s"),
        ("Speed", "Inner wall", "Inner Wall Speed", f"{inner} mm/s"),
        ("Speed", "Normal printing (Acceleration)", "Print Acceleration (activa «Enable Acceleration Control»)", "2000 mm/s²"),
    ]
    if not accessory:
        rows += [
            ("Quality", "Seam position", "Z Seam Alignment: User Specified + Z Seam Position", "Back (detrás)"),
            ("Quality", "Ironing type", "Enable Ironing", "No ironing (desactivado)"),
        ]
    if brim:
        rows.append(("Others", f"Brim type: Outer brim only; Brim width", "Build Plate Adhesion Type: Brim; Brim Width", f"{brim} mm"))
    elif accessory:
        rows.append(("Others", "Brim type", "Build Plate Adhesion Type", "No brim / Skirt, como prefieras"))
    if support == "tree":
        rows += [
            ("Support", "Enable support; Type", "Generate Support; Support Structure", "activado; tree(auto) / Tree"),
            ("Support", "On build plate only; Threshold angle", "Support Placement: Touching Buildplate; Support Overhang Angle",
             "solo desde la cama (nunca sobre la pieza); 50°"),
        ]
    else:
        rows.append(("Support", "Enable support", "Generate Support", "desactivado"))
    if box:   # el marco tiene que entrar en su alojamiento: compensa el «pie de elefante» de la primera capa
        rows.append(("Quality", "Elephant foot compensation", "Initial Layer Horizontal Expansion", ("0,1 mm", "-0,1 mm")))
    if bridges:
        rows += [
            ("Speed", "Bridge speed", "Bridge Skin Speed (activa «Enable Bridge Settings»)", "25 mm/s"),
            ("Quality", "Bridge flow", "Bridge Skin Flow", ("0,9", "90 %")),
            ("Filament › Cooling", "Overhang fan speed", "Bridge Fan Speed", "100 %"),
        ]
    return rows


def _orientation_steps(shape: str) -> list[str]:
    """Cómo girar la pieza en cada laminador, cuando hace falta."""
    if shape != "plana":
        return ["Esta pieza ya sale orientada: déjala como llega, apoyada en la cama."]
    return [
        "La plana sale tumbada (el grosor en vertical): hay que ponerla de pie.",
        "- Orca Slicer / Bambu Studio: selecciona la pieza, pulsa R (Rotate) o abre el panel de la izquierda «Object manipulation»",
        "  y pon Rotation X = 90°. Después usa «Place on face» o pulsa F para dejarla apoyada en la cama.",
        "- Cura: selecciona la pieza, pulsa R (Rotate) y arrastra el anillo rojo en pasos de 15° hasta 90°; o usa «Lay flat»",
        "  y gírala hasta que el lado largo quede sobre la cama.",
    ]


def _overhang_lines(shape: str, overhang: float, faces: int) -> list[str]:
    if faces:
        return ["Las esquinas de la caja son verticales: se imprime sin soportes. Una foto por cara, la primera mirando al frente."]
    if shape not in ("plana", "arco", "cilindro", "cono"):
        return []
    if overhang > 0:
        return [f"El relieve está limitado a {overhang:.0f}° de voladizo: imprímela sin soportes."]
    return ["Si al imprimir de pie ves hilos o gotas en el relieve, vuelve a generarla con «Voladizo máximo» de 45-50°."]


def settings(shape: str, size_mm: tuple[float, float, float], min_mm: float, max_mm: float,
             volume_mm3: float, overhang: float = 0.0, faces: int = 0) -> str:
    """Texto con los ajustes recomendados para esta pieza. `size_mm` es ancho × alto × fondo, con el alto
    tal como se imprime (de pie)."""
    w, h, d = size_mm
    f = lambda v: f"{v:.1f}".replace(".", ",")
    rows = _rows(shape, w)
    lines = [
        f"Ajustes de impresión recomendados — {PRINTER}",
        f"Pieza: {f'caja de {faces} caras' if faces else NAMES.get(shape, shape)}, {f(w)} × {f(h)} × {f(d)} mm, grosor de {f(min_mm)} a {f(max_mm)} mm",
        f"Filamento: unos {grams(volume_mm3):.0f} g de PLA",
        "",
        "MATERIAL",
        "- PLA blanco o natural. Los colores oscuros o con brillo metálico no dejan pasar la luz.",
        "- Boquilla de 0,4 mm. La pieza tiene que ser MACIZA (relleno 100 %) para que la luz pase igual por todas partes.",
        "",
        "QUÉ CAMBIAR EN TU LAMINADOR",
        "Parte del perfil de la Ender 3 V3 KE (Creality) y cambia solo estas opciones. Los nombres van como salen en",
        "inglés; si tu programa está en español, son las mismas opciones, en la misma pestaña.",
        "",
        *_slicer_blocks(rows),
        "ORIENTACIÓN",
        *_orientation_steps(shape),
        *[f"- {line}" for line in ORIENTATION.get(shape, [])],
        *[f"- {line}" for line in _overhang_lines(shape, overhang, faces)],
        "",
        "COMPROBACIONES",
    ]
    fits = w <= BED[0] and d <= BED[1] and h <= BED[2]
    lines.append(f"- Altura de impresión: {f(h)} mm "
                 + ("(cabe en la Ender 3 V3 KE)." if fits else "(NO cabe en la Ender 3 V3 KE: reduce el tamaño)."))
    lines.append("- Mira la pieza a contraluz en el visor antes de imprimir: lo claro será fino y lo oscuro grueso.")
    lines.append("- Si descargas el 3MF, ábrelo directamente en el laminador: cada pieza llega como un objeto aparte.")
    lines.append("")
    return "\n".join(lines)


def accessory_settings(notes: list[str], size_mm: tuple[float, float, float], grams_pla: float, box: bool = False,
                       bridges: bool = False) -> str:
    """Ajustes para la caja de luz o la base: aquí no pasa luz a través, así que se imprime rápido."""
    w, h, d = size_mm
    f = lambda v: f"{v:.1f}".replace(".", ",")
    rows = _rows("accesorio", w, accessory=True, box=box, bridges=bridges)
    return "\n".join([
        f"Ajustes de impresión recomendados — {PRINTER}",
        f"Accesorio: {f(w)} × {f(h)} × {f(d)} mm, unos {grams_pla:.0f} g de PLA",
        "",
        *notes,
        "",
        "MATERIAL",
        "- PLA de cualquier color opaco (negro o gris oscuro evitan que la luz se escape por las paredes).",
        "",
        "QUÉ CAMBIAR EN TU LAMINADOR",
        "Parte del perfil de la Ender 3 V3 KE (Creality) y cambia solo estas opciones. Los nombres van como salen en",
        "inglés; si tu programa está en español, son las mismas opciones, en la misma pestaña.",
        "",
        *_slicer_blocks(rows),
        "ORIENTACIÓN",
        "- Imprímelo tal como sale del STL, sin girarlo y sin soportes. Si descargas el 3MF, cada pieza viene ya colocada.",
        "",
        "LUZ",
        "- Luz LED USB de 5 V en blanco cálido (2700-3000 K): tira adhesiva o módulo pequeño.",
        "- Prueba la litofanía con la luz antes de pegar nada: más luz no siempre se ve mejor.",
        "",
    ])
