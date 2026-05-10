from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eigenview.data.storage import Base

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """In-memory SQLite session for unit tests — no network, no Supabase."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def sample_ticker() -> str:
    """First ticker from live NDX100 universe (falls back to AAPL on network failure)."""
    import asyncio as _asyncio
    from eigenview.data.universe import get_universe
    try:
        loop = _asyncio.get_event_loop()
        if not loop.is_running():
            tickers = loop.run_until_complete(get_universe("ndx100"))
            if tickers:
                return tickers[0]
    except Exception:
        pass
    return "AAPL"


@pytest.fixture
def sample_tickers() -> list[str]:
    """First 5 tickers from live NDX100 universe (falls back on network failure)."""
    import asyncio as _asyncio
    from eigenview.data.universe import get_universe
    try:
        loop = _asyncio.get_event_loop()
        if not loop.is_running():
            tickers = loop.run_until_complete(get_universe("ndx100"))
            if tickers and len(tickers) >= 5:
                return tickers[:5]
            if tickers:
                return tickers
    except Exception:
        pass
    return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
