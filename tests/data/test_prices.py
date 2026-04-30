from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from eigenview.data.exceptions import DataNotFoundError


def _make_price_df(newest_days_ago: int = 0, rows: int = 5) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame as yfinance would return it."""
    today = pd.Timestamp.now(tz=timezone.utc).normalize() - timedelta(days=newest_days_ago)
    idx = pd.date_range(end=today, periods=rows, freq="D", tz=timezone.utc)
    df = pd.DataFrame(
        {
            "open": [100.0] * rows,
            "high": [105.0] * rows,
            "low": [95.0] * rows,
            "close": [102.0] * rows,
            "volume": [1_000_000] * rows,
        },
        index=idx,
    )
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# Shared DB mock — prevents any real DB calls in all tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Patch AsyncSessionLocal so no real DB connection is attempted."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    mock_session.commit = AsyncMock()

    mock_session_local = MagicMock(return_value=mock_session)
    mock_session_local.__call__ = MagicMock(return_value=mock_session)

    monkeypatch.setattr(
        "eigenview.data.prices.AsyncSessionLocal",
        lambda: mock_session,
    )


# ---------------------------------------------------------------------------
# Test 1: happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_prices_happy_path():
    """Mock yfinance download returns a valid DataFrame; result has correct shape."""
    fake_df = _make_price_df(newest_days_ago=0, rows=10)

    with patch("eigenview.data.prices._download", return_value=fake_df):
        from eigenview.data.prices import fetch_prices

        result = await fetch_prices("AAPL", timeframe="1d", days=10)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty
    assert set(result.columns) >= {"open", "high", "low", "close", "volume"}
    assert len(result) == 10
    assert result.attrs.get("stale") is False


# ---------------------------------------------------------------------------
# Test 2: empty result → DataNotFoundError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_prices_empty_raises():
    """Empty yfinance result must raise DataNotFoundError."""
    empty_df = pd.DataFrame()

    with patch("eigenview.data.prices._download", return_value=empty_df):
        from eigenview.data.prices import fetch_prices

        with pytest.raises(DataNotFoundError):
            await fetch_prices("BADTICKER", timeframe="1d", days=90)


# ---------------------------------------------------------------------------
# Test 3: stale data detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_prices_stale_flag():
    """When newest row is 2 days old, df.attrs['stale'] must be True."""
    fake_df = _make_price_df(newest_days_ago=2, rows=5)

    with patch("eigenview.data.prices._download", return_value=fake_df):
        from eigenview.data.prices import fetch_prices

        result = await fetch_prices("AAPL", timeframe="1d", days=5)

    assert result.attrs["stale"] is True


# ---------------------------------------------------------------------------
# Test 4: determinism — same mock input produces identical output twice
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_prices_deterministic():
    """Same mock input must produce identical DataFrames on repeated calls."""
    fake_df = _make_price_df(newest_days_ago=0, rows=7)

    with patch("eigenview.data.prices._download", return_value=fake_df.copy()):
        from eigenview.data.prices import fetch_prices

        result1 = await fetch_prices("MSFT", timeframe="1d", days=7)

    with patch("eigenview.data.prices._download", return_value=fake_df.copy()):
        result2 = await fetch_prices("MSFT", timeframe="1d", days=7)

    pd.testing.assert_frame_equal(result1, result2)
