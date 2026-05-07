"""tests/api/test_chat.py — POST /api/chat SSE contract tests."""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

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

    import eigenview.api.routes.chat as chat_mod
    from eigenview.api.main import app
    orig = chat_mod.AsyncSessionLocal
    chat_mod.AsyncSessionLocal = _SessionLocal

    with TestClient(app) as tc:
        yield tc

    chat_mod.AsyncSessionLocal = orig
    _ENGINE.sync_engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fake_stream(*args, **kwargs):
    """Yields a minimal valid SSE stream."""
    yield "data: \"Hello\"\n\n"
    yield "data: [DONE]\n\n"


async def _error_stream(*args, **kwargs):
    """Yields SSE stream that hits the error path."""
    yield "data: \"Sorry, AI temporarily unavailable. Retry in a moment.\"\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# POST /api/chat — success path
# ---------------------------------------------------------------------------

def test_chat_returns_200(client):
    with patch("eigenview.api.routes.chat._stream_response", side_effect=_fake_stream):
        resp = client.post("/api/chat", json={"question": "What are today's top picks?"})
    assert resp.status_code == 200


def test_chat_returns_event_stream_content_type(client):
    with patch("eigenview.api.routes.chat._stream_response", side_effect=_fake_stream):
        resp = client.post("/api/chat", json={"question": "Why NVDA?"})
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_chat_response_contains_done_sentinel(client):
    with patch("eigenview.api.routes.chat._stream_response", side_effect=_fake_stream):
        resp = client.post("/api/chat", json={"question": "Explain GEX."})
    assert "[DONE]" in resp.text


def test_chat_accepts_optional_ticker(client):
    with patch("eigenview.api.routes.chat._stream_response", side_effect=_fake_stream):
        resp = client.post("/api/chat", json={"question": "Why NVDA?", "ticker": "NVDA"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/chat — error path (API down)
# ---------------------------------------------------------------------------

def test_chat_degrades_gracefully_on_api_error(client):
    with patch("eigenview.api.routes.chat._stream_response", side_effect=_error_stream):
        resp = client.post("/api/chat", json={"question": "What?"})
    assert resp.status_code == 200
    assert "[DONE]" in resp.text


# ---------------------------------------------------------------------------
# POST /api/chat — input validation
# ---------------------------------------------------------------------------

def test_chat_missing_question_returns_422(client):
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 422
