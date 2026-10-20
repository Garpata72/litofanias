"""Ajustes de impresión recomendados para la Creality Ender 3 V3 KE, en un texto que acompaña al STL."""
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


def settings(shape: str, size_mm: tuple[float, float, float], min_mm: float, max_mm: float,
             volume_mm3: float) -> str:
    """Texto con los ajustes recomendados para esta pieza. `size_mm` es ancho × alto × fondo, con el alto
    tal como se imprime (de pie)."""
    w, h, d = size_mm
    f = lambda v: f"{v:.1f}".replace(".", ",")
    lines = [
        f"Ajustes de impresión recomendados — {PRINTER}",
        f"Pieza: {NAMES.get(shape, shape)}, {f(w)} × {f(h)} × {f(d)} mm, grosor de {f(min_mm)} a {f(max_mm)} mm",
        f"Filamento: unos {grams(volume_mm3):.0f} g de PLA",
        "",
        "MATERIAL",
        "- PLA blanco o natural. Los colores oscuros o con brillo metálico no dejan pasar la luz.",
        "- Boquilla 205-210 °C, cama 60 °C. Ventilador al 100 % desde la capa 3.",
        "",
        "CALIDAD",
        "- Boquilla 0,4 mm. Altura de capa 0,12 mm (0,08 mm si quieres el máximo detalle).",
        "- Relleno 100 % y 5 paredes o más: la pieza tiene que ser maciza para que la luz pase igual.",
        "- Velocidad: 60 mm/s; pared exterior a 40 mm/s. Aceleración moderada (2000 mm/s²).",
        "- Sin «planchado» (ironing) ni costura aleatoria: deja la costura en la parte de atrás.",
        "",
        "ORIENTACIÓN",
        *[f"- {line}" for line in ORIENTATION.get(shape, [])],
        "",
        "COMPROBACIONES",
    ]
    fits = w <= BED[0] and d <= BED[1] and h <= BED[2]
    lines.append(f"- Altura de impresión: {f(h)} mm "
                 + ("(cabe en la Ender 3 V3 KE)." if fits else "(NO cabe en la Ender 3 V3 KE: reduce el tamaño)."))
    lines.append("- Mira la pieza a contraluz en el visor antes de imprimir: lo claro será fino y lo oscuro grueso.")
    lines.append("")
    return "\n".join(lines)


def accessory_settings(notes: list[str], size_mm: tuple[float, float, float], grams_pla: float) -> str:
    """Ajustes para la caja de luz o la base: aquí no pasa luz a través, así que se imprime rápido."""
    w, h, d = size_mm
    f = lambda v: f"{v:.1f}".replace(".", ",")
    return "\n".join([
        f"Ajustes de impresión recomendados — {PRINTER}",
        f"Accesorio: {f(w)} × {f(h)} × {f(d)} mm, unos {grams_pla:.0f} g de PLA",
        "",
        *notes,
        "",
        "AJUSTES",
        "- PLA de cualquier color opaco (negro o gris oscuro evitan que la luz se escape por las paredes).",
        "- Capa 0,2 mm, 3 paredes, relleno 15 %, velocidad normal.",
        "- Sin soportes.",
        "",
        "LUZ",
        "- Luz LED USB de 5 V en blanco cálido (2700-3000 K): tira adhesiva o módulo pequeño.",
        "- Prueba la litofanía con la luz antes de pegar nada: más luz no siempre se ve mejor.",
        "",
    ])
