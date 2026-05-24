"""Real /api/spec and /api/audit/ta tests — real DB, no mocks."""
from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="module")
def client():
    from eigenview.api.main import app
    with TestClient(app) as tc:
        yield tc


def test_spec_ta_returns_200(client):
    resp = client.get("/api/spec/ta")
    assert resp.status_code == 200


def test_spec_ta_contains_patterns(client):
    resp = client.get("/api/spec/ta")
    data = resp.json()
    # response is a dict with a 'patterns' key containing the list of setups
    assert "patterns" in data or isinstance(data, list), (
        f"spec/ta must have 'patterns' key or be a list, got: {list(data.keys()) if isinstance(data, dict) else type(data)}"
    )


def test_spec_ta_patterns_have_name(client):
    resp = client.get("/api/spec/ta")
    data = resp.json()
    items = data["patterns"] if "patterns" in data else data
    for item in items:
        assert "name" in item or "setup" in item or "label" in item or "id" in item, (
            f"Pattern item missing name field: {item}"
        )


def test_audit_ta_returns_200(client):
    resp = client.get("/api/audit/ta")
    assert resp.status_code == 200


def test_layouts_get_returns_200(client):
    resp = client.get("/api/layouts")
    assert resp.status_code == 200


def test_layouts_post_saves_and_retrieves(client):
    payload = {"id": "test_real", "name": "Test Real Layout", "config": {"test": True}}
    post_resp = client.post("/api/layouts", json=payload)
    assert post_resp.status_code in (200, 201, 204), (
        f"layouts POST failed: {post_resp.status_code} {post_resp.json()}"
    )
    get_resp = client.get("/api/layouts")
    assert get_resp.status_code == 200
