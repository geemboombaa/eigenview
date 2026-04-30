from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Shared DB mock
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # Default: execute returns empty result (cache miss)
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = []
    mock_execute_result.scalars.return_value.first.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.commit = AsyncMock()

    monkeypatch.setattr("eigenview.data.calendar.AsyncSessionLocal", lambda: mock_session)
    return mock_session


# ---------------------------------------------------------------------------
# Test 1: get_catalysts returns list with event_type and event_date fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_catalysts_returns_required_fields():
    future_date = date.today() + timedelta(days=30)

    def fake_yf_calendar(ticker: str) -> list[dict]:
        return [
            {
                "ticker": ticker.upper(),
                "event_type": "earnings",
                "event_date": future_date,
                "days_from_now": (future_date - date.today()).days,
            }
        ]

    async def fake_finnhub(ticker: str) -> list[dict]:
        return []

    with patch("eigenview.data.calendar._yf_calendar", side_effect=fake_yf_calendar), \
         patch("eigenview.data.calendar._finnhub_earnings", side_effect=fake_finnhub):

        from eigenview.data.calendar import get_catalysts

        events = await get_catalysts("AAPL")

    assert len(events) >= 1
    ev = events[0]
    assert "event_type" in ev
    assert "event_date" in ev
    assert "ticker" in ev
    assert "days_from_now" in ev


# ---------------------------------------------------------------------------
# Test 2: days_from_now computed correctly from today
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_days_from_now_accuracy():
    today = date.today()
    offset = 45
    future_date = today + timedelta(days=offset)

    def fake_yf_calendar(ticker: str) -> list[dict]:
        return [
            {
                "ticker": ticker.upper(),
                "event_type": "earnings",
                "event_date": future_date,
                "days_from_now": (future_date - today).days,
            }
        ]

    async def fake_finnhub(ticker: str) -> list[dict]:
        return []

    with patch("eigenview.data.calendar._yf_calendar", side_effect=fake_yf_calendar), \
         patch("eigenview.data.calendar._finnhub_earnings", side_effect=fake_finnhub):

        from eigenview.data.calendar import get_catalysts

        events = await get_catalysts("MSFT")

    ev = events[0]
    assert ev["days_from_now"] == offset
    assert ev["event_date"] == future_date


# ---------------------------------------------------------------------------
# Test 3: no earnings → returns empty list, no crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_catalysts_empty_result():
    def fake_yf_calendar(ticker: str) -> list[dict]:
        return []

    async def fake_finnhub(ticker: str) -> list[dict]:
        return []

    with patch("eigenview.data.calendar._yf_calendar", side_effect=fake_yf_calendar), \
         patch("eigenview.data.calendar._finnhub_earnings", side_effect=fake_finnhub):

        from eigenview.data.calendar import get_catalysts

        events = await get_catalysts("ZZZZ")

    assert events == []


# ---------------------------------------------------------------------------
# Test 4: days_to_next_catalyst returns int when earnings exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_days_to_next_catalyst_returns_int():
    today = date.today()
    offset = 20
    future_date = today + timedelta(days=offset)

    def fake_yf_calendar(ticker: str) -> list[dict]:
        return [
            {
                "ticker": ticker.upper(),
                "event_type": "earnings",
                "event_date": future_date,
                "days_from_now": offset,
            }
        ]

    async def fake_finnhub(ticker: str) -> list[dict]:
        return []

    with patch("eigenview.data.calendar._yf_calendar", side_effect=fake_yf_calendar), \
         patch("eigenview.data.calendar._finnhub_earnings", side_effect=fake_finnhub):

        from eigenview.data.calendar import days_to_next_catalyst

        result = await days_to_next_catalyst("NVDA")

    assert isinstance(result, int)
    assert result == offset
