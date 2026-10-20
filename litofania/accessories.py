"""Fase 8: cajas de luz y soportes con hueco para una luz LED USB de 5 V.

Cada accesorio se calcula a partir de la litofanía ya generada (sus medidas, su grosor máximo y, en la
plana recortada, su contorno) y sale orientado como se imprime. Las piezas se construyen con operaciones
booleanas de manifold3d, así siempre son mallas cerradas.

- Plana: caja de luz. La litofanía entra por arriba en una ranura detrás de un marco frontal cuya ventana
  sigue el contorno; detrás queda la cámara para la tira LED y, abajo en la trasera, el paso del cable.
  Se imprime tumbada sobre la trasera.
- Cilindro y cúpula: base redonda con una ranura circular donde encaja la pieza y un hueco central abierto
  hacia arriba para la luz.
- Esfera: peana con un collar que entra en la abertura de la esfera y el hueco de la luz dentro.
- Arco: base en forma de sector con la ranura del arco y un hueco delante de la cara cóncava para la luz.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold

WALL = 2.4          # paredes: 6 pasadas de 0,4 mm
FLOOR = 2.0         # suelo de las bases
LIP = 2.0           # grosor del marco frontal de la caja
GROOVE = 6.0        # profundidad de las ranuras de las bases
CABLE = (9.0, 6.0)  # paso del cable USB: ancho × alto
LED_MIN = 24.0      # diámetro mínimo del hueco de la luz (un LED USB pequeño cabe)
SEGMENTS = 128


@dataclass
class Accessory:
    name: str
    verts: np.ndarray
    faces: np.ndarray
    size_mm: tuple[float, float, float]
    notes: list[str]


def _box(x0, y0, z0, x1, y1, z1) -> Manifold:
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def _cyl(r: float, z0: float, z1: float) -> Manifold:
    return Manifold.cylinder(z1 - z0, r, r, SEGMENTS).translate((0, 0, z0))


def _ring(r_in: float, r_out: float, z0: float, z1: float) -> Manifold:
    return _cyl(r_out, z0, z1) - _cyl(max(0.01, r_in), z0 - 1, z1 + 1)


def _finish(name: str, solid: Manifold, notes: list[str]) -> Accessory:
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    faces = np.asarray(mesh.tri_verts, dtype=np.int64)
    verts = verts - verts.min(axis=0)
    size = tuple(float(v) for v in verts.max(axis=0))
    return Accessory(name, verts, faces, size, notes)


def outline_loops(mask: np.ndarray, mm_per_px: float) -> list[list[tuple[float, float]]]:
    """Contorno (en mm, y hacia arriba) de los cuadros de la rejilla que tienen las 4 esquinas dentro de
    la máscara: el mismo borde que tiene la plana recortada."""
    rows, cols = mask.shape
    keep = mask[:-1, :-1] & mask[:-1, 1:] & mask[1:, :-1] & mask[1:, 1:]
    ii, jj = np.nonzero(keep)
    # Cada cuadro aporta sus 4 aristas en sentido antihorario (x = columna, y = -fila); las compartidas se anulan.
    x0, x1 = jj, jj + 1
    y0, y1 = -(ii + 1), -ii
    starts = np.concatenate([np.column_stack([x0, y0]), np.column_stack([x1, y0]),
                             np.column_stack([x1, y1]), np.column_stack([x0, y1])])
    ends = np.concatenate([np.column_stack([x1, y0]), np.column_stack([x1, y1]),
                           np.column_stack([x0, y1]), np.column_stack([x0, y0])])
    key = lambda a: a[:, 0].astype(np.int64) * 1_000_003 + a[:, 1].astype(np.int64)
    ks, ke = key(starts), key(ends)
    edge = ks * 4_000_000_000_000 + ke
    rev = ke * 4_000_000_000_000 + ks
    border = ~np.isin(edge, rev)
    nxt: dict[int, list[int]] = {}
    for s, e in zip(ks[border].tolist(), ke[border].tolist()):
        nxt.setdefault(s, []).append(e)
    pos = {k: tuple(p) for k, p in zip(ks[border].tolist(), starts[border].tolist())}
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, k = [], start
        while k in nxt:
            loop.append(pos[k])
            e = nxt[k].pop()
            if not nxt[k]:
                del nxt[k]
            k = e
        if len(loop) >= 3:
            loops.append([(x * mm_per_px, (y + rows - 1) * mm_per_px) for x, y in loop])
    return loops


def light_box(width: float, height: float, t_max: float, frame: float, depth: float = 30.0,
              clearance: float = 0.4, outline: list | None = None) -> Accessory:
    """Caja de luz para la plana, tumbada sobre la trasera: x = ancho, y = alto, z = fondo (delante arriba)."""
    lip = max(2.5, frame)                        # el marco frontal tapa el marco de la litofanía
    wo = width + clearance + 2 * WALL
    ho = height + clearance + WALL               # por arriba la ranura queda abierta
    slot = t_max + clearance
    do = WALL + depth + slot + LIP
    box = _box(0, 0, 0, wo, ho, do)
    box -= _box(WALL, WALL, WALL, wo - WALL, ho - WALL, WALL + depth + 0.01)          # cámara de luz
    box -= _box(WALL, WALL, WALL + depth, wo - WALL, ho + 1, WALL + depth + slot)     # ranura de la litofanía
    ox, oy = WALL + clearance / 2, WALL                                              # esquina de la litofanía
    if outline:
        low = np.min([np.min(loop, axis=0) for loop in outline], axis=0)   # contorno pegado a la esquina
        window = CrossSection([np.asarray(loop) - low + (ox, oy) for loop in outline], FillRule.EvenOdd)
        window = window.offset(-lip, JoinType.Round)
    else:
        window = CrossSection.square((width - 2 * lip, height - 2 * lip)).translate((ox + lip, oy + lip))
    box -= window.extrude(LIP + 2).translate((0, 0, do - LIP - 1))
    cw, ch = CABLE
    box -= _box(wo / 2 - cw / 2, WALL + 3, -1, wo / 2 + cw / 2, WALL + 3 + ch, WALL + 1)   # cable por la trasera
    notes = [
        "Caja de luz para la litofanía plana. Imprímela tal como sale: tumbada sobre la trasera, sin soportes.",
        f"La litofanía entra por la ranura de arriba (holgura {clearance:.1f} mm).",
        f"Cámara de luz de {depth:.0f} mm de fondo: pega una tira LED USB de 5 V (blanco cálido) en la trasera,",
        "por dentro, y saca el cable por el agujero de abajo.",
    ]
    return _finish("caja", box, notes)


def round_base(radius: float, t_max: float, height: float = 25.0, clearance: float = 0.4,
               kind: str = "cilindro") -> Accessory:
    """Base redonda para el cilindro o la cúpula: ranura circular para la pared y hueco central para la luz."""
    r_groove_out = radius + clearance / 2
    r_groove_in = radius - t_max - clearance / 2
    r_out = r_groove_out + WALL
    r_led = max(r_groove_in - WALL, 3.0)
    base = _cyl(r_out, 0, height)
    base -= _ring(r_groove_in, r_groove_out, height - GROOVE, height + 1)
    base -= _cyl(r_led, FLOOR, height + 1)
    cw, ch = CABLE
    base -= _box(0, -cw / 2, -1, r_out + 1, cw / 2, ch)                 # canal del cable por debajo
    base -= _cyl(min(r_led, cw / 2 + 1), -1, FLOOR + 1)                  # y paso al hueco de la luz
    what = "el cilindro" if kind == "cilindro" else "la cúpula"
    notes = [
        f"Base para {what}: imprímela tal como sale, sin soportes.",
        f"La pieza encaja en la ranura circular de arriba ({GROOVE:.0f} mm de profundidad, holgura {clearance:.1f} mm).",
        f"Hueco central de {2 * r_led:.0f} mm para la luz LED USB de 5 V; el cable sale por el canal de abajo.",
    ]
    if 2 * r_led < LED_MIN:
        notes.append("El hueco es pequeño para un LED USB: usa uno de tipo tira o aumenta el diámetro.")
    return _finish("base", base, notes)


def sphere_stand(hole: float, height: float = 25.0, clearance: float = 0.4) -> Accessory:
    """Peana para la esfera: la abertura apoya en la cara de arriba y un collar la centra."""
    r_collar_out = hole / 2 - clearance / 2
    r_collar_in = max(r_collar_out - WALL, 3.0)
    r_out = hole / 2 + 8.0
    stand = _cyl(r_out, 0, height) + _ring(r_collar_in, r_collar_out, height - 0.01, height + 5)
    stand -= _cyl(r_collar_in, FLOOR, height + 6)
    cw, ch = CABLE
    stand -= _box(0, -cw / 2, -1, r_out + 1, cw / 2, ch)
    stand -= _cyl(min(r_collar_in, cw / 2 + 1), -1, FLOOR + 1)
    notes = [
        "Peana para la esfera: imprímela tal como sale, sin soportes.",
        f"La abertura de la esfera ({hole:.0f} mm) apoya arriba y el collar de 5 mm la centra.",
        f"Hueco de {2 * r_collar_in:.0f} mm para la luz LED USB de 5 V; el cable sale por el canal de abajo.",
    ]
    if 2 * r_collar_in < LED_MIN:
        notes.append("El hueco es pequeño para un LED USB: agranda la abertura de la esfera si puedes.")
    return _finish("peana", stand, notes)


def arc_base(radius: float, angle_deg: float, t_max: float, height: float = 20.0,
             clearance: float = 0.4) -> Accessory:
    """Base del arco: sector con la ranura del arco y un hueco para la luz delante de la cara cóncava.

    Mismo sistema que shapes: el arco va de -θ/2 a θ/2 con la cara convexa hacia +y (x = -r·sen a, y = r·cos a)."""
    theta = math.radians(angle_deg)
    margin = (WALL + 2) / radius
    r_out = radius + clearance / 2 + WALL
    r_g_out, r_g_in = radius + clearance / 2, radius - t_max - clearance / 2
    r_led_out = r_g_in - WALL
    r_led_in = max(0.0, r_led_out - 18.0)

    def sector(r_in: float, r_o: float, a0: float, a1: float) -> CrossSection:
        n = max(8, int(SEGMENTS * (a1 - a0) / (2 * math.pi)) + 2)
        a = np.linspace(a0, a1, n)
        outer = [(-r_o * math.sin(v), r_o * math.cos(v)) for v in a]
        inner = [(-r_in * math.sin(v), r_in * math.cos(v)) for v in a[::-1]] if r_in > 0 else [(0.0, 0.0)]
        return CrossSection([np.asarray(outer + inner)], FillRule.EvenOdd)

    a0, a1 = -theta / 2 - margin, theta / 2 + margin
    base = sector(max(0.0, r_led_in - WALL), r_out, a0, a1).extrude(height)
    base -= sector(r_g_in, r_g_out, -theta / 2 - 0.5 / radius, theta / 2 + 0.5 / radius).extrude(GROOVE + 1) \
        .translate((0, 0, height - GROOVE))
    base -= sector(r_led_in, r_led_out, -theta / 2 + margin, theta / 2 - margin).extrude(height) \
        .translate((0, 0, FLOOR))
    cw, ch = CABLE
    y_led = (r_led_in + r_led_out) / 2
    base -= _box(-cw / 2, -1e3, -1, cw / 2, y_led, ch)                  # canal del cable hacia atrás
    notes = [
        "Base para el arco: imprímela tal como sale, sin soportes.",
        f"El arco encaja en la ranura curva ({GROOVE:.0f} mm de profundidad, holgura {clearance:.1f} mm).",
        "Delante de la cara cóncava queda un canal para una tira LED USB de 5 V; el cable sale por debajo.",
    ]
    return _finish("base", base, notes)

