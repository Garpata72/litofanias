"""Almacenamiento local de imágenes y STL en la carpeta `datos/`."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

ROOT = Path(os.environ.get("LITOFANIAS_DATOS", Path(__file__).resolve().parent.parent / "datos"))
IMAGES = ROOT / "imagenes"
MODELS = ROOT / "stl"
MASKS = ROOT / "mascaras"
TEXTURES = ROOT / "texturas"
PRESETS = ROOT / "plantillas.json"


def ensure_dirs() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    MASKS.mkdir(parents=True, exist_ok=True)
    TEXTURES.mkdir(parents=True, exist_ok=True)


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


def asset_path(folder: Path, asset_id: str) -> Path | None:
    """PNG de una máscara o una textura subida."""
    path = folder / f"{asset_id}.png"
    return path if asset_id.isalnum() and path.exists() else None


def save_asset_meta(folder: Path, asset_id: str, meta: dict) -> None:
    (folder / f"{asset_id}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def list_assets(folder: Path) -> list[dict]:
    metas = [json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")]
    return sorted(metas, key=lambda m: m["creada"], reverse=True)


def mask_path(mask_id: str) -> Path | None:
    return asset_path(MASKS, mask_id)


def load_presets() -> dict[str, dict]:
    try:
        return json.loads(PRESETS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_presets(presets: dict[str, dict]) -> None:
    tmp = PRESETS.with_suffix(".tmp")
    tmp.write_text(json.dumps(presets, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PRESETS)
