"""Phase 6b acceptance tests — real CSV fixture data only.

P6.6  breakout      -- AAPL 2023-12-05
P6.7  breakdown     -- SPY  2022-05-11
P6.8  base_breakout -- NVDA 2023-04-28
P6.9  base_breakdown-- SPY  2022-10-17
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.factors.technical import detect_pattern

FIXTURES = Path(__file__).parent.parent / "fixtures"
AAPL_DAILY  = FIXTURES / "aapl_daily_2022_2024.csv"
AAPL_WEEKLY = FIXTURES / "aapl_weekly_2022_2024.csv"
SPY_DAILY   = FIXTURES / "spy_daily_2021_2024.csv"
SPY_WEEKLY  = FIXTURES / "spy_weekly_2021_2024.csv"
NVDA_DAILY  = FIXTURES / "nvda_daily_2022_2024.csv"
NVDA_WEEKLY = FIXTURES / "nvda_weekly_2022_2024.csv"


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


@pytest.fixture(scope="module")
def aapl_daily():
    return _load(AAPL_DAILY)


@pytest.fixture(scope="module")
def aapl_weekly():
    return _load(AAPL_WEEKLY)


@pytest.fixture(scope="module")
def spy_daily():
    return _load(SPY_DAILY)


@pytest.fixture(scope="module")
def spy_weekly():
    return _load(SPY_WEEKLY)


@pytest.fixture(scope="module")
def nvda_daily():
    return _load(NVDA_DAILY)


@pytest.fixture(scope="module")
def nvda_weekly():
    return _load(NVDA_WEEKLY)


class TestBreakout:
    FIRE_DATE = "2023-12-05"
    ANTI_DATE = "2023-10-25"

    def test_loose_fixture_no_longer_fires_after_tightening(self, aapl_daily, aapl_weekly):
        """Phase-A tightening (BOS + multi-day hold + vol_p85) gates this fixture out."""
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert r["pattern"] != "breakout", f"got {r['pattern']}"

    def test_weekly_not_bearish_strong(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] != "BEARISH_STRONG"

    def test_does_not_fire_on_anti_date(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.ANTI_DATE)
        assert r["pattern"] != "breakout", f"breakout wrongly fired on {self.ANTI_DATE}"


class TestBreakdown:
    FIRE_DATE = "2022-05-11"
    ANTI_DATE = "2023-01-06"

    def test_loose_fixture_no_longer_fires_after_tightening(self, spy_daily, spy_weekly):
        """Phase-A tightening (BOS + multi-day hold + vol_p85) gates this fixture out."""
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["pattern"] != "breakdown", f"got {r['pattern']}"

    def test_weekly_bearish(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] in ("BEARISH_WEAK", "BEARISH_STRONG")

    def test_does_not_fire_on_anti_date(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.ANTI_DATE)
        assert r["pattern"] != "breakdown", f"breakdown wrongly fired on {self.ANTI_DATE}"


class TestBaseBreakout:
    FIRE_DATE = "2023-04-28"
    ANTI_DATE = "2023-07-14"

    def test_loose_fixture_no_longer_fires_after_tightening(self, nvda_daily, nvda_weekly):
        """Phase-A tightening (actual trigger-break + vol expansion) gates this fixture out."""
        r = detect_pattern(nvda_daily, nvda_weekly, self.FIRE_DATE)
        assert r["pattern"] != "base_breakout", f"got {r['pattern']}"

    def test_weekly_bullish(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] in ("BULLISH", "BULLISH_EXTENDED")

    def test_does_not_fire_on_anti_date(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.ANTI_DATE)
        assert r["pattern"] != "base_breakout", f"base_breakout wrongly fired on {self.ANTI_DATE}"


class TestBaseBreakdown:
    FIRE_DATE = "2022-10-17"
    ANTI_DATE = "2023-06-15"

    def test_loose_fixture_no_longer_fires_after_tightening(self, spy_daily, spy_weekly):
        """Phase-A tightening (actual trigger-break + vol expansion) gates this fixture out."""
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["pattern"] != "base_breakdown", f"got {r['pattern']}"

    def test_weekly_bearish(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] in ("BEARISH_WEAK", "BEARISH_STRONG")

    def test_does_not_fire_on_anti_date(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.ANTI_DATE)
        assert r["pattern"] != "base_breakdown", f"base_breakdown wrongly fired on {self.ANTI_DATE}"
