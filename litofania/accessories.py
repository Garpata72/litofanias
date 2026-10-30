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
- Cilindro y lámpara cónica: también un aro con radios para colgarlas de un casquillo E27 o E14.

Las bases redondas y la peana pueden llevar un hueco para un portapilas (abierto por debajo) o un aro que
centra una vela LED; la caja de luz puede ser de escritorio, con una peana aparte que la inclina hacia atrás.
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
BATTERY = (67.0, 48.0, 18.0)   # portapilas de 3 pilas AA con interruptor: largo × ancho × alto
TEA_LIGHT = 39.0    # diámetro de una vela LED (tea light)
SOCKETS = {"E27": 40.5, "E14": 29.0}   # diámetro del agujero del aro para el casquillo
GAP = 10.0          # separación entre piezas de un mismo accesorio
FRAME_T = 2.0       # grosor del marco frontal extraíble
FIT = 0.15          # holgura por lado entre el marco extraíble y su alojamiento
BED_XY = 220.0      # cama de la Ender 3 V3 KE


@dataclass
class Accessory:
    name: str
    verts: np.ndarray
    faces: np.ndarray
    size_mm: tuple[float, float, float]
    notes: list[str]
    parts: list | None = None    # varias piezas: [(nombre, verts, faces)], ya colocadas una al lado de otra


def _box(x0, y0, z0, x1, y1, z1) -> Manifold:
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def _cyl(r: float, z0: float, z1: float) -> Manifold:
    return Manifold.cylinder(z1 - z0, r, r, SEGMENTS).translate((0, 0, z0))


def _ring(r_in: float, r_out: float, z0: float, z1: float) -> Manifold:
    return _cyl(r_out, z0, z1) - _cyl(max(0.01, r_in), z0 - 1, z1 + 1)


def _mesh(solid: Manifold) -> tuple[np.ndarray, np.ndarray]:
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    return verts - verts.min(axis=0), np.asarray(mesh.tri_verts, dtype=np.int64)


def _finish(name: str, solid: Manifold, notes: list[str], extra: list[tuple[str, Manifold]] = ()) -> Accessory:
    """Pieza lista, apoyada en z = 0 desde el origen. Con `extra`, las demás piezas van a su derecha (en x),
    o en otra fila si ya no caben en la cama."""
    verts, faces = _mesh(solid)
    parts = [(name, verts, faces)]
    x, y, row = verts[:, 0].max() + GAP, 0.0, verts[:, 1].max()
    for label, m in extra:
        v, f = _mesh(m)
        if x + v[:, 0].max() > BED_XY and x > 0:
            x, y, row = 0.0, row + GAP, row + GAP + v[:, 1].max()
        else:
            row = max(row, y + v[:, 1].max())
        v = v + (x, y, 0)
        x = v[:, 0].max() + GAP
        parts.append((label, v, f))
    all_v = np.vstack([p[1] for p in parts])
    offsets = np.cumsum([0] + [len(p[1]) for p in parts[:-1]])
    all_f = np.vstack([p[2] + o for p, o in zip(parts, offsets)])
    size = tuple(float(v) for v in all_v.max(axis=0))
    return Accessory(name, all_v, all_f, size, notes, parts if extra else None)


def _wavy_disc(r: float, waves: int = 0, amp: float = 0.0) -> CrossSection:
    """Círculo de radio `r` (con ondas como las de la pared de la lámpara), en el mismo sistema que
    shapes: x = -r·sen a, y = r·cos a."""
    if not waves or not amp:
        return CrossSection.circle(r, SEGMENTS)
    n = max(SEGMENTS, 24 * waves)
    a = 2 * np.pi * np.arange(n) / n - np.pi
    rr = r + amp * np.sin(waves * a)
    return CrossSection([np.column_stack([-rr * np.sin(a), rr * np.cos(a)])], FillRule.EvenOdd)


def _wavy_ring(r_in: float, r_out: float, z0: float, z1: float, waves: int = 0, amp: float = 0.0) -> Manifold:
    return (_wavy_disc(r_out, waves, amp) - _wavy_disc(r_in, waves, amp)).extrude(z1 - z0).translate((0, 0, z0))


def _battery_pocket(solid: Manifold, r_room: float, battery: tuple[float, float, float], z_led: float):
    """Hueco del portapilas abierto por debajo, centrado, y paso del cable hasta el hueco de la luz."""
    L, W, H = battery
    if math.hypot(L / 2, W / 2) > r_room:
        raise ValueError(f"El portapilas de {L:.0f} × {W:.0f} mm no cabe en esta base: agranda la pieza o usa uno más pequeño")
    solid -= _box(-L / 2, -W / 2, -1, L / 2, W / 2, H)
    return solid - _cyl(2.5, H - 1, z_led + 1)


def _tea_light(solid: Manifold, r_led: float, z_floor: float, diameter: float) -> Manifold:
    """Aro bajo en el suelo del hueco de la luz que deja la vela LED centrada."""
    r = diameter / 2 + 0.5
    if r_led < r:
        raise ValueError(f"La vela LED de {diameter:.0f} mm no cabe en el hueco de la luz ({2 * r_led:.0f} mm)")
    if r_led - r >= 1.0:
        solid += _ring(r, r_led + 0.01, z_floor - 0.01, z_floor + 5)
    return solid


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


def _window(outline, width, height, ox, oy, lip) -> CrossSection:
    """Ventana del marco frontal: el contorno de la litofanía recortado `lip` hacia dentro (o un rectángulo)."""
    if outline:
        low = np.min([np.min(loop, axis=0) for loop in outline], axis=0)   # contorno pegado a la esquina
        window = CrossSection([np.asarray(loop) - low + (ox, oy) for loop in outline], FillRule.EvenOdd)
        return window.offset(-lip, JoinType.Round)
    return CrossSection.square((width - 2 * lip, height - 2 * lip)).translate((ox + lip, oy + lip))


def _fit_note(wo: float, ho: float) -> list[str]:
    if max(wo, ho) > BED_XY or min(wo, ho) > BED_XY:
        raise ValueError(f"La caja ({wo:.0f} × {ho:.0f} mm) no cabe en la cama de {BED_XY:.0f} mm: reduce la litofanía")
    if max(wo, ho) > BED_XY - 12:
        diag = (wo + ho) / math.sqrt(2) <= BED_XY
        return [f"Entra muy justo en la cama ({wo:.0f} × {ho:.0f} mm). Quita el borde (brim) o el «skirt»"
                + (" y gírala 45° en el laminador." if diag else ".")]
    return []


def light_box(width: float, height: float, t_max: float, frame: float, depth: float = 30.0,
              clearance: float = 0.4, outline: list | None = None, desk: bool = False,
              tilt_deg: float = 10.0, mount: str = "marco") -> Accessory:
    """Caja de luz para la plana, tumbada sobre la trasera: x = ancho, y = alto, z = fondo (delante arriba).

    `mount` = "marco": bandeja abierta por delante con un repecho donde descansa la litofanía y un marco
    frontal extraíble (pieza aparte) que la sujeta; nada queda en el aire al imprimir. `mount` = "ranura":
    la litofanía entra por arriba en una ranura tapada por un marco fijo (lleva puentes al imprimir).

    Con `desk` va acompañada de una peana en la que encaja de pie, inclinada `tilt_deg` grados hacia atrás,
    y el cable sale por la trasera por encima de la peana."""
    if mount == "marco":
        return _frame_box(width, height, t_max, frame, depth, clearance, outline, desk, tilt_deg)
    lip = max(2.5, frame)                        # el marco frontal tapa el marco de la litofanía
    wo = width + clearance + 2 * WALL
    ho = height + clearance + WALL               # por arriba la ranura queda abierta
    slot = t_max + clearance
    do = WALL + depth + slot + LIP
    box = _box(0, 0, 0, wo, ho, do)
    box -= _box(WALL, WALL, WALL, wo - WALL, ho - WALL, WALL + depth + 0.01)          # cámara de luz
    box -= _box(WALL, WALL, WALL + depth, wo - WALL, ho + 1, WALL + depth + slot)     # ranura de la litofanía
    ox, oy = WALL + clearance / 2, WALL                                              # esquina de la litofanía
    window = _window(outline, width, height, ox, oy, lip)
    box -= window.extrude(LIP + 2).translate((0, 0, do - LIP - 1))
    cw, ch = CABLE
    cable_y = WALL + (22 if desk else 3)                       # en la de escritorio, por encima de la peana
    box -= _box(wo / 2 - cw / 2, cable_y, -1, wo / 2 + cw / 2, cable_y + ch, WALL + 1)   # cable por la trasera
    notes = [
        "Caja de luz para la litofanía plana. Imprímela tal como sale: tumbada sobre la trasera, sin soportes.",
        f"La litofanía entra por la ranura de arriba (holgura {clearance:.1f} mm).",
        f"Cámara de luz de {depth:.0f} mm de fondo: pega una tira LED USB de 5 V (blanco cálido) en la trasera,",
        "por dentro, y saca el cable por el agujero de atrás.",
    ]
    notes += _fit_note(wo, ho)
    if not desk:
        return _finish("caja", box, notes)
    notes += _desk_notes(tilt_deg)
    return _finish("caja", box, notes, [("peana", desk_stand(wo, do, clearance, tilt_deg))])


def _desk_notes(tilt_deg: float) -> list[str]:
    return [
        f"Peana de escritorio (pieza aparte): la caja encaja de pie en su hueco, inclinada {tilt_deg:.0f}° hacia atrás.",
        "Imprime la peana apoyada en su base, sin soportes.",
    ]


def _frame_box(width, height, t_max, frame, depth, clearance, outline, desk, tilt_deg) -> Accessory:
    """Caja de luz de dos piezas: bandeja con repecho + marco frontal extraíble (ver `light_box`)."""
    lip = max(2.5, frame)                        # anchura del repecho y del borde del marco
    c = clearance                                # holgura por lado de la litofanía en su alojamiento
    rw, rh = width + 2 * c, height + 2 * c
    wo, ho = rw + 2 * WALL, rh + 2 * WALL
    slot = t_max + 0.3                           # hueco entre repecho y marco para la litofanía
    rebate = slot + FRAME_T                      # el marco queda enrasado con el borde de la bandeja
    do = WALL + depth + rebate
    tray = _box(0, 0, 0, wo, ho, do)
    tray -= _box(WALL + lip, WALL + lip, WALL, wo - WALL - lip, ho - WALL - lip, WALL + depth + 0.01)   # cámara
    tray -= _box(WALL, WALL, WALL + depth, wo - WALL, ho - WALL, do + 1)                                # alojamiento
    tray -= _cyl(6.0, do - FRAME_T - 0.5, do + 1).translate((wo / 2, ho, 0))     # muesca para sacar el marco con la uña
    cw, ch = CABLE
    cable_y = WALL + (22 if desk else 3)
    tray -= _box(wo / 2 - cw / 2, cable_y, -1, wo / 2 + cw / 2, cable_y + ch, WALL + 1)
    ox, oy = WALL + c, WALL + c
    cover = _box(WALL + FIT, WALL + FIT, 0, wo - WALL - FIT, ho - WALL - FIT, FRAME_T)
    cover -= _window(outline, width, height, ox, oy, lip).extrude(FRAME_T + 2).translate((0, 0, -1))
    notes = [
        "Caja de luz de dos piezas para la litofanía plana: la bandeja y el marco frontal que se quita y se pone.",
        "Bandeja: imprímela tal como sale, tumbada sobre la trasera, sin soportes ni puentes.",
        "Marco: imprímelo apoyado por la cara lisa (tal como sale), sin soportes. Encaja a presión.",
        f"Montaje: pon la litofanía en el alojamiento (holgura {c:.1f} mm por lado),,",
        "y presiona el marco encima. Para sacarlo, mete la uña en la muesca de arriba.",
        f"Cámara de luz de {depth:.0f} mm de fondo: pega una tira LED USB de 5 V (blanco cálido) en la trasera,",
        "por dentro, y saca el cable por el agujero de atrás.",
        f"Si el marco queda flojo, pega una tira fina de cinta en su canto; si no entra, líjalo (holgura {FIT:.2f} mm).",
    ] + _fit_note(wo, ho)
    extra = [("marco", cover)]
    if desk:
        notes += _desk_notes(tilt_deg)
        extra.append(("peana", desk_stand(wo, do, clearance, tilt_deg)))
    return _finish("caja", tray, notes, extra)


def desk_stand(box_w: float, box_d: float, clearance: float = 0.4, tilt_deg: float = 10.0) -> Manifold:
    """Peana para la caja de luz de pie: un bloque con un hueco del tamaño de la base de la caja, inclinado
    hacia atrás (+y) `tilt_deg` grados. La caja entra al menos 8 mm por delante y más por detrás."""
    a = math.radians(tilt_deg)
    w, d = box_w + clearance, box_d + clearance
    rise = d / 2 * math.sin(a)
    depth = 8.0 + rise                         # hondura en el centro del hueco
    wp, dp = w + 2 * 8.0, d + 2 * 20.0
    hp = FLOOR + depth + rise
    stand = _box(0, 0, 0, wp, dp, hp)
    pocket = _box(-w / 2, -d / 2, 0, w / 2, d / 2, 60).rotate((-tilt_deg, 0, 0))   # se inclina hacia +y
    stand -= pocket.translate((wp / 2, dp / 2, hp - depth))
    cw, ch = CABLE
    stand -= _box(wp / 2 - cw / 2, dp / 2, hp - 4, wp / 2 + cw / 2, dp + 1, hp + 1)   # muesca para el cable
    return stand


def round_base(radius: float, t_max: float, height: float = 25.0, clearance: float = 0.4,
               kind: str = "cilindro", waves: int = 0, wave_mm: float = 0.0,
               battery: tuple[float, float, float] | None = None, tea_light: float | None = None) -> Accessory:
    """Base redonda para el cilindro, la lámpara cónica o la cúpula: ranura para la pared (con sus ondas,
    si las tiene) y hueco central para la luz. `t_max` es el grosor horizontal de la pared.

    `battery` (largo, ancho, alto) añade un hueco abierto por debajo para un portapilas, y la base crece lo
    necesario; `tea_light` (diámetro) pone en el suelo del hueco un aro que centra una vela LED."""
    if battery:
        height = max(height, battery[2] + FLOOR + GROOVE + 4)
    floor = battery[2] + FLOOR if battery else FLOOR
    r_groove_out = radius + clearance / 2
    r_groove_in = radius - t_max - clearance / 2
    r_out = r_groove_out + WALL + wave_mm
    r_led = max(r_groove_in - WALL - wave_mm, 3.0)
    base = _cyl(r_out, 0, height)
    base -= _wavy_ring(r_groove_in, r_groove_out, height - GROOVE, height + 1, waves, wave_mm)
    base -= _cyl(r_led, floor, height + 1)
    cw, ch = CABLE
    base -= _box(0, -cw / 2, -1, r_out + 1, cw / 2, ch)                 # canal del cable por debajo
    base -= _cyl(min(r_led, cw / 2 + 1), -1, floor + 1)                  # y paso al hueco de la luz
    if battery:
        base = _battery_pocket(base, r_out - WALL, battery, floor)
    if tea_light:
        base = _tea_light(base, r_led, floor, tea_light)
    what = {"cilindro": "el cilindro", "cono": "la lámpara cónica"}.get(kind, "la cúpula")
    notes = [
        f"Base para {what}: imprímela tal como sale, sin soportes.",
        f"La pieza encaja en la ranura de arriba ({GROOVE:.0f} mm de profundidad, holgura {clearance:.1f} mm).",
        f"Hueco central de {2 * r_led:.0f} mm para la luz LED USB de 5 V; el cable sale por el canal de abajo.",
    ]
    notes += _light_notes(r_led, battery, tea_light)
    return _finish("base", base, notes)


def _light_notes(r_led: float, battery, tea_light) -> list[str]:
    notes = []
    if battery:
        notes.append(f"Por debajo, hueco de {battery[0]:.0f} × {battery[1]:.0f} × {battery[2]:.0f} mm para el portapilas; "
                     "su cable sube por el agujero central hasta la luz.")
    if tea_light:
        notes.append(f"En el suelo del hueco, un aro centra una vela LED de {tea_light:.0f} mm.")
    elif 2 * r_led < LED_MIN:
        notes.append("El hueco es pequeño para un LED USB: usa uno de tipo tira o aumenta el diámetro.")
    return notes


def socket_ring(radius: float, t_max: float, socket_mm: float = 40.5, clearance: float = 0.4,
                waves: int = 0, wave_mm: float = 0.0, spokes: int = 3) -> Accessory:
    """Aro para colgar el cilindro o la lámpara cónica de un casquillo: un borde con ranura que encaja en el
    canto de la pared, unido con radios a un anillo del diámetro del casquillo (E27, E14…).

    Sale con la ranura hacia abajo, abierta a la cama, y se imprime sin soportes (el techo de la ranura
    es un puente corto). `radius` es el radio exterior del canto donde va y `t_max` el grosor de la pared."""
    r_g_out = radius + clearance / 2
    r_g_in = radius - t_max - clearance / 2
    r_rim_in, r_rim_out = r_g_in - WALL, r_g_out + WALL
    r_hub_in = socket_mm / 2
    r_hub_out = r_hub_in + 4.0
    if r_hub_out + 6 > r_rim_in - wave_mm:
        raise ValueError(f"La lámpara es demasiado estrecha para un aro de casquillo de {socket_mm:.0f} mm")
    top = GROOVE + 2.4
    ring = _wavy_ring(r_rim_in, r_rim_out, 0, top, waves, wave_mm)
    ring -= _wavy_ring(r_g_in, r_g_out, -1, GROOVE, waves, wave_mm)
    ring += _ring(r_hub_in, r_hub_out, 0, 5.0)
    length = r_rim_in - wave_mm - r_hub_out + 2
    for k in range(spokes):
        bar = _box(r_hub_out - 1, -3.0, 0, r_hub_out - 1 + length, 3.0, 4.0)
        ring += bar.rotate((0, 0, 90 + 360 * k / spokes))
    notes = [
        "Aro para el casquillo: imprímelo tal como sale, con la ranura hacia la cama y sin soportes.",
        f"La ranura ({GROOVE:.0f} mm de profundidad, holgura {clearance:.1f} mm) encaja en el canto de la lámpara.",
        f"El anillo central tiene {socket_mm:.1f} mm de agujero: pasa por él la rosca del casquillo y apriétalo con su arandela.",
        "Usa una bombilla LED (se calienta poco): las de filamento o halógenas pueden deformar el PLA.",
    ]
    return _finish("aro", ring, notes)


def sphere_stand(hole: float, height: float = 25.0, clearance: float = 0.4, neck_t: float = 0.0,
                 battery: tuple[float, float, float] | None = None, tea_light: float | None = None) -> Accessory:
    """Peana para la esfera: la abertura apoya en la cara de arriba y un collar la centra. Si la esfera
    lleva cuello (`neck_t` = su grosor), el cuello entra en una ranura circular de la peana.

    `battery` y `tea_light` como en round_base."""
    if battery:
        height = max(height, battery[2] + FLOOR + GROOVE + 4)
    floor = battery[2] + FLOOR if battery else FLOOR
    r_out = hole / 2 + 8.0 + (WALL if neck_t else 0)
    if neck_t:   # ranura para el cuello: su cara exterior es la de la abertura
        r_g_out, r_g_in = hole / 2 + clearance / 2, hole / 2 - neck_t - clearance / 2
        r_led = max(r_g_in - WALL, 3.0)
        stand = _cyl(r_out, 0, height) - _ring(r_g_in, r_g_out, height - GROOVE, height + 1)
        stand -= _cyl(r_led, floor, height + 1)
        fit = f"El cuello de la esfera entra en la ranura de arriba ({GROOVE:.0f} mm, holgura {clearance:.1f} mm)."
    else:
        r_collar_out = hole / 2 - clearance / 2
        r_led = max(r_collar_out - WALL, 3.0)
        stand = _cyl(r_out, 0, height) + _ring(r_led, r_collar_out, height - 0.01, height + 5)
        stand -= _cyl(r_led, floor, height + 6)
        fit = f"La abertura de la esfera ({hole:.0f} mm) apoya arriba y el collar de 5 mm la centra."
    cw, ch = CABLE
    stand -= _box(0, -cw / 2, -1, r_out + 1, cw / 2, ch)
    stand -= _cyl(min(r_led, cw / 2 + 1), -1, floor + 1)
    if battery:
        stand = _battery_pocket(stand, r_out - WALL, battery, floor)
    if tea_light:
        stand = _tea_light(stand, r_led, floor, tea_light)
    notes = [
        "Peana para la esfera: imprímela tal como sale, sin soportes.",
        fit,
        f"Hueco de {2 * r_led:.0f} mm para la luz LED USB de 5 V; el cable sale por el canal de abajo.",
    ]
    notes += _light_notes(r_led, battery, tea_light)
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

