"""Archivos 3MF: varias piezas en un solo archivo, cada una como un objeto con su nombre, para colocarlas
por separado en el laminador (la litofanía y su caja o su base, o la caja y su peana)."""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import quoteattr

import numpy as np

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""
RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def read_stl(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Lee un STL binario y une los vértices repetidos: devuelve (vértices N×3, caras M×3)."""
    with open(path, "rb") as f:
        f.seek(80)
        n = int(np.frombuffer(f.read(4), "<u4")[0])
        data = np.frombuffer(f.read(50 * n), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    pts = np.ascontiguousarray(data["v"].reshape(-1, 3))
    key = pts.view(np.dtype((np.void, 12))).ravel()
    _, first, inverse = np.unique(key, return_index=True, return_inverse=True)
    return pts[first].astype(np.float64), inverse.reshape(-1, 3).astype(np.int64)


def write_3mf(path: str, objects: list[tuple[str, np.ndarray, np.ndarray]]) -> None:
    """Escribe las piezas (nombre, vértices, caras) en milímetros, tal como están colocadas."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="es-ES" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
             ' <metadata name="Application">Litofanías</metadata>\n <resources>\n']
    for i, (name, verts, faces) in enumerate(objects, start=1):
        parts.append(f'  <object id="{i}" name={quoteattr(name)} type="model"><mesh><vertices>\n')
        parts.append("".join([f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>\n' for x, y, z in verts.tolist()]))
        parts.append('</vertices><triangles>\n')
        parts.append("".join([f'<triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in faces.tolist()]))
        parts.append('</triangles></mesh></object>\n')
    parts.append(' </resources>\n <build>\n')
    parts += [f'  <item objectid="{i}"/>\n' for i in range(1, len(objects) + 1)]
    parts.append(' </build>\n</model>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", "".join(parts))
