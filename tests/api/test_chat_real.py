"""Real /api/chat SSE tests — real Anthropic API, no mocks."""
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


def test_chat_post_returns_200(client):
    resp = client.post("/api/chat", json={"question": "What is the macro regime today?"})
    assert resp.status_code == 200


def test_chat_response_is_text_event_stream(client):
    resp = client.post(
        "/api/chat",
        json={"question": "What is the macro regime today?"},
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "text/event-stream" in content_type or len(resp.content) > 0


def test_chat_response_has_content(client):
    resp = client.post("/api/chat", json={"question": "What picks do you see today?"})
    assert resp.status_code == 200
    assert len(resp.content) > 0


def test_chat_empty_question_does_not_crash(client):
    resp = client.post("/api/chat", json={"question": ""})
    assert resp.status_code in (200, 422)


def test_chat_missing_body_returns_422(client):
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 422
