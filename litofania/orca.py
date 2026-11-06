"""Proyecto 3MF de OrcaSlicer listo para abrir, a partir de una plantilla guardada por Orca.

Orca solo lee los cambios de filamento por altura (los de la barra de capas) de SUS proyectos 3MF, y solo
si llevan dentro la configuración completa (`Metadata/project_settings.config`). Por eso se parte de un
proyecto vacío guardado por Carlos en Orca 2.5 con su perfil de la Ender 3 V3 KE (PLA Elegoo Rapid PLA+,
M600, sin torre de purga, relleno 100 %). De él se copia toda la configuración y se cambian la geometría,
el número y el color de los filamentos, las alturas de capa y los cambios de filamento.

Para usar otro perfil: guarda en Orca un proyecto con 2 filamentos y tu configuración y ponlo en
`datos/plantilla_orca.3mf` (la geometría no importa). Ver `template_path()`.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

TEMPLATE = Path(__file__).resolve().parent / "plantillas" / "orca_ender3v3ke.3mf"

# Ficheros de la plantilla que se regeneran o se descartan.
_SKIP = re.compile(r"^(3D/|Metadata/(model_settings\.config|custom_gcode_per_layer\.xml|"
                   r"project_settings\.config|plate_\d+.*|top_\d+\.png|pick_\d+\.png)|_rels/\.rels)")


def template_path(user_template: Path | None = None) -> Path:
    """La plantilla propia (si existe) o la incluida con la app."""
    return user_template if user_template is not None and user_template.exists() else TEMPLATE


def _adjust_config(c: dict, colors: list[str], layer: float, first: float) -> dict:
    n = len(colors)
    n0 = len(c["filament_colour"])
    if n0 < 2:
        raise ValueError("La plantilla de Orca debe tener al menos 2 filamentos para poder ampliarla")

    def fit(values):
        return (values + [values[-1]] * n)[:n]

    # Opciones por filamento: listas con un valor por filamento. Las de máquina con 2 valores
    # (modo normal/silencioso) no lo son.
    skip = {"start_end_points", "extruder_ams_count"}
    for k, v in list(c.items()):
        if isinstance(v, list) and len(v) == n0 and not k.startswith("machine_") and k not in skip:
            c[k] = fit(v)
    c["filament_colour"] = list(colors)
    if "filament_multi_colour" in c:
        c["filament_multi_colour"] = list(colors)
    if "filament_self_index" in c:
        c["filament_self_index"] = [str(i + 1) for i in range(n)]
    if "flush_volumes_matrix" in c:          # purga n × n (sin torre de purga apenas importa)
        m = c["flush_volumes_matrix"]
        out = max([int(float(x)) for x in m] + [0])
        c["flush_volumes_matrix"] = [m[i * n0 + j] if i < n0 and j < n0 else ("0" if i == j else str(out))
                                     for i in range(n) for j in range(n)]
    if "flush_volumes_vector" in c:
        c["flush_volumes_vector"] = (c["flush_volumes_vector"] * n)[:2 * n]
    for k in ("different_settings_to_system", "inherits_group"):   # proceso + n filamentos + impresora
        v = c.get(k)
        if isinstance(v, list) and len(v) == n0 + 2:
            c[k] = [v[0]] + fit(v[1:-1]) + [v[-1]]
    c["layer_height"] = "%g" % layer
    c["initial_layer_print_height"] = "%g" % first
    return c


def _bed_center(c: dict) -> tuple[float, float]:
    pts = [tuple(float(x) for x in p.split("x")) for p in c.get("printable_area", ["0x0", "220x220"])]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _mesh_xml(oid: int, uuid: str, v: np.ndarray, t: np.ndarray) -> str:
    vs = "".join('     <vertex x="%.5g" y="%.5g" z="%.5g"/>\n' % tuple(p) for p in v.tolist())
    ts = "".join('     <triangle v1="%d" v2="%d" v3="%d"/>\n' % tuple(f) for f in t.tolist())
    return (f'  <object id="{oid}" p:UUID="{uuid}" type="model">\n   <mesh>\n    <vertices>\n{vs}'
            f'    </vertices>\n    <triangles>\n{ts}    </triangles>\n   </mesh>\n  </object>\n')


def write_project(path: str, parts: list[tuple[str, int, np.ndarray, np.ndarray]], colors: list[str],
                  layer: float, first: float, changes: list[tuple[float, int]] = (), name: str = "modelo",
                  template: Path | None = None, overrides: dict[str, str] | None = None) -> None:
    """parts: [(nombre, filamento 1.., vértices (V,3), triángulos (T,3))], ya colocadas entre sí.
    colors: color «#RRGGBB» de cada filamento (define cuántos hay).
    changes: [(z de arriba de la capa, filamento)]: cambio de filamento al empezar esa capa, como el
    «Cambiar filamento» de la barra de capas de Orca.
    overrides: opciones del proceso que cambian para esta pieza (relleno, planchado, velocidad de la primera
    capa…); si en la plantilla la opción es una lista, se repite el valor en cada elemento."""
    zin = zipfile.ZipFile(template or TEMPLATE)
    config = _adjust_config(json.loads(zin.read("Metadata/project_settings.config")), colors, layer, first)
    for k, v in (overrides or {}).items():
        old = config.get(k)
        config[k] = v if isinstance(v, list) else [v] * len(old) if isinstance(old, list) else v
    # Orden de los filamentos en la primera capa (Orca: «Secuencia de filamentos de la primera capa»).
    first_seq = config.get("first_layer_print_sequence")
    seq_value = " ".join(str(x) for x in first_seq) if first_seq and first_seq != ["0"] else ""
    main = zin.read("3D/3dmodel.model").decode("utf-8")
    # Las etiquetas Application y OrcaSlicer hacen que Orca lo abra como proyecto propio.
    meta = "\n".join(line for line in main.splitlines() if line.strip().startswith("<metadata"))
    plate_meta = ""
    block = re.search(r"<plate>(.*?)</plate>", zin.read("Metadata/model_settings.config").decode("utf-8"), re.S)
    if block:
        n = len(colors)
        lines = []
        for line in block.group(1).split("<model_instance")[0].splitlines():
            if "<metadata" not in line or re.search(r'key="(thumbnail|top|pick)', line):
                continue
            line = re.sub(r'(key="filament_maps" value=")[^"]*', lambda m: m.group(1) + " ".join(["1"] * n), line)
            line = re.sub(r'(key="filament_volume_maps" value=")[^"]*', lambda m: m.group(1) + " ".join(["0"] * n), line)
            lines.append(line)
        if seq_value:
            lines.append(f'    <metadata key="first_layer_print_sequence" value="{seq_value}"/>')
        plate_meta = "\n".join(lines)

    parts = [(n, e, np.asarray(v, float), np.asarray(t, int)) for n, e, v, t in parts]
    allv = np.concatenate([p[2] for p in parts])
    lo, hi = allv.min(0), allv.max(0)
    center = (lo + hi) / 2
    cx, cy = _bed_center(config)
    tz = center[2] - lo[2]
    k = len(parts)
    obj = k + 1
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name) or "modelo"
    fname = f"3D/Objects/{safe}_1.model"

    objects = "".join(_mesh_xml(i + 1, "%04x0000-81cb-4c03-9d28-80fed5dfa1dc" % (i + 1), p[2] - center, p[3])
                      for i, p in enumerate(parts))
    hdr = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
           'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
           'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n')
    sub = hdr + ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n' + objects + " </resources>\n <build/>\n</model>\n"
    comps = "".join(f'    <component p:path="/{fname}" objectid="{i + 1}" p:UUID="{i + 1:04x}0000-b206-40ff-9872-83e8017abed1" '
                    f'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n' for i in range(k))
    trans = f"1 0 0 0 1 0 0 0 1 {cx:g} {cy:g} {tz:g}"
    model = (hdr + meta + "\n <resources>\n"
             f'  <object id="{obj}" p:UUID="{obj:08x}-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <components>\n{comps}'
             "   </components>\n  </object>\n </resources>\n"
             f' <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n  <item objectid="{obj}" '
             f'p:UUID="{obj + 1:08x}-b1ec-4553-aec9-835e5b724bb4" transform="{trans}" printable="1"/>\n </build>\n</model>\n')
    rels_obj = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                f' <Relationship Target="/{fname}" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')

    pieces = "".join(
        f'    <part id="{i + 1}" subtype="normal_part">\n'
        f'      <metadata key="name" value={quoteattr(n)}/>\n'
        '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
        f'      <metadata key="extruder" value="{e}"/>\n'
        '      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
        "    </part>\n" for i, (n, e, _, _) in enumerate(parts))
    settings = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
                f'  <object id="{obj}">\n    <metadata key="name" value={quoteattr(name)}/>\n'
                f'    <metadata key="extruder" value="1"/>\n{pieces}  </object>\n'
                f"  <plate>\n{plate_meta}\n    <model_instance>\n"
                f'      <metadata key="object_id" value="{obj}"/>\n      <metadata key="instance_id" value="0"/>\n'
                f'      <metadata key="identify_id" value="{100 + obj}"/>\n    </model_instance>\n  </plate>\n'
                f'  <assemble>\n   <assemble_item object_id="{obj}" instance_id="0" transform="{trans}" offset="0 0 0" />\n'
                "  </assemble>\n</config>\n")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            if not _SKIP.match(info.filename):
                z.writestr(info.filename, zin.read(info.filename))
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("3D/_rels/3dmodel.model.rels", rels_obj)
        z.writestr(fname, sub)
        z.writestr("Metadata/model_settings.config", settings)
        z.writestr("Metadata/project_settings.config", json.dumps(config, indent=4, ensure_ascii=False))
        if changes:
            layers = "".join(f'<layer top_z="{zc:g}" type="2" extruder="{e}" color="{colors[e - 1]}" extra="" gcode="tool_change"/>\n'
                             for zc, e in changes)
            z.writestr("Metadata/custom_gcode_per_layer.xml",
                       '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n<plate>\n<plate_info id="1"/>\n'
                       f'{layers}<mode value="MultiAsSingle"/>\n</plate>\n</custom_gcodes_per_layer>\n')
    zin.close()
