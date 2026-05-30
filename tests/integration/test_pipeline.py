"""
Integration tests — prove the full pipeline with real data.

These tests hit the real DB + real API feeds. They're slow (30–120s total)
but prove correctness that synthetic unit tests cannot.

Run all integration tests:   uv run pytest tests/integration/ -v -s
Run just data layer:          uv run pytest tests/integration/ -v -k "TestData"
Run just factor layer:        uv run pytest tests/integration/ -v -k "TestFactor"
Run just API layer:           uv run pytest tests/integration/ -v -k "TestAPI"
"""
from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio


# ── shared fixtures ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def nvda_prices():
    from eigenview.data.prices import get_prices
    return await get_prices("NVDA", timeframe="1d", days=90)


@pytest_asyncio.fixture
async def nvda_chains():
    from eigenview.data.chains import get_chain
    from eigenview.data.storage import AsyncSessionLocal, Chain
    from sqlalchemy import select
    await get_chain("NVDA")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Chain).where(Chain.ticker == "NVDA", Chain.snapshot_date == date.today())
        )
        return result.scalars().all()


@pytest_asyncio.fixture
async def macro_result():
    from eigenview.data.storage import AsyncSessionLocal
    from eigenview.factors.macro_regime import score_macro_regime
    async with AsyncSessionLocal() as session:
        return await score_macro_regime(session)


@pytest.fixture
def nvda_spot(nvda_prices):
    return float(nvda_prices["close"].iloc[-1])


# ── data layer ────────────────────────────────────────────────────────────────

class TestDataLayer:

    def test_prices_enough_rows(self, nvda_prices):
        assert len(nvda_prices) >= 50, f"Only {len(nvda_prices)} rows — need ≥50 trading days in 90-day window"

    def test_prices_has_ohlcv_columns(self, nvda_prices):
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in nvda_prices.columns

    def test_prices_no_null_close(self, nvda_prices):
        assert nvda_prices["close"].isna().sum() == 0

    def test_prices_reasonable_spot(self, nvda_prices):
        last = nvda_prices["close"].iloc[-1]
        assert 10 < last < 10_000, f"Implausible close: {last}"

    def test_chain_has_many_contracts(self, nvda_chains):
        assert len(nvda_chains) > 100, f"Only {len(nvda_chains)} contracts — expected >100"

    def test_chain_has_calls_and_puts(self, nvda_chains):
        # call_put stored as single char 'C'/'P'
        sides = {str(c.call_put).lower() for c in nvda_chains}
        assert "c" in sides and "p" in sides

    def test_chain_gamma_populated(self, nvda_chains):
        with_gamma = [c for c in nvda_chains if c.gamma is not None and c.gamma != 0]
        assert len(with_gamma) > 10, f"Only {len(with_gamma)} non-zero gamma contracts"

    def test_chain_multiple_expiries(self, nvda_chains):
        expiries = {c.expiry for c in nvda_chains if c.expiry}
        assert len(expiries) >= 3, f"Only {len(expiries)} expiries"


# ── factor layer ──────────────────────────────────────────────────────────────

class TestFactorTechnical:

    def test_runs_without_error(self, nvda_prices):
        from eigenview.factors.technical import score_technical
        r = score_technical(nvda_prices, "NVDA")
        assert r.factor_id == "technical"

    def test_strength_in_range(self, nvda_prices):
        from eigenview.factors.technical import score_technical
        r = score_technical(nvda_prices, "NVDA")
        assert 0.0 <= r.strength <= 1.0

    def test_pattern_is_known(self, nvda_prices):
        from eigenview.factors.technical import score_technical
        KNOWN = {
            "no_pattern", "breakout", "pullback_in_trend", "compression_break",
            "flag", "bullish_reversal", "ema_reclaim", "base_breakout",
            "oversold_bounce", "failed_breakdown", "bearish_reversal",
        }
        r = score_technical(nvda_prices, "NVDA")
        assert r.label in KNOWN, f"Unknown pattern: {r.label}"

    def test_detail_has_required_keys(self, nvda_prices):
        from eigenview.factors.technical import score_technical
        r = score_technical(nvda_prices, "NVDA")
        for k in ["pattern", "confidence", "trend", "adx", "rsi", "vol_ratio", "fib_levels"]:
            assert k in r.detail, f"Missing detail key: {k}"

    def test_fib_levels_present(self, nvda_prices):
        from eigenview.factors.technical import score_technical
        r = score_technical(nvda_prices, "NVDA")
        fib = r.detail.get("fib_levels", {})
        for level in ["f236", "f382", "f500", "f618", "f786"]:
            assert level in fib, f"Missing fib level: {level}"

    def test_firing_consistent_with_confidence(self, nvda_prices):
        from eigenview.factors.technical import score_technical
        r = score_technical(nvda_prices, "NVDA")
        # If confidence >= 0.6, should fire (unless no_pattern)
        if r.detail.get("pattern") != "no_pattern" and r.detail.get("confidence", 0) >= 0.6:
            assert r.firing is True, "Should fire when confidence ≥ 60%"
        if r.detail.get("confidence", 0) < 0.6:
            assert r.firing is False, "Should not fire when confidence < 60%"


class TestFactorGEX:

    def test_regime_is_known(self, nvda_chains, nvda_spot):
        from eigenview.factors.gex import score_gex
        r = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        assert r.label in {"short_gamma", "long_gamma", "flip_zone"}

    def test_has_walls(self, nvda_chains, nvda_spot):
        from eigenview.factors.gex import score_gex
        r = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        d = r.detail
        assert d.get("call_wall") is not None
        assert d.get("put_wall") is not None
        assert d.get("gamma_flip") is not None

    def test_gex_by_expiry_present(self, nvda_chains, nvda_spot):
        from eigenview.factors.gex import score_gex
        r = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        by_exp = r.detail.get("gex_by_expiry", {})
        assert "0dte" in by_exp
        assert "weekly" in by_exp
        assert "monthly" in by_exp

    def test_gamma_cluster_present(self, nvda_chains, nvda_spot):
        from eigenview.factors.gex import score_gex
        r = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        cluster = r.detail.get("gamma_cluster", {})
        assert "pinning_risk" in cluster


class TestFactorFlow:

    def test_dominant_side_valid(self, nvda_chains):
        from eigenview.factors.flow import score_flow
        r = score_flow(list(nvda_chains), "NVDA")
        assert r.detail.get("dominant_side") in {"calls", "puts", "neutral"}

    def test_premium_data_present(self, nvda_chains):
        from eigenview.factors.flow import score_flow
        r = score_flow(list(nvda_chains), "NVDA")
        assert r.detail.get("call_premium", -1) >= 0
        assert r.detail.get("put_premium", -1) >= 0

    def test_strength_in_range(self, nvda_chains):
        from eigenview.factors.flow import score_flow
        r = score_flow(list(nvda_chains), "NVDA")
        assert 0.0 <= r.strength <= 1.0

    def test_firing_consistent_with_sweeps(self, nvda_chains):
        from eigenview.factors.flow import score_flow
        r = score_flow(list(nvda_chains), "NVDA")
        total = r.detail.get("total_qualified", 0)
        if total == 0:
            assert r.firing is False, "Should not fire with 0 qualified sweeps"
        if total >= 1 and r.detail.get("largest_sweep_usd", 0) >= 500_000:
            assert r.firing is True, "Should fire with qualified sweep ≥$500K"


class TestFactorMacro:

    def test_score_in_range(self, macro_result):
        score = macro_result.detail.get("score", -1)
        assert 0 <= score <= 10, f"Score {score} out of range"

    def test_label_is_regime(self, macro_result):
        assert macro_result.label in {"GREEN", "YELLOW", "RED"}

    def test_vix_present(self, macro_result):
        assert macro_result.detail.get("vix_m1") is not None, "VIX M1 missing"

    def test_narrative_non_empty(self, macro_result):
        assert len(macro_result.narrative) > 10


# ── synthesis layer ───────────────────────────────────────────────────────────

class TestSynthesis:

    def test_gate_blocks_when_ta_off(self, nvda_prices, nvda_chains, nvda_spot, macro_result):
        from eigenview.factors.base import FactorResult
        from eigenview.factors.flow import score_flow
        from eigenview.factors.gex import score_gex
        from eigenview.synthesis.gate import TickerScorecard, qualify_pick

        gex = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        flow = score_flow(list(nvda_chains), "NVDA")
        ta_off = FactorResult("technical", False, 0.0, "no_pattern", {}, "no pattern")
        dormant_on = FactorResult("dormant", True, 0.8, "ACTIVE", {}, "active")
        sent_on    = FactorResult("sentiment", True, 0.7, "bullish", {}, "bullish")
        macro_score = int(macro_result.detail.get("score", 0))

        sc = TickerScorecard(
            ticker="NVDA", macro=macro_result, technical=ta_off,
            gex=gex, flow=flow, dormant=dormant_on, sentiment=sent_on, spot_price=nvda_spot,
        )
        assert qualify_pick(sc, macro_score) is False, "TA hard gate must block qualification"

    def test_gate_blocks_when_gex_off(self, nvda_prices, nvda_chains, nvda_spot, macro_result):
        from eigenview.factors.base import FactorResult
        from eigenview.factors.flow import score_flow
        from eigenview.factors.technical import score_technical
        from eigenview.synthesis.gate import TickerScorecard, qualify_pick

        ta = score_technical(nvda_prices, "NVDA")
        flow = score_flow(list(nvda_chains), "NVDA")
        gex_off = FactorResult("gex", False, 0.0, "long_gamma", {}, "long gamma")
        dormant_on = FactorResult("dormant", True, 0.8, "ACTIVE", {}, "active")
        sent_on    = FactorResult("sentiment", True, 0.7, "bullish", {}, "bullish")
        macro_score = int(macro_result.detail.get("score", 0))

        sc = TickerScorecard(
            ticker="NVDA", macro=macro_result, technical=ta,
            gex=gex_off, flow=flow, dormant=dormant_on, sentiment=sent_on, spot_price=nvda_spot,
        )
        assert qualify_pick(sc, macro_score) is False, "GEX hard gate must block qualification"

    def test_macro_does_not_gate_qualification(self, nvda_prices, nvda_chains, nvda_spot, macro_result):
        from eigenview.factors.base import FactorResult
        from eigenview.factors.flow import score_flow
        from eigenview.factors.gex import score_gex
        from eigenview.factors.technical import score_technical
        from eigenview.synthesis.gate import TickerScorecard, qualify_pick

        ta = score_technical(nvda_prices, "NVDA")
        gex = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        flow = score_flow(list(nvda_chains), "NVDA")
        dormant_on = FactorResult("dormant", True, 0.8, "ACTIVE", {}, "active")
        sent_on    = FactorResult("sentiment", True, 0.7, "bullish", {}, "bullish")

        sc = TickerScorecard(
            ticker="NVDA", macro=macro_result, technical=ta,
            gex=gex, flow=flow, dormant=dormant_on, sentiment=sent_on, spot_price=nvda_spot,
        )
        # Macro never gates qualification (user-locked 2026-05-29): the verdict is
        # identical whether macro is RED (2) or GREEN (9).
        assert qualify_pick(sc, macro_score=2) == qualify_pick(sc, macro_score=9)

    def test_conviction_in_range(self, nvda_prices, nvda_chains, nvda_spot, macro_result):
        from eigenview.factors.base import FactorResult
        from eigenview.factors.flow import score_flow
        from eigenview.factors.gex import score_gex
        from eigenview.factors.technical import score_technical
        from eigenview.synthesis.gate import TickerScorecard, conviction_score

        ta = score_technical(nvda_prices, "NVDA")
        gex = score_gex(list(nvda_chains), nvda_spot, "NVDA")
        flow = score_flow(list(nvda_chains), "NVDA")
        dormant_off = FactorResult("dormant", False, 0.0, "ACCUMULATING", {}, "accumulating")
        sent_off    = FactorResult("sentiment", False, 0.0, "NO DATA", {}, "no data")

        sc = TickerScorecard(
            ticker="NVDA", macro=macro_result, technical=ta,
            gex=gex, flow=flow, dormant=dormant_off, sentiment=sent_off, spot_price=nvda_spot,
        )
        conv = conviction_score(sc)
        assert 1 <= conv <= 5


# ── API layer ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAPI:

    async def test_health(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_picks_returns_list(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/picks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_market_regime(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/market/regime")
        assert r.status_code == 200
        data = r.json()
        assert any(k in data for k in ["label", "score", "regime"])

    async def test_chart_nvda(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/chart/NVDA?tf=1d")
        assert r.status_code == 200
        data = r.json()
        assert "candles" in data
        assert isinstance(data["candles"], list)
        assert len(data["candles"]) >= 60, f"Only {len(data['candles'])} candles"

    async def test_chart_has_indicators(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/chart/NVDA?tf=1d")
        data = r.json()
        ind = data.get("indicators", {})
        assert "ema21" in ind
        assert len(ind["ema21"]) > 30

    async def test_signal_matrix(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/signals/matrix")
        assert r.status_code == 200
        data = r.json()
        assert "rows" in data

    async def test_scan_status(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/scan/status")
        assert r.status_code == 200
        data = r.json()
        assert "running" in data
        assert "message" in data

    async def test_picks_date_filter(self):
        from httpx import ASGITransport, AsyncClient
        from eigenview.api.main import app
        today = date.today().isoformat()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/picks?date={today}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
