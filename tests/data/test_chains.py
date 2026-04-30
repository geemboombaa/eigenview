from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_calls(n: int = 4, include_zero_iv: bool = False) -> pd.DataFrame:
    strikes = [100.0 + i * 5 for i in range(n)]
    ivs = [0.25 + i * 0.05 for i in range(n)]
    if include_zero_iv:
        ivs[0] = 0.0  # first row has bad IV
    expiry = (date.today().replace(month=date.today().month % 12 + 1)).isoformat()
    return pd.DataFrame(
        {
            "strike": strikes,
            "bid": [1.0] * n,
            "ask": [1.5] * n,
            "volume": [100] * n,
            "openInterest": [500] * n,
            "impliedVolatility": ivs,
            "expiration": [expiry] * n,
        }
    )


def _make_raw_puts(n: int = 4) -> pd.DataFrame:
    df = _make_raw_calls(n)
    return df


def _make_ticker_obj(calls_df: pd.DataFrame, puts_df: pd.DataFrame, expiry: str) -> MagicMock:
    ticker_obj = MagicMock()
    ticker_obj.options = [expiry]
    hist = pd.DataFrame({"Close": [150.0]})
    ticker_obj.history.return_value = hist
    chain = MagicMock()
    chain.calls = calls_df
    chain.puts = puts_df
    ticker_obj.option_chain.return_value = chain
    return ticker_obj


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
    )
    mock_session.commit = AsyncMock()
    monkeypatch.setattr("eigenview.data.chains.AsyncSessionLocal", lambda: mock_session)


# ---------------------------------------------------------------------------
# Test 1: fetch_chain returns dict with calls and puts keys, both DataFrames
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_chain_returns_correct_structure():
    expiry = "2025-06-20"
    calls_raw = _make_raw_calls(4)
    puts_raw = _make_raw_puts(4)
    ticker_obj = _make_ticker_obj(calls_raw, puts_raw, expiry)

    with patch("eigenview.data.chains._get_ticker_data", return_value=([expiry], 150.0, ticker_obj)), \
         patch("eigenview.data.chains._get_option_chain", return_value=(calls_raw, puts_raw)):

        from eigenview.data.chains import fetch_chain

        result = await fetch_chain("AAPL")

    assert "calls" in result
    assert "puts" in result
    assert "iv_rank" in result
    assert isinstance(result["calls"], pd.DataFrame)
    assert isinstance(result["puts"], pd.DataFrame)
    assert isinstance(result["iv_rank"], float)
    assert not result["calls"].empty
    assert not result["puts"].empty


# ---------------------------------------------------------------------------
# Test 2: rows with iv=0 filtered before Greeks computed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_chain_filters_zero_iv():
    expiry = "2025-06-20"
    calls_raw = _make_raw_calls(4, include_zero_iv=True)
    puts_raw = _make_raw_puts(4)
    ticker_obj = _make_ticker_obj(calls_raw, puts_raw, expiry)

    with patch("eigenview.data.chains._get_ticker_data", return_value=([expiry], 150.0, ticker_obj)), \
         patch("eigenview.data.chains._get_option_chain", return_value=(calls_raw, puts_raw)):

        from eigenview.data.chains import fetch_chain

        result = await fetch_chain("AAPL")

    calls = result["calls"]
    # The row with iv=0 must not appear in the output
    assert (calls["iv"] > 0).all(), "All remaining rows must have positive IV"
    assert len(calls) == 3  # one filtered out


# ---------------------------------------------------------------------------
# Test 3: bad ticker (empty options list) → empty DataFrames, no crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_chain_empty_expiries():
    ticker_obj = MagicMock()
    ticker_obj.options = []
    ticker_obj.history.return_value = pd.DataFrame({"Close": [100.0]})

    with patch("eigenview.data.chains._get_ticker_data", return_value=([], 100.0, ticker_obj)):
        from eigenview.data.chains import fetch_chain

        result = await fetch_chain("BADTICKER")

    assert result["calls"].empty
    assert result["puts"].empty
    assert result["iv_rank"] == 0.0


# ---------------------------------------------------------------------------
# Test 4: gamma column present and non-null for valid rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_chain_gamma_present_and_valid():
    expiry = "2025-09-19"
    calls_raw = _make_raw_calls(3)
    puts_raw = _make_raw_puts(3)

    with patch("eigenview.data.chains._get_ticker_data", return_value=([expiry], 150.0, MagicMock())), \
         patch("eigenview.data.chains._get_option_chain", return_value=(calls_raw, puts_raw)):

        from eigenview.data.chains import fetch_chain

        result = await fetch_chain("TSLA")

    calls = result["calls"]
    assert "gamma" in calls.columns
    # With valid IV and spot, gamma should be computed (not all NaN)
    non_null_gamma = calls["gamma"].dropna()
    assert len(non_null_gamma) > 0, "At least some gamma values should be non-null"
