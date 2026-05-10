from __future__ import annotations

import json
import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_LAYOUTS_FILE_DEFAULT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "layouts.json"
))

_DEFAULT_LAYOUTS = [
    {"id": "standard", "name": "Standard", "is_default": True},
    {"id": "minimal", "name": "Minimal", "is_default": False},
    {"id": "pro", "name": "Pro Trader", "is_default": False},
    {"id": "research", "name": "Research", "is_default": False},
    {"id": "focus", "name": "Focus", "is_default": False},
]


def _layouts_file() -> str:
    return os.environ.get("EV_LAYOUTS_FILE", _LAYOUTS_FILE_DEFAULT)


def _read_layouts() -> list:
    path = _layouts_file()
    if not os.path.exists(path):
        return list(_DEFAULT_LAYOUTS)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return list(_DEFAULT_LAYOUTS)


def _write_layouts(data: list) -> None:
    path = _layouts_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/layouts")
async def get_layouts() -> list:
    return _read_layouts()


class LayoutBody(BaseModel):
    id: str
    name: str
    modules: list = []
    is_default: bool = False


@router.post("/layouts")
async def save_layout(body: LayoutBody) -> dict:
    layouts = _read_layouts()
    existing = next((i for i, l in enumerate(layouts) if l["id"] == body.id), None)
    entry = body.model_dump()
    if existing is not None:
        layouts[existing] = entry
    else:
        layouts.append(entry)
    _write_layouts(layouts)
    return {"ok": True}
