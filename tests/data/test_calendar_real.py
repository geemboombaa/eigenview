"""Real yfinance + Finnhub calendar tests — no mocks, no patches."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from eigenview.data.calendar import days_to_next_catalyst, get_catalysts

pytestmark = pytest.mark.data_dependent


@pytest.mark.asyncio
async def test_get_catalysts_nvda_returns_list():
    events = await get_catalysts("NVDA")
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_get_catalysts_fields_present_when_nonempty():
    events = await get_catalysts("NVDA")
    if events:
        ev = events[0]
        assert "event_type" in ev
        assert "event_date" in ev
        assert "days_from_now" in ev
        assert "ticker" in ev


@pytest.mark.asyncio
async def test_get_catalysts_event_dates_are_real_dates():
    events = await get_catalysts("AAPL")
    for ev in events:
        edate = ev["event_date"]
        assert isinstance(edate, date), f"event_date must be date, got {type(edate)}"


@pytest.mark.asyncio
async def test_get_catalysts_days_from_now_matches_event_date():
    events = await get_catalysts("NVDA")
    today = date.today()
    for ev in events:
        edate = ev["event_date"]
        if isinstance(edate, date):
            expected = (edate - today).days
            assert abs(ev["days_from_now"] - expected) <= 1, (
                f"days_from_now={ev['days_from_now']} doesn't match computed {expected}"
            )


@pytest.mark.asyncio
async def test_get_catalysts_event_type_is_string():
    events = await get_catalysts("MSFT")
    for ev in events:
        assert isinstance(ev["event_type"], str)
        assert len(ev["event_type"]) > 0


@pytest.mark.asyncio
async def test_days_to_next_catalyst_returns_int_or_none():
    result = await days_to_next_catalyst("NVDA")
    assert result is None or isinstance(result, int)


@pytest.mark.asyncio
async def test_days_to_next_catalyst_positive_when_set():
    result = await days_to_next_catalyst("NVDA")
    if result is not None:
        assert result >= 0
