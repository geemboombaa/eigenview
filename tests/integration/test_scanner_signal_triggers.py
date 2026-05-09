"""tests/integration/test_scanner_signal_triggers.py

Integration test: verify daily scan writes to signal_triggers table.
Uses real DB (Postgres). Marked data_dependent.
"""
from __future__ import annotations

import asyncio
import pytest

from sqlalchemy import text


@pytest.mark.data_dependent
def test_signal_triggers_populated_after_scan():
    """
    GIVEN a completed daily scan
    WHEN we query signal_triggers
    THEN at least one row exists with valid setup_type, direction, confidence
    """
    async def _check():
        from eigenview.data.storage import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            r = await s.execute(text(
                "SELECT ticker, setup_type, direction, confidence FROM signal_triggers LIMIT 10"
            ))
            return r.fetchall()

    rows = asyncio.run(_check())
    assert rows, "signal_triggers is empty — scanner did not write triggers"
    for row in rows:
        ticker, setup_type, direction, confidence = row
        assert ticker and len(ticker) >= 2, f"Invalid ticker: {ticker}"
        assert setup_type and len(setup_type) >= 3, f"Invalid setup_type: {setup_type}"
        assert direction in ("long", "short"), f"Invalid direction: {direction}"
        if confidence is not None:
            assert 0.0 <= confidence <= 1.0, f"confidence {confidence} out of [0,1]"


@pytest.mark.data_dependent
def test_signal_triggers_setup_type_is_known_pattern():
    """All setup_types in signal_triggers must be from the known TA taxonomy."""
    from eigenview.ci.condition_coverage import REQUIRED_PATTERNS

    async def _check():
        from eigenview.data.storage import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            r = await s.execute(text("SELECT DISTINCT setup_type FROM signal_triggers"))
            return [row[0] for row in r.fetchall()]

    setup_types = asyncio.run(_check())
    if not setup_types:
        pytest.skip("No signal_triggers rows — run daily-scan first")

    for st in setup_types:
        assert st in REQUIRED_PATTERNS, (
            f"setup_type '{st}' not in REQUIRED_PATTERNS taxonomy. "
            "Either add to REQUIRED_PATTERNS or fix the scanner."
        )


@pytest.mark.data_dependent
def test_signal_triggers_entry_stop_relationship():
    """entry_low < entry_high and stop < entry_low for long picks."""
    async def _check():
        from eigenview.data.storage import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            r = await s.execute(text(
                "SELECT ticker, direction, entry_low, entry_high, stop "
                "FROM signal_triggers "
                "WHERE entry_low IS NOT NULL AND entry_high IS NOT NULL AND stop IS NOT NULL"
            ))
            return r.fetchall()

    rows = asyncio.run(_check())
    if not rows:
        pytest.skip("No signal_triggers rows with entry/stop data")

    for ticker, direction, el, eh, stop in rows:
        assert el < eh, f"{ticker}: entry_low {el} >= entry_high {eh}"
        if direction == "long":
            assert stop < el, f"{ticker} long: stop {stop} >= entry_low {el}"
        elif direction == "short":
            assert stop > eh, f"{ticker} short: stop {stop} <= entry_high {eh}"
