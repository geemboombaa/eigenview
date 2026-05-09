"""
Integration test conftest.
Forces asyncpg connection pool to close between API tests to prevent
event loop interference on Windows.
"""
from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
async def reset_db_pool():
    """Yield, then dispose the DB engine so asyncpg connections don't bleed between tests."""
    yield
    try:
        from eigenview.data.storage import engine as _engine
        # Dispose quietly — suppress asyncpg cancellation noise
        await asyncio.wait_for(_engine.dispose(), timeout=2.0)
    except Exception:
        pass
