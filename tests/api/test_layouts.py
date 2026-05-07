"""tests/api/test_layouts.py — GET/POST /api/layouts contract tests."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="module", autouse=True)
def _no_real_db_lifespan():
    from unittest.mock import AsyncMock
    with patch("eigenview.api.main.create_tables", new_callable=AsyncMock):
        yield


@pytest.fixture(scope="module")
def client():
    from eigenview.api.main import app
    with TestClient(app) as tc:
        yield tc


# ---------------------------------------------------------------------------
# GET /api/layouts
# ---------------------------------------------------------------------------

def test_get_layouts_returns_200(client):
    resp = client.get("/api/layouts")
    assert resp.status_code == 200


def test_get_layouts_returns_list(client):
    resp = client.get("/api/layouts")
    assert isinstance(resp.json(), list)


def test_get_layouts_default_entries(client):
    resp = client.get("/api/layouts")
    ids = [l["id"] for l in resp.json()]
    assert "standard" in ids


def test_get_layouts_has_required_fields(client):
    resp = client.get("/api/layouts")
    layouts = resp.json()
    assert len(layouts) > 0
    for l in layouts:
        assert "id" in l
        assert "name" in l


# ---------------------------------------------------------------------------
# POST /api/layouts
# ---------------------------------------------------------------------------

def test_post_layout_returns_ok(client, tmp_path):
    with patch("eigenview.api.routes.layouts._LAYOUTS_FILE", str(tmp_path / "layouts.json")):
        resp = client.post("/api/layouts", json={
            "id": "test_layout",
            "name": "Test Layout",
            "modules": [],
            "is_default": False,
        })
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_post_layout_persists(client, tmp_path):
    layouts_file = str(tmp_path / "layouts.json")
    with patch("eigenview.api.routes.layouts._LAYOUTS_FILE", layouts_file):
        client.post("/api/layouts", json={
            "id": "persist_test",
            "name": "Persist Test",
            "modules": [],
            "is_default": False,
        })
        saved = json.loads(Path(layouts_file).read_text())
    assert any(l["id"] == "persist_test" for l in saved)


def test_post_layout_updates_existing(client, tmp_path):
    layouts_file = str(tmp_path / "layouts.json")
    with patch("eigenview.api.routes.layouts._LAYOUTS_FILE", layouts_file):
        client.post("/api/layouts", json={"id": "dup", "name": "V1", "modules": [], "is_default": False})
        client.post("/api/layouts", json={"id": "dup", "name": "V2", "modules": [], "is_default": False})
        saved = json.loads(Path(layouts_file).read_text())
    dups = [l for l in saved if l["id"] == "dup"]
    assert len(dups) == 1
    assert dups[0]["name"] == "V2"
