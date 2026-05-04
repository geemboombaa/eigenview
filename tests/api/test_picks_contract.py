"""Phase 2 — /api/picks contract tests.

Uses a seeded in-memory SQLite DB (via monkeypatching AsyncSessionLocal) so
tests always run — no live DB or picks required.
"""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Windows asyncio ──────────────────────────────────────────────────────────
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ── Minimal factors_json that satisfies the contract ────────────────────────
_TECHNICAL_DETAIL = {
    "pattern":      "pullback_in_trend",
    "confidence":   0.75,
    "direction":    "long",
    "trend":        "bullish",
    "weekly_trend": "bullish",
    "weekly_state": "BULLISH",
    "rsi":          48.5,
    "rsi_p40":      45.0,
    "adx":          28.3,
    "vol_ratio":    0.9,
    "swing_low":    420.0,
    "swing_high":   460.0,
    "vol_character": "declining",
    "bull_divergence": False,
    "bear_divergence": False,
    "ema200":       400.0,
    "weekly_ema8":  440.0,
    "weekly_ema21": 430.0,
    "fib_levels":   {},
}

_FACTORS_JSON = json.dumps({
    "technical": {
        "firing": True,
        "label":  "pullback_in_trend",
        "detail": _TECHNICAL_DETAIL,
    },
    "gex": {
        "firing": True,
        "label":  "long_gamma",
        "detail": {"call_wall": 470.0, "put_wall": 410.0, "gamma_flip": 435.0},
    },
    "flow":    {"firing": True,  "label": "call_sweep", "detail": {}},
    "dormant": {"firing": False, "label": "no_data",   "detail": {}},
    "sentiment": {"firing": True, "label": "bullish",  "detail": {}},
})

_SEED_PICK = {
    "date":           date.today(),
    "ticker":         "NVDA",
    "score":          0.8,
    "setup_type":     "pullback",
    "direction":      "long",
    "entry_low":      422.0,
    "entry_high":     435.0,
    "stop":           415.0,
    "conviction":     4,
    "thesis":         "Strong pullback setup on NVDA.",
    "factors_json":   _FACTORS_JSON,
    "signal_fired_at": datetime.utcnow(),
}


# ── In-memory SQLite session factory ────────────────────────────────────────
_TEST_ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


async def _init_db() -> None:
    from eigenview.data.storage import Base
    async with _TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed_pick() -> None:
    from sqlalchemy import text
    factory = async_sessionmaker(_TEST_ENGINE, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text("""
            INSERT INTO picks
              (id, date, ticker, score, setup_type, direction,
               entry_low, entry_high, stop, conviction, thesis,
               factors_json, signal_fired_at)
            VALUES
              (1, :date, :ticker, :score, :setup_type, :direction,
               :entry_low, :entry_high, :stop, :conviction, :thesis,
               :factors_json, :signal_fired_at)
        """), {
            "date":           str(_SEED_PICK["date"]),
            "ticker":         _SEED_PICK["ticker"],
            "score":          _SEED_PICK["score"],
            "setup_type":     _SEED_PICK["setup_type"],
            "direction":      _SEED_PICK["direction"],
            "entry_low":      _SEED_PICK["entry_low"],
            "entry_high":     _SEED_PICK["entry_high"],
            "stop":           _SEED_PICK["stop"],
            "conviction":     _SEED_PICK["conviction"],
            "thesis":         _SEED_PICK["thesis"],
            "factors_json":   _SEED_PICK["factors_json"],
            "signal_fired_at": str(_SEED_PICK["signal_fired_at"]),
        })
        await session.commit()


_TestSessionLocal = async_sessionmaker(_TEST_ENGINE, expire_on_commit=False)


@asynccontextmanager
async def _test_session_ctx():
    async with _TestSessionLocal() as session:
        yield session


# ── Fixture: TestClient with seeded DB ──────────────────────────────────────
@pytest.fixture(scope="module")
def client(event_loop_policy):
    """Return a TestClient wired to the in-memory DB."""
    import asyncio

    import eigenview.api.routes.picks as picks_module
    from eigenview.api.main import app

    # Bootstrap DB once
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_init_db())
    loop.run_until_complete(_seed_pick())
    loop.close()

    # Patch AsyncSessionLocal in the picks module to use the test engine
    original = picks_module.AsyncSessionLocal
    picks_module.AsyncSessionLocal = _TestSessionLocal
    yield TestClient(app)
    picks_module.AsyncSessionLocal = original


# ── Tests ────────────────────────────────────────────────────────────────────

def test_picks_returns_list(client):
    resp = client.get("/api/picks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_pick_has_required_fields(client):
    resp = client.get("/api/picks")
    picks = resp.json()
    assert picks, "Expected at least one seeded pick"
    pick = picks[0]
    for field in ("setup_type", "direction", "entry_low", "entry_high", "stop", "conviction"):
        assert field in pick, f"Missing top-level field: {field}"


def test_pick_structure_non_empty(client):
    resp = client.get("/api/picks")
    picks = resp.json()
    assert picks
    pick = picks[0]
    assert "structure" in pick
    assert pick["structure"]["description"], "structure.description must be a non-empty string"
    assert pick["structure"]["legs"],        "structure.legs must be a non-empty string"


def test_pick_signal_fired_at(client):
    resp = client.get("/api/picks")
    picks = resp.json()
    assert picks
    pick = picks[0]
    assert "signal_fired_at" in pick
    assert pick["signal_fired_at"] is not None, "signal_fired_at must not be None for seeded pick"
    datetime.fromisoformat(pick["signal_fired_at"])  # must be ISO-parseable


def test_pick_technical_factor(client):
    resp = client.get("/api/picks")
    picks = resp.json()
    assert picks
    pick = picks[0]
    assert "factors" in pick
    assert "technical" in pick["factors"]
    ta = pick["factors"]["technical"]
    assert ta["firing"] is True
    detail = ta["detail"]
    required = ("trend", "weekly_trend", "rsi", "adx", "vol_ratio",
                "swing_low", "weekly_state", "rsi_p40")
    for field in required:
        assert field in detail, f"Missing detail field: {field}"
