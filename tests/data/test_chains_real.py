"""Real yfinance options chain tests — no mocks, no patches."""
from __future__ import annotations

import pytest
import pandas as pd

from eigenview.data.chains import fetch_chain

pytestmark = pytest.mark.data_dependent


@pytest.mark.asyncio
async def test_fetch_chain_nvda_returns_dict():
    result = await fetch_chain("NVDA")
    assert isinstance(result, dict)
    assert "calls" in result
    assert "puts" in result
    assert "iv_rank" in result


@pytest.mark.asyncio
async def test_fetch_chain_nvda_calls_is_dataframe():
    result = await fetch_chain("NVDA")
    assert isinstance(result["calls"], pd.DataFrame)
    assert isinstance(result["puts"], pd.DataFrame)


@pytest.mark.asyncio
async def test_fetch_chain_nvda_has_required_columns():
    result = await fetch_chain("NVDA")
    calls = result["calls"]
    if not calls.empty:
        assert {"strike", "iv", "gamma"}.issubset(calls.columns)


@pytest.mark.asyncio
async def test_fetch_chain_iv_all_positive():
    result = await fetch_chain("NVDA")
    calls = result["calls"]
    if not calls.empty:
        assert (calls["iv"] > 0).all(), "All IV values must be positive (zero-IV rows filtered)"


@pytest.mark.asyncio
async def test_fetch_chain_iv_rank_in_valid_range():
    result = await fetch_chain("NVDA")
    assert 0.0 <= result["iv_rank"] <= 1.0


@pytest.mark.asyncio
async def test_fetch_chain_gamma_column_has_values():
    result = await fetch_chain("NVDA")
    calls = result["calls"]
    if not calls.empty and "gamma" in calls.columns:
        non_null = calls["gamma"].dropna()
        assert len(non_null) > 0, "At least some gamma values must be non-null"


@pytest.mark.asyncio
async def test_fetch_chain_aapl_structure_matches_nvda():
    result = await fetch_chain("AAPL")
    assert "calls" in result
    assert "puts" in result
    assert "iv_rank" in result


@pytest.mark.asyncio
async def test_fetch_chain_bad_ticker_returns_empty():
    result = await fetch_chain("XXXXXXNOTREAL")
    assert result["calls"].empty
    assert result["puts"].empty
    assert result["iv_rank"] == 0.0
