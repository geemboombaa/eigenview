"""Real OHLCV → score_technical tests — no synthetic DataFrames."""
from __future__ import annotations

import pytest

from eigenview.data.prices import fetch_prices
from eigenview.factors.base import FactorResult
from eigenview.factors.technical import score_technical

pytestmark = pytest.mark.data_dependent

TICKERS = ["NVDA", "AAPL", "AMD"]


@pytest.mark.asyncio
async def test_score_technical_returns_factor_result():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    assert isinstance(result, FactorResult)


@pytest.mark.asyncio
async def test_score_technical_factor_id_is_technical():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    assert result.factor_id == "technical"


@pytest.mark.asyncio
async def test_score_technical_firing_is_bool():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    assert isinstance(result.firing, bool)


@pytest.mark.asyncio
async def test_score_technical_strength_in_range():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    assert 0.0 <= result.strength <= 1.0


@pytest.mark.asyncio
async def test_score_technical_label_is_string():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    assert isinstance(result.label, str)
    assert len(result.label) > 0


@pytest.mark.asyncio
async def test_score_technical_detail_is_dict():
    df = await fetch_prices("AAPL", "1d", 90)
    result = score_technical(df, "AAPL")
    assert isinstance(result.detail, dict)


@pytest.mark.asyncio
async def test_score_technical_insufficient_real_data_no_crash():
    df = await fetch_prices("NVDA", "1d", 90)
    short = df.iloc[:10]  # real data, fewer than 30 rows
    result = score_technical(short, "NVDA")
    assert result.firing is False
    assert result.label in ("NO DATA", "no_pattern", "NO SIGNAL")


@pytest.mark.asyncio
async def test_score_technical_all_three_tickers_no_crash():
    for ticker in TICKERS:
        df = await fetch_prices(ticker, "1d", 90)
        result = score_technical(df, ticker)
        assert isinstance(result, FactorResult), f"{ticker} returned non-FactorResult"
        assert 0.0 <= result.strength <= 1.0, f"{ticker} strength out of range"
