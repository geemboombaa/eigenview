"""tests/api/test_api_routes.py — contract tests for all API endpoints."""
from __future__ import annotations

import sys
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ---------------------------------------------------------------------------
# Shared in-memory DB + seeded data
# ---------------------------------------------------------------------------

_ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_SessionLocal = async_sessionmaker(_ENGINE, expire_on_commit=False)


@pytest.fixture(scope="module", autouse=True)
def _no_real_db_lifespan():
    """Prevent lifespan from opening real asyncpg connections during tests."""
    with patch("eigenview.api.main.create_tables", new_callable=AsyncMock):
        yield


async def _setup_db() -> None:
    from eigenview.data.storage import Base
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed() -> None:
    import datetime as dt
    from eigenview.data.storage import MacroDaily, Price
    async with _SessionLocal() as s:
        s.add(MacroDaily(
            date=date.today(),
            dix=0.48,
            gex_index=1_200_000_000.0,
            vix_m1=14.5,
            vix_m2=16.0,
            vix_contango_pct=0.03,
        ))
        for i in range(5):
            s.add(Price(
                ticker="NVDA",
                date=date.today() - dt.timedelta(days=i),
                open=100.0, high=105.0, low=95.0, close=102.0,
                volume=1_000_000,
                timeframe="1d",
            ))
        await s.commit()


@pytest.fixture(scope="module")
def client(event_loop_policy):
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_setup_db())
    loop.run_until_complete(_seed())
    loop.close()

    import eigenview.api.routes.market as market_mod
    import eigenview.api.routes.chart as chart_mod
    import eigenview.api.routes.heat as heat_mod
    import eigenview.api.routes.bench as bench_mod
    from eigenview.api.main import app

    orig_market = market_mod.AsyncSessionLocal
    orig_chart = chart_mod.AsyncSessionLocal
    orig_heat = heat_mod.AsyncSessionLocal
    orig_bench = bench_mod.AsyncSessionLocal

    market_mod.AsyncSessionLocal = _SessionLocal
    chart_mod.AsyncSessionLocal = _SessionLocal
    heat_mod.AsyncSessionLocal = _SessionLocal
    bench_mod.AsyncSessionLocal = _SessionLocal

    with TestClient(app) as tc:
        yield tc

    market_mod.AsyncSessionLocal = orig_market
    chart_mod.AsyncSessionLocal = orig_chart
    heat_mod.AsyncSessionLocal = orig_heat
    bench_mod.AsyncSessionLocal = orig_bench

    _ENGINE.sync_engine.dispose()


# ---------------------------------------------------------------------------
# GET /api/market/regime
# ---------------------------------------------------------------------------

def test_market_regime_returns_200(client):
    resp = client.get("/api/market/regime")
    assert resp.status_code == 200


def test_market_regime_has_required_fields(client):
    resp = client.get("/api/market/regime")
    data = resp.json()
    for field in ("score", "regime", "narrative"):
        assert field in data, f"Missing field: {field}"


def test_market_regime_score_in_range(client):
    resp = client.get("/api/market/regime")
    data = resp.json()
    assert 0 <= data["score"] <= 10


def test_market_regime_label_valid(client):
    resp = client.get("/api/market/regime")
    data = resp.json()
    assert data["regime"] in ("GREEN", "YELLOW", "RED", "UNKNOWN")


# ---------------------------------------------------------------------------
# GET /api/market/regime — no data fallback
# ---------------------------------------------------------------------------

def test_market_regime_empty_db_returns_unknown(client):
    """Without seeded macro data, endpoint returns UNKNOWN gracefully."""
    import asyncio
    import eigenview.api.routes.market as market_mod

    empty_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    empty_session = async_sessionmaker(empty_engine, expire_on_commit=False)

    loop = asyncio.new_event_loop()

    async def _init():
        from eigenview.data.storage import Base
        async with empty_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_init())
    loop.close()

    orig = market_mod.AsyncSessionLocal
    market_mod.AsyncSessionLocal = empty_session
    try:
        resp = client.get("/api/market/regime")
    finally:
        market_mod.AsyncSessionLocal = orig

    assert resp.status_code == 200
    assert resp.json()["regime"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# GET /api/chart/{ticker}
# ---------------------------------------------------------------------------

def test_chart_nvda_returns_200(client):
    resp = client.get("/api/chart/NVDA")
    assert resp.status_code == 200


def test_chart_has_required_keys(client):
    resp = client.get("/api/chart/NVDA")
    data = resp.json()
    for key in ("candles", "indicators", "gex_levels", "pattern"):
        assert key in data, f"Missing key: {key}"


def test_chart_candles_are_list(client):
    resp = client.get("/api/chart/NVDA")
    data = resp.json()
    assert isinstance(data["candles"], list)


def test_chart_unknown_ticker_returns_empty_candles(client):
    resp = client.get("/api/chart/ZZZNOTTICKER")
    assert resp.status_code == 200
    data = resp.json()
    assert data["candles"] == []


# ---------------------------------------------------------------------------
# GET /api/heat
# ---------------------------------------------------------------------------

def test_heat_returns_200(client):
    resp = client.get("/api/signals/heat")
    assert resp.status_code == 200


def test_heat_returns_list(client):
    resp = client.get("/api/signals/heat")
    data = resp.json()
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# GET /api/bench
# ---------------------------------------------------------------------------

def test_bench_returns_200(client):
    resp = client.get("/api/bench")
    assert resp.status_code == 200


def test_bench_returns_list(client):
    resp = client.get("/api/bench")
    data = resp.json()
    assert isinstance(data, list)
