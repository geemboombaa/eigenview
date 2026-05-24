"""Dispose asyncpg engine between API tests."""
from __future__ import annotations

import asyncio
import pytest


@pytest.fixture(autouse=True)
async def reset_db_pool_api():
    yield
    try:
        from eigenview.data.storage import engine
        await asyncio.wait_for(engine.dispose(), timeout=2.0)
    except Exception:
        pass
