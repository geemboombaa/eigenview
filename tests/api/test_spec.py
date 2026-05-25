"""tests/api/test_spec.py — contract tests for /api/spec/* and /api/audit/ta."""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_SessionLocal = async_sessionmaker(_ENGINE, expire_on_commit=False)


@pytest.fixture(scope="module", autouse=True)
def _no_real_db_lifespan():
    with patch("eigenview.api.main.create_tables", new_callable=AsyncMock):
        yield


@pytest.fixture(scope="module")
def client():
    import asyncio
    loop = asyncio.new_event_loop()

    async def _setup():
        from eigenview.data.storage import Base
        async with _ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_setup())
    loop.close()

    import eigenview.api.routes.spec as spec_mod
    from eigenview.api.main import app
    orig = spec_mod.AsyncSessionLocal
    spec_mod.AsyncSessionLocal = _SessionLocal

    with TestClient(app) as tc:
        yield tc

    spec_mod.AsyncSessionLocal = orig
    _ENGINE.sync_engine.dispose()


# ---------------------------------------------------------------------------
# GET /api/spec/ta
# ---------------------------------------------------------------------------

def test_spec_ta_returns_200(client):
    resp = client.get("/api/spec/ta")
    assert resp.status_code == 200


def test_spec_ta_has_patterns(client):
    resp = client.get("/api/spec/ta")
    data = resp.json()
    assert "patterns" in data
    assert len(data["patterns"]) > 0


def test_spec_ta_pattern_has_required_fields(client):
    resp = client.get("/api/spec/ta")
    pattern = resp.json()["patterns"][0]
    for field in ("name", "display_name", "category", "conditions"):
        assert field in pattern, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/audit/ta
# ---------------------------------------------------------------------------

def test_audit_ta_returns_200(client):
    resp = client.get("/api/audit/ta")
    assert resp.status_code == 200


def test_audit_ta_has_summary(client):
    resp = client.get("/api/audit/ta")
    data = resp.json()
    assert "summary" in data
    assert "findings" in data


def test_audit_ta_summary_has_counts(client):
    resp = client.get("/api/audit/ta")
    summary = resp.json()["summary"]
    for key in ("pass", "fail", "warn"):
        assert key in summary


# ---------------------------------------------------------------------------
# POST /api/spec/notes + GET /api/spec/notes/{spec_id}
# ---------------------------------------------------------------------------

def test_save_spec_note_returns_ok(client):
    resp = client.post("/api/spec/notes", json={
        "spec_id": "pullback_in_trend",
        "note": "test note",
    })
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_get_spec_notes_returns_saved(client):
    client.post("/api/spec/notes", json={
        "spec_id": "test_spec_id",
        "note": "retrieved note",
    })
    resp = client.get("/api/spec/notes/test_spec_id")
    assert resp.status_code == 200
    notes = resp.json().get("notes", [])
    assert any(n["note"] == "retrieved note" for n in notes)


def test_get_spec_notes_empty_returns_empty_list(client):
    resp = client.get("/api/spec/notes/nonexistent_spec_xyz")
    assert resp.status_code == 200
    assert resp.json()["notes"] == []
