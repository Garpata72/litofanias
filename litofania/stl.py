"""Escritura de STL binario sin dependencias externas."""
from __future__ import annotations

import numpy as np

_DTYPE = np.dtype([
    ("normal", "<f4", 3),
    ("v", "<f4", (3, 3)),
    ("attr", "<u2"),
])


def write_stl(path: str, verts: np.ndarray, faces: np.ndarray) -> None:
    tri = verts[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lens, out=np.zeros_like(normals), where=lens > 0)

    data = np.zeros(len(faces), dtype=_DTYPE)
    data["normal"] = normals
    data["v"] = tri
    with open(path, "wb") as f:
        f.write(b"litofania".ljust(80, b" "))
        f.write(np.uint32(len(faces)).tobytes())
        data.tofile(f)
