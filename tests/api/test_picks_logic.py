"""Real tests for picks route logic — pure structure/serialization + route handlers via app client."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from eigenview.api.routes.picks import _pick_to_dict, recommend_structure
from eigenview.data.storage import Pick


class TestRecommendStructure:

    def test_breakout_low_iv_is_bull_call_spread(self):
        s = recommend_structure("breakout", "long", iv_rank=30.0)
        assert s["type"] == "bull_call_spread"

    def test_pullback_low_iv_is_long_call(self):
        s = recommend_structure("pullback", "long", iv_rank=20.0)
        assert s["type"] == "long_call"

    def test_long_high_iv_defined_risk_spread(self):
        s = recommend_structure("breakout", "long", iv_rank=80.0)
        assert s["type"] == "bull_call_spread"

    def test_short_is_bear_put_spread(self):
        s = recommend_structure("breakdown", "short", iv_rank=50.0)
        assert s["type"] == "bear_put_spread"

    def test_none_iv_defaults_to_fifty(self):
        s = recommend_structure("pullback", "long", iv_rank=None)
        # iv defaults to 50 -> pullback branch needs <40, so falls through to spread
        assert s["type"] == "bull_call_spread"


def _pick(signal_age_hours: float | None) -> Pick:
    p = Pick()
    p.ticker = "NVDA"
    p.date = date.today()
    p.conviction = 4
    p.setup_type = "breakout"
    p.direction = "long"
    p.entry_low = 100.0
    p.entry_high = 102.0
    p.stop = 97.0
    p.thesis = "test thesis"
    p.factors_json = '{"technical": {"detail": {"iv_rank": 35}}}'
    p.signal_fired_at = (
        datetime.utcnow() - timedelta(hours=signal_age_hours)
        if signal_age_hours is not None
        else None
    )
    return p


class TestPickToDict:

    def test_fresh_signal(self):
        d = _pick_to_dict(_pick(1.0))
        assert d["freshness"] == "fresh"
        assert d["ticker"] == "NVDA"
        assert d["structure"]["type"] in ("bull_call_spread", "long_call")

    def test_valid_signal(self):
        assert _pick_to_dict(_pick(5.0))["freshness"] == "valid"

    def test_stale_signal(self):
        assert _pick_to_dict(_pick(20.0))["freshness"] == "stale"

    def test_no_signal_time_unknown(self):
        d = _pick_to_dict(_pick(None))
        assert d["freshness"] == "unknown"
        assert d["signal_age_hours"] is None

    def test_iv_rank_extracted_from_factors(self):
        assert _pick_to_dict(_pick(1.0))["iv_rank"] == 35


@pytest.mark.asyncio
class TestPicksRoutes:

    async def _client(self):
        from eigenview.api.main import app
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def test_picks_returns_list(self):
        async with await self._client() as c:
            r = await c.get("/api/picks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_picks_bad_date_400(self):
        async with await self._client() as c:
            r = await c.get("/api/picks?date=not-a-date")
        assert r.status_code == 400

    async def test_pick_dates_returns_list(self):
        async with await self._client() as c:
            r = await c.get("/api/picks/dates")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_pick_unknown_ticker_404(self):
        async with await self._client() as c:
            r = await c.get("/api/pick/ZZZZNOPE")
        assert r.status_code == 404

    async def test_pick_factors_unknown_ticker_404(self):
        async with await self._client() as c:
            r = await c.get("/api/pick/ZZZZNOPE/factors")
        assert r.status_code == 404
