"""Instrucciones de impresión y de acabado (resina UV) para las piezas multicolor: la foto en color tipo
HueForge y los posavasos. Mismo estilo que printing.py: qué abrir, qué cambiar en Orca/Bambu y Cura, y cómo
hacer los cambios de filamento a mano en la Ender 3 V3 KE (un solo extrusor, M600)."""
from __future__ import annotations

from litofania.printing import BED, PRINTER, _slicer_blocks, grams

f1 = lambda v: f"{v:.1f}".replace(".", ",")
f2 = lambda v: f"{v:.2f}".replace(".", ",")

BED_PREP = [
    "ANTES DE IMPRIMIR",
    "- Limpia la cama con alcohol isopropílico de 99 % y un paño de microfibra, y no la toques con los dedos: la grasa",
    "  despega las líneas finas de la primera capa.",
    "- Limpia también la punta de la boquilla. El polvo o una gota quemada quedan aplastados bajo la primera capa y",
    "  emborronan el borde entre colores (se nota mucho entre blanco y negro).",
    "- Z-hop (la boquilla sube un poco en cada desplazamiento): en el proyecto de Orca va a 0,4 mm para que, al viajar",
    "  de un sitio a otro, la boquilla pase por encima de lo ya impreso en vez de rozarlo o arrastrar hilos.",
    "",
]

TPU = [
    "VARIANTE FLEXIBLE (TPU o PLA Flex, antideslizante)",
    "- Funciona bien con extrusor directo como el de la KE y cambios manuales (un AMS no puede con filamento flexible).",
    "- Boquilla 225 °C, velocidad constante de unos 30-40 mm/s (la KE va mejor despacio con TPU), retracción mínima.",
    "- Cama a 30 °C: más caliente, el TPU se suelda a la PEI y se rompe la primera capa al despegarlo.",
    "- Sin planchado (ironing) y sin resina: el TPU se dobla y la resina se agrietaría.",
    "",
]

M600 = [
    "CAMBIO DE FILAMENTO EN LA KE (M600)",
    "- En el proyecto de Orca ya está: «G-code de cambio de filamento» = M600 y «Cambio manual de filamento» activado.",
    "  Si laminas el STL con tu propio perfil, ponlo en Ajustes de impresora › G-code de máquina › «Change filament G-code»: M600.",
    "- Cuando la impresora se pare: retira el filamento, mete el siguiente, purga hasta que salga del color nuevo y limpio,",
    "  quita con pinzas el hilo que cuelga de la boquilla y pulsa «Continuar» en la pantalla.",
    "- No dejes la pieza parada mucho tiempo con la boquilla encima: el calor puede marcar la superficie.",
    "",
]

RESIN = [
    "ACABADO CON RESINA UV (opcional, protege y da brillo)",
    "Material: resina UV transparente «doming» o de joyería (baja viscosidad, amarillea poco), lámpara UV de 365-405 nm",
    "(una de uñas de 36-48 W sirve), guantes de nitrilo, gafas, palillos o un palito de mezclar y un mechero o soplete de llama fina.",
    "1. Deja la pieza 24 h tras imprimir. Límpiala con aire o un pincel; NO uses alcohol isopropílico sobre PLA de colores",
    "   (puede dejar velos). Los hilos se van con una pasada muy rápida de llama fina a unos 10 cm; las rebabas y gotas,",
    "   con un cortacutículas de acero, al ras (los alicates tiran del plástico y lo blanquean).",
    "2. Pon la pieza perfectamente horizontal (usa un nivel o el móvil) sobre papel de horno o un film, a cubierto del polvo.",
    "3. Capa de sellado: extiende una capa MUY fina con el palillo por toda la cara, metiéndola en las esquinas del relieve.",
    "   Cura 2-3 min bajo la lámpara. Esta capa evita burbujas que salen del relieve en las capas gruesas.",
    "4. Vierte la resina en capas de 1-2 mm como máximo, desde el centro, y llévala al borde con el palillo.",
    "   Pasa la llama a unos 10 cm, muy rápido, para reventar las burbujas. Cura 3-5 min cada capa.",
    "   NO uses pistola de aire caliente: calienta toda la pieza por encima de lo que aguanta el PLA y deforma el relieve fino.",
    "5. Última capa: enrasa con el borde (o haz una cúpula si no hay borde, sin llegar al canto: la tensión superficial",
    "   la sujeta). Cura 5 min y deja la pieza 24 h a la luz antes de usarla. Si queda pegajosa, otro ciclo de UV.",
    "6. Por debajo, pega corcho o fieltro adhesivo (2-3 mm) para que no raye ni resbale.",
    "Precauciones: la resina sin curar irrita la piel: guantes y ventilación. Lo que sobre, cúralo al sol antes de tirarlo.",
    "El PLA se ablanda hacia 55-60 °C: vale para bebidas frías o tazas templadas; para tazas recién hechas imprime en PETG.",
    "",
]


def _common_rows(layer: float, first: float, infill: str) -> list[tuple]:
    return [
        ("Filament", "Nozzle temperature", "Printing Temperature", "205-215 °C (la misma en todos los colores)"),
        ("Filament", "Bed temperature", "Build Plate Temperature", "60 °C"),
        ("Quality", "Layer height", "Layer Height", f"{f2(layer)} mm"),
        ("Quality", "Initial layer height", "Initial Layer Height", f"{f2(first)} mm"),
        ("Quality", "Adaptive layer height / Variable layer height", "Use Adaptive Layers", "desactivado (los cambios van a alturas fijas)"),
        ("Quality", "Ironing type", "Enable Ironing", "No ironing (desactivado)"),
        ("Strength", "Sparse infill density", "Infill Density", infill),
        ("Others", "Prime tower: Enable", "Prime Tower: Enable Prime Tower", "desactivado (purgas a mano en cada cambio)"),
        ("Support", "Enable support", "Generate Support", "desactivado"),
        ("Extruder (ajustes de impresora)", "Z-hop height; Z-hop type", "Z Hop When Retracted; Z Hop Height",
         ("0,4 mm; Normal (Normal Lift)", "activado; 0,4 mm")),
    ]


def photo_settings(size_mm: tuple[float, float, float], filaments: list, changes: list[dict], layer: float,
                   first: float, base_layers: int, volume_mm3: float, rim: bool) -> str:
    """`changes`: [{"capa": capa de Orca, "z": z de arriba de la capa, "nombre": filamento}]."""
    w, h, d = size_mm
    rows = _common_rows(layer, first, "100 % (todo el relieve macizo: el color depende del grosor)")
    rows += [("Strength", "Top shell layers", "Top Layers", "5 o más (con relleno al 100 % da igual)"),
             ("Speed", "Outer wall; Top surface", "Outer Wall Speed; Top Surface Speed", "40 mm/s; 60 mm/s")]
    cura = [f"   - Capa {c['capa']} (Z de arriba {f2(c['z'])} mm): cambiar a {c['nombre']}" for c in changes]
    lines = [
        f"FOTO EN RELIEVE MULTICOLOR (tipo HueForge) — {PRINTER}",
        f"Pieza: {f1(w)} × {f1(h)} mm, alto máximo {f2(d)} mm. Unos {grams(volume_mm3):.0f} g de PLA en total.",
        "Se mira desde arriba, con luz normal (no es una litofanía: no va a contraluz).",
        "",
        "FILAMENTOS, en este orden (de oscuro a claro):",
        *[f"   {i + 1}. {fl.name}  {fl.color}  (TD {f2(fl.td)} mm)" for i, fl in enumerate(filaments)],
        f"La base ({base_layers} capas) va con el filamento 1.",
        "",
        "OPCIÓN RÁPIDA (recomendada)",
        "1. Abre el 3MF en OrcaSlicer con Archivo › Abrir proyecto. Trae tu perfil de la KE, las alturas de capa,",
        f"   los {len(filaments)} filamentos con su color y los {len(changes)} cambios ya puestos en la barra de capas.",
        "2. Lamina y mira la vista previa: en la barra de capas verás las marcas de cambio. Revisa que el resumen",
        f"   diga {len(changes)} cambio(s) de filamento.",
        "3. Empieza con el filamento 1 cargado.",
        "",
        "A MANO (con el STL, en Orca, Bambu o Cura)",
        "Importa el STL tal cual, tumbado, con el relieve hacia arriba, y cambia estas opciones:",
        "",
        *_slicer_blocks(rows),
        "Cambios de filamento (Orca/Bambu: clic derecho en la barra de capas › «Añadir cambio de filamento»;",
        "Cura: Extensiones › Post-procesado › Modificar G-code › «Filament Change», una por capa):",
        *cura,
        "",
        *BED_PREP,
        *M600,
        "SI EL RESULTADO NO SE PARECE A LA VISTA PREVIA",
        "- Lo que más cambia el resultado es el TD real de cada filamento. Si sale muy oscuro, sube el TD del color",
        "  claro (o adelanta su cambio un par de capas) y vuelve a generar; si sale lavado, bájalo.",
        "- Para medir el TD: imprime una escalera de 10 escalones de 0,08 mm sobre negro y mira en qué escalón deja",
        "  de verse el negro: TD ≈ número de escalones × 0,08 mm. HueForge publica los TD de muchas marcas.",
        "",
        *RESIN[:1],
        ("Esta pieza lleva borde: la resina queda dentro y enrasada, como un cristal." if rim else
         "Sin borde: haz solo una capa fina en cúpula, sin llegar al canto, o genera la pieza con «borde para resina»."),
        *RESIN[1:],
        "COMPROBACIONES",
        f"- Tamaño: {f1(w)} × {f1(h)} mm " + ("(cabe en la cama de la KE)." if max(w, h) <= BED[0] else "(NO cabe en la cama de 220 × 220 mm)."),
        "",
    ]
    return "\n".join(lines)


def coaster_settings(mode: str, n_colors: int, shape: str, size_mm: tuple[float, float, float], colors: list[str],
                     names: list[str], changes: list[tuple[float, int]], first: float, inlay_mm: float,
                     volume_mm3: float, resin_ml: float, rim: bool) -> str:
    w, h, d = size_mm
    rows = _common_rows(0.2, first, "20 %; Gyroid")
    rows += [("Strength", "Wall loops", "Wall Line Count", "3"),
             ("Strength", "Top shell layers; Bottom shell layers", "Top Layers; Bottom Layers", "5; 5")]
    head = [
        f"POSAVASOS MULTICOLOR ({shape}, modo {mode}) — {PRINTER}",
        f"Pieza: {f1(w)} × {f1(h)} × {f1(d)} mm. Unos {grams(volume_mm3) * 0.5:.0f} g de PLA (relleno 20 %).",
        "Colores: " + ", ".join(f"{i + 1}. {names[i]} {colors[i]}" for i in range(n_colors)),
        "",
        "OPCIÓN RÁPIDA (recomendada)",
        "Abre el 3MF en OrcaSlicer con Archivo › Abrir proyecto: trae tu perfil de la KE, los filamentos y,",
    ]
    if mode == "relieve":
        steps = [
            "   en este modo, los cambios de filamento ya puestos en la barra de capas. Revisa y lamina.",
            "   El proyecto trae relleno al 100 % (es el de las fotos en color): para el posavasos basta un 20 % con giroide.",
            "",
            "A MANO (con el STL de la pieza entera, en Orca, Bambu o Cura)",
            "Impórtalo boca arriba, capas de 0,2 mm (todas las alturas son múltiplos de 0,2), y cambia estas opciones:",
            "",
            *_slicer_blocks(rows),
            "Cambios de filamento (barra de capas en Orca/Bambu; «Filament Change» en Cura):",
            *[f"   - Al empezar la capa con Z de arriba {f2(z)} mm: cambiar al color {e} ({names[e - 1]})" for z, e in changes],
            f"Total: {len(changes)} cambio(s). Ninguna capa tiene dos colores.",
        ]
        if rim:
            steps.append("El borde sube con la pieza: se imprime en cada franja con el color que toque (queda a rayas por fuera).")
        else:
            steps.append("Sin borde para resina, el proyecto activa el planchado (ironing) de las caras de arriba: quedan más lisas.")
    else:
        cambios = n_colors - 1 if inlay_mm <= 0.3 + 1e-6 else 2 * n_colors - 1
        steps = [
            "   en este modo, cada color como una parte con su filamento y la primera capa de "
            f"{f2(first)} mm. Revisa y lamina. Trae relleno al 100 %: para el posavasos basta un 20 % con giroide.",
            "",
            "IMPORTANTE: la pieza sale BOCA ABAJO y con el motivo en espejo: NO la gires. La cara vista es la que toca",
            "la cama: copia su textura (PEI texturizada = mate rugoso; lámina lisa o cristal = brillo).",
            "",
            "A MANO (con los STL de cada color)",
            "Importa los STL a la vez y contesta «Sí» a cargarlos como un solo objeto de varias partes. Asigna el",
            f"filamento de cada parte: color 2 = filamento 1, {'color 3 = filamento 2, color 1 = filamento 3' if n_colors == 3 else 'color 1 = filamento 2'}.",
            "El fondo va el último a propósito: en la capa mixta Orca imprime el motivo, cambia al fondo y sigue con él.",
            "",
            *_slicer_blocks(rows),
            f"La vista previa de Orca debería decir {cambios} cambio(s) de filamento. Carga primero el color del motivo.",
            "Si pausa nada más empezar (cambio inicial), reanuda sin cambiar nada.",
            "Primera capa: en el proyecto va a 15 mm/s (relleno a 30 mm/s) para que los trazos finos del motivo",
            "no se levanten.",
            "ORDEN DE COLORES EN LA PRIMERA CAPA: deja «Secuencia de filamentos de la primera capa» en AUTOMÁTICO.",
            "AVISO: en una capa mixta Orca ordena los colores para gastar el menor número de cambios, así que puede",
            "imprimir primero el filamento 2 aunque lo hayas numerado después (la vista previa y el G-code lo muestran).",
            "No es un error: el resultado es el mismo. Con el incrustado en 0,3 mm (una sola capa mixta) hay un único",
            "M600; con 0,5 mm (dos capas mixtas) hay dos. Una secuencia personalizada «1 2» no lo arregla (Orca 2.5",
            "imprimió el filamento 2 primero y añadió un cambio más). Revisa en el G-code los «MANUAL_TOOL_CHANGE» y",
            "los «M600»: debe haber uno por cada cambio de la vista previa. Si quieres que empiece el otro color,",
            "intercambia los filamentos de las dos partes en la lista de objetos o los colores en la tabla de la app.",
        ]
    lines = head + steps + ["", *BED_PREP, *M600]
    if mode == "relieve" and rim:
        lines += [*RESIN[:1], f"Esta pieza lleva borde de resina: hacen falta unos {resin_ml:.0f} ml para enrasarlo (prepara un 20 % más).",
                  *RESIN[1:]]
    else:
        lines += [*RESIN[:1], "Sin borde: aplica una capa fina en cúpula sobre la cara vista, sin llegar al canto.",
                  *RESIN[1:]]
    if not (mode == "relieve" and rim):
        lines += TPU
    lines += ["COMPROBACIONES",
              f"- Tamaño: {f1(w)} × {f1(h)} mm " + ("(cabe en la cama de la KE)." if max(w, h) <= BED[0] else "(NO cabe en la cama de 220 × 220 mm)."),
              ""]
    return "\n".join(lines)


def multipass_settings(shape: str, size_mm: tuple[float, float, float], passes: list[dict], pass_mm: float,
                       bed_center: tuple[float, float], volume_mm3: float) -> str:
    """Instrucciones del posavasos multipaso. `passes`: [{"nombre", "filamento", "color", "z_hop"}] en orden."""
    w, h, d = size_mm
    n = len(passes)
    steps = []
    for i, ps in enumerate(passes):
        last = i == n - 1
        steps += [
            f"PASADA {i + 1} de {n}: {ps['filamento']} ({ps['color']}) — archivo {ps['archivo']}",
            f"   Z-hop {f2(ps['z_hop'])} mm. " + ("Va solo con los trazos finos del motivo, de 0 a " + f2(pass_mm) + " mm." if not last else
                                                f"Es el cuerpo: se imprime alrededor de lo ya impreso hasta {f2(d)} mm de alto."),
            "   " + ("Carga este filamento, abre su 3MF y lamina." if i == 0 else
                     "Sin tocar la pieza: cambia el filamento (descarga y carga el nuevo, purga a mano fuera de la pieza), abre su 3MF y lamina."),
            "",
        ]
    lines = [
        f"POSAVASOS MULTIPASO ({shape}) — {PRINTER}",
        f"Pieza: {f1(w)} × {f1(h)} × {f1(d)} mm. Unos {grams(volume_mm3) * 0.5:.0f} g de PLA (relleno 20 %).",
        f"Se imprime en {n} pasadas, una por color, cada una en su archivo y SIN la pieza quitada de la cama.",
        "",
        "QUÉ ES Y CUÁNDO CONVIENE",
        "- En vez de pausar la impresora (M600) a mitad de capa, cada color es una impresión completa aparte, sobre la misma",
        "  cama y en el mismo sitio. La boquilla nunca se queda parada y caliente encima de la cara vista, y no hay que",
        "  acertar con el momento del cambio. Entre pasadas cambias el filamento con calma.",
        "- Los colores del motivo (poco grosor) van primero y el cuerpo va el último, rodeándolos. La boquilla sube",
        "  (Z-hop) para pasar por encima de lo ya impreso. La cara vista es la que toca la cama: se imprime boca abajo.",
        "- Sirve también con filamento flexible (TPU) en alguna pasada y para pasar de 2-3 colores: hay una pasada por color.",
        "",
        "LO QUE DEBES SABER DE LA KE ANTES DE EMPEZAR (no lo he podido probar en tu impresora)",
        "- El inicio normal de la KE hace «G28 Z» y «BED_MESH_CALIBRATE»: el palpador toca la cama con la boquilla en",
        "  varios puntos. A partir de la pasada 2 eso chocaría con lo ya impreso, así que los proyectos de las pasadas 2 y",
        "  siguientes NO lo llevan. El final de cada pasada solo suelta X, Y y el extrusor, no Z: por eso la impresora",
        "  sigue sabiendo dónde está la cama. CONDICIÓN: no apagues ni reinicies la impresora entre pasadas ni muevas Z a",
        "  mano. Si lo haces, no continúes: vuelve a empezar desde la pasada 1.",
        "- Entre pasadas la cama sigue caliente (el final de las pasadas intermedias no la apaga), para que la pieza no",
        "  se encoja y se despegue. Mejor no tardes más de 15-20 minutos entre una pasada y la siguiente.",
        "- Falda y borde (skirt/brim) están desactivados: una falda de la pasada 2 chocaría con la pieza de la pasada 1.",
        "- Haz la primera vez una PRUEBA PEQUEÑA (tamaño 50 mm) con la mano cerca del botón de parada y mirando la primera",
        "  capa de cada pasada. Es una técnica nueva en tu máquina: aquí se aprende probando.",
        "",
        "ORDEN DE IMPRESIÓN",
        *steps,
        "COLOCACIÓN: la posición es la misma en todas las pasadas",
        f"- Cada 3MF ya coloca la pieza en el mismo punto de la cama (centro: X {bed_center[0]:g}, Y {bed_center[1]:g}).",
        "  Al abrir cada archivo, comprueba en el panel del objeto que la posición es la misma. NO muevas el objeto,",
        "  NO pulses «Organizar» (A) y NO importes los STL sueltos (el laminador los centraría uno a uno). Los STL de",
        "  este paquete están solo como referencia.",
        "",
        "PASO A PASO EN LA MÁQUINA",
        "1. Limpia la cama con alcohol isopropílico y no la toques. Carga el filamento de la pasada 1 y lámina su 3MF.",
        "2. Imprime la pasada 1. Al acabar la boquilla se aparta y la cama sigue caliente. NO retires la pieza.",
        "3. Con la impresora encendida: descarga el filamento, carga el de la pasada 2, purga hasta que salga limpio y",
        "   quita el hilo de la boquilla con pinzas (y limpia la boquilla: lo que quede se arrastra sobre la pieza).",
        "4. Lamina el 3MF de la pasada 2 y envíalo. La impresora hará el homing X e Y y empezará sin palpar la cama.",
        "5. Repite hasta la última pasada (el cuerpo). Tras ella, ya sí puedes dejar enfriar la cama y retirar la pieza.",
        "",
        "AJUSTES QUE LLEVAN LOS PROYECTOS (ya puestos)",
        "- Capas de 0,20 mm y primera capa de 0,20 mm en todas las pasadas (si una pasada tuviera otra altura, las",
        "  alturas no cuadrarían). Relleno 20 % giroide, 3 paredes, primera capa lenta (15 mm/s).",
        "- Z-hop: pasada 1 de 0,2 mm; las siguientes de " + f2(pass_mm + 0.2) + " mm (grosor de lo ya impreso + 0,2 mm).",
        "- Sin falda ni borde. Sin torre de purga. Sin planchado.",
        "- Si usas tu propio perfil y no el del proyecto, pon el Z-hop a «grosor de lo ya impreso + 0,2 mm» y",
        "  desactiva la falda en las pasadas 2 y siguientes.",
        "",
        "QUÉ MIRAR Y CÓMO CORREGIR",
        "- Se ve una rendija fina entre colores: la pieza se movió entre pasadas (el despegue de la pasada 1 es la",
        "  causa más probable) o la cama estaba fría al reanudar. Mantén la cama caliente y limpia mejor la cama.",
        "- La boquilla roza lo ya impreso al viajar: sube el Z-hop 0,2 mm.",
        "- Un color no se pega al contiguo: es normal que el borde sea una línea; la pasada del cuerpo lo rodea y lo sujeta.",
        "",
        *BED_PREP,
        *TPU,
        *RESIN[:1],
        "Sin borde: aplica una capa fina en cúpula sobre la cara vista, sin llegar al canto.",
        *RESIN[1:],
        "COMPROBACIONES",
        f"- Tamaño: {f1(w)} × {f1(h)} mm " + ("(cabe en la cama de la KE)." if max(w, h) <= BED[0] else "(NO cabe en la cama de 220 × 220 mm)."),
        "",
    ]
    return "\n".join(lines)
