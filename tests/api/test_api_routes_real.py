"""Real FastAPI contract tests — real DB, no in-memory SQLite, no mocks."""
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


def test_picks_returns_200(client):
    resp = client.get("/api/picks")
    assert resp.status_code == 200


def test_picks_returns_list(client):
    resp = client.get("/api/picks")
    data = resp.json()
    assert isinstance(data, list)


def test_picks_items_have_required_fields(client):
    resp = client.get("/api/picks")
    picks = resp.json()
    for p in picks:
        assert "ticker" in p, f"pick missing 'ticker': {p}"
        assert "conviction" in p or "score" in p, f"pick missing conviction/score: {p}"
        assert "setup_type" in p, f"pick missing 'setup_type': {p}"


def test_market_regime_returns_200(client):
    resp = client.get("/api/market/regime")
    assert resp.status_code == 200


def test_market_regime_has_score(client):
    resp = client.get("/api/market/regime")
    data = resp.json()
    assert "score" in data or "regime" in data, f"regime response missing score/regime: {data}"


def test_chart_nvda_returns_200_or_404(client):
    resp = client.get("/api/chart/NVDA")
    assert resp.status_code in (200, 404)


def test_chart_nvda_200_returns_candles(client):
    resp = client.get("/api/chart/NVDA")
    if resp.status_code == 200:
        data = resp.json()
        # chart endpoint returns dict with 'candles' key (list of OHLCV bars)
        assert "candles" in data, f"chart response missing 'candles': {list(data.keys())}"
        assert isinstance(data["candles"], list)


def test_heat_endpoint_exists(client):
    resp = client.get("/api/signals/heat")
    assert resp.status_code in (200, 404)


def test_bench_returns_200(client):
    resp = client.get("/api/bench")
    assert resp.status_code == 200


def test_picks_ticker_is_uppercase(client):
    resp = client.get("/api/picks")
    for p in resp.json():
        assert p["ticker"] == p["ticker"].upper(), f"ticker not uppercase: {p['ticker']}"


def test_picks_conviction_in_valid_range(client):
    resp = client.get("/api/picks")
    for p in resp.json():
        conviction = p.get("conviction", p.get("score", 0))
        assert 0 <= conviction <= 5, f"conviction={conviction} out of [0,5]"


def test_picks_entry_stop_fields_present(client):
    for p in client.get("/api/picks").json():
        assert "entry_low" in p and "entry_high" in p and "stop" in p
        assert p["entry_low"] < p["entry_high"], "entry_low must be < entry_high"


def test_picks_signal_fired_at_is_iso(client):
    from datetime import datetime
    for p in client.get("/api/picks").json():
        fired = p.get("signal_fired_at")
        if fired:
            datetime.fromisoformat(fired)  # raises if not valid ISO


def test_picks_structure_has_description(client):
    for p in client.get("/api/picks").json():
        assert "structure" in p, f"pick missing 'structure': {p['ticker']}"
        assert p["structure"].get("description"), "structure.description must be non-empty"


def test_picks_factors_technical_detail_complete(client):
    for p in client.get("/api/picks").json():
        factors = p.get("factors", {})
        if factors.get("technical", {}).get("firing"):
            detail = factors["technical"]["detail"]
            for field in ("trend", "weekly_state", "rsi", "adx"):
                assert field in detail, f"{p['ticker']} technical detail missing '{field}'"
