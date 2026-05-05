"""tests/api/test_api_routes.py — contract tests for all API endpoints."""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime

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


async def _setup_db() -> None:
    from eigenview.data.storage import Base
    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed() -> None:
    from sqlalchemy import text
    async with _SessionLocal() as s:
        # Macro row
        await s.execute(text("""
            INSERT INTO macro_daily (date, dix, gex_index, vix_m1, vix_m2, vix_contango_pct)
            VALUES (:date, 0.48, 1200000000.0, 14.5, 16.0, 0.03)
        """), {"date": str(date.today())})

        # Price rows
        for i in range(5):
            await s.execute(text("""
                INSERT INTO prices (ticker, date, open, high, low, close, volume, timeframe)
                VALUES ('NVDA', :date, 100.0, 105.0, 95.0, 102.0, 1000000, '1d')
            """), {"date": str(date.today() - __import__('datetime').timedelta(days=i))})

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

    yield TestClient(app)

    market_mod.AsyncSessionLocal = orig_market
    chart_mod.AsyncSessionLocal = orig_chart
    heat_mod.AsyncSessionLocal = orig_heat
    bench_mod.AsyncSessionLocal = orig_bench


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

def test_market_regime_empty_db_returns_unknown():
    """Without seeded macro data, endpoint returns UNKNOWN gracefully."""
    import asyncio
    empty_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    empty_session = async_sessionmaker(empty_engine, expire_on_commit=False)

    loop = asyncio.new_event_loop()

    async def _init():
        from eigenview.data.storage import Base
        async with empty_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_init())
    loop.close()

    import eigenview.api.routes.market as market_mod
    from eigenview.api.main import app
    orig = market_mod.AsyncSessionLocal
    market_mod.AsyncSessionLocal = empty_session

    with TestClient(app) as c:
        resp = c.get("/api/market/regime")

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
    resp = client.get("/api/heat")
    assert resp.status_code == 200


def test_heat_returns_list(client):
    resp = client.get("/api/heat")
    data = resp.json()
    assert isinstance(data, list)


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
