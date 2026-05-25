"""
Integration tests for the scanner's live-fetch path.

Covers src/eigenview/synthesis/scanner.py:
  - _fetch_live: pulls real OHLCV from yfinance (replaces the old get_prices call)
  - _score_with_lookback: walks back up to `lookback` bars to find a firing setup

Real data only: hits live yfinance. No mocks, no synthetic frames.
Run: uv run pytest tests/integration/test_scanner_live_fetch.py -v -s
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from eigenview.synthesis.scanner import _fetch_live, _score_with_lookback


@pytest_asyncio.fixture
async def nvda_live():
    return await _fetch_live("NVDA")


class TestFetchLive:

    def test_returns_enough_rows(self, nvda_live):
        assert len(nvda_live) >= 50, f"Only {len(nvda_live)} rows from live 200d fetch"

    def test_has_lowercase_ohlc_columns(self, nvda_live):
        for col in ["open", "high", "low", "close"]:
            assert col in nvda_live.columns, f"Missing column {col}: got {list(nvda_live.columns)}"

    def test_no_null_close(self, nvda_live):
        assert nvda_live["close"].isna().sum() == 0

    def test_plausible_spot(self, nvda_live):
        last = float(nvda_live["close"].iloc[-1])
        assert 10 < last < 10_000, f"Implausible close: {last}"


class TestScoreWithLookback:

    def test_returns_technical_factor(self, nvda_live):
        r = _score_with_lookback(nvda_live, "NVDA")
        assert r.factor_id == "technical"

    def test_strength_in_range(self, nvda_live):
        r = _score_with_lookback(nvda_live, "NVDA")
        assert 0.0 <= r.strength <= 1.0

    def test_lookback_zero_matches_direct_score(self, nvda_live):
        from eigenview.factors.technical import score_technical
        direct = score_technical(nvda_live, "NVDA")
        looked = _score_with_lookback(nvda_live, "NVDA", lookback=0)
        assert looked.label == direct.label
