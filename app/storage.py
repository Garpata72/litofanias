"""Almacenamiento local de imágenes y STL en la carpeta `datos/`."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("LITOFANIAS_DATOS", Path(__file__).resolve().parent.parent / "datos"))
IMAGES = ROOT / "imagenes"
MODELS = ROOT / "stl"


def ensure_dirs() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def image_path(image_id: str) -> Path | None:
    if not image_id.isalnum():
        return None
    matches = [p for p in IMAGES.glob(f"{image_id}.*") if p.suffix != ".json"]
    return matches[0] if matches else None


def save_meta(image_id: str, meta: dict) -> None:
    (IMAGES / f"{image_id}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def list_images() -> list[dict]:
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in IMAGES.glob("*.json")]
    return sorted(metas, key=lambda m: m["creada"], reverse=True)


def get_meta(image_id: str) -> dict | None:
    path = IMAGES / f"{image_id}.json"
    if not image_id.isalnum() or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
