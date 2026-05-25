"""Real yfinance price tests — no mocks, no patches, no synthetic data."""
from __future__ import annotations

import pytest
import pandas as pd

from eigenview.data.exceptions import DataNotFoundError
from eigenview.data.prices import fetch_prices

pytestmark = pytest.mark.data_dependent


@pytest.mark.asyncio
async def test_fetch_prices_nvda_returns_dataframe():
    df = await fetch_prices("NVDA", "1d", 90)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


@pytest.mark.asyncio
async def test_fetch_prices_nvda_has_ohlcv_columns():
    df = await fetch_prices("NVDA", "1d", 90)
    assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)


@pytest.mark.asyncio
async def test_fetch_prices_nvda_min_row_count():
    df = await fetch_prices("NVDA", "1d", 90)
    assert len(df) >= 50  # weekends + holidays reduce from 90


@pytest.mark.asyncio
async def test_fetch_prices_close_prices_positive():
    df = await fetch_prices("NVDA", "1d", 90)
    assert (df["close"] > 0).all()


@pytest.mark.asyncio
async def test_fetch_prices_volume_non_negative():
    df = await fetch_prices("NVDA", "1d", 90)
    assert (df["volume"] >= 0).all()


@pytest.mark.asyncio
async def test_fetch_prices_stale_attr_always_set():
    df = await fetch_prices("AAPL", "1d", 30)
    assert "stale" in df.attrs
    assert isinstance(df.attrs["stale"], bool)


@pytest.mark.asyncio
async def test_fetch_prices_index_is_datetime():
    df = await fetch_prices("MSFT", "1d", 30)
    assert hasattr(df.index, "dtype")
    assert "datetime" in str(df.index.dtype)


@pytest.mark.asyncio
async def test_fetch_prices_bad_ticker_raises():
    with pytest.raises(DataNotFoundError):
        await fetch_prices("XXXXXXNOTREAL", "1d", 90)
