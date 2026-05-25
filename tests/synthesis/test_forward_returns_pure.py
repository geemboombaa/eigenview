"""Pure + real-DB tests for forward_returns (no network)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from eigenview.synthesis.forward_returns import (
    _trading_day_offset,
    populate_forward_returns_for_date,
)


def test_trading_day_offset_is_after_start():
    start = date(2024, 1, 2)
    off5 = _trading_day_offset(start, 5)
    off20 = _trading_day_offset(start, 20)
    assert off5 > start
    assert off20 > off5


def test_trading_day_offset_covers_more_calendar_than_trading_days():
    start = date(2024, 1, 2)
    # 5 trading days should map to >5 calendar days (weekends)
    assert (_trading_day_offset(start, 5) - start).days > 5


@pytest.mark.asyncio
async def test_populate_no_picks_returns_zero():
    # A date far in the past with no picks in the DB -> nothing to update.
    n = await populate_forward_returns_for_date(date(2000, 1, 3))
    assert n == 0
