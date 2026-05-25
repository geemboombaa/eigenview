"""Real scanner tests — real DB, real yfinance data, no mocks."""
from __future__ import annotations

import pytest

from eigenview.data.storage import AsyncSessionLocal
from eigenview.data.universe import get_universe
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.scanner import run_daily_scan

pytestmark = pytest.mark.data_dependent


async def _ndx_sample(n: int = 2) -> list[str]:
    tickers = await get_universe("ndx100")
    return tickers[:n] if tickers else ["AAPL", "MSFT"]


@pytest.mark.asyncio
async def test_run_daily_scan_returns_list():
    tickers = await _ndx_sample(2)
    async with AsyncSessionLocal() as session:
        results = await run_daily_scan(tickers, session)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_run_daily_scan_scorecards_are_typed():
    tickers = await _ndx_sample(1)
    async with AsyncSessionLocal() as session:
        results = await run_daily_scan(tickers, session)
    for r in results:
        assert isinstance(r, TickerScorecard), f"Expected TickerScorecard, got {type(r)}"


@pytest.mark.asyncio
async def test_run_daily_scan_spot_price_positive():
    tickers = await _ndx_sample(1)
    async with AsyncSessionLocal() as session:
        results = await run_daily_scan(tickers, session)
    for r in results:
        assert r.spot_price > 0, f"{r.ticker} spot_price={r.spot_price} must be positive"


@pytest.mark.asyncio
async def test_run_daily_scan_all_factors_present():
    tickers = await _ndx_sample(1)
    async with AsyncSessionLocal() as session:
        results = await run_daily_scan(tickers, session)
    for r in results:
        assert r.technical is not None
        assert r.gex is not None
        assert r.flow is not None
        assert r.dormant is not None
        assert r.sentiment is not None
        assert r.macro is not None


@pytest.mark.asyncio
async def test_run_daily_scan_factor_strengths_in_range():
    tickers = await _ndx_sample(2)
    async with AsyncSessionLocal() as session:
        results = await run_daily_scan(tickers, session)
    for r in results:
        for factor in (r.technical, r.gex, r.flow, r.dormant, r.sentiment):
            assert 0.0 <= factor.strength <= 1.0, (
                f"{r.ticker}.{factor.factor_id}.strength={factor.strength} out of [0,1]"
            )


@pytest.mark.asyncio
async def test_run_daily_scan_ticker_field_matches_input():
    tickers = await _ndx_sample(1)
    async with AsyncSessionLocal() as session:
        results = await run_daily_scan(tickers, session)
    result_tickers = {r.ticker for r in results}
    if results:
        assert result_tickers.issubset(set(tickers))
