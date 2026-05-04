"""Phase 6b acceptance tests for detect_pattern -- 6 new setups.

P6.6  breakout         -- AAPL 2023-12-05 (broke above Oct-Nov resistance)
P6.7  breakdown        -- SPY  2022-05-11 (broke below Apr-May support on high vol)
P6.8  base_breakout    -- NVDA 2023-04-28 (VCP coil near highs before AI rally)
P6.9  base_breakdown   -- SPY  2022-10-17 (VCP at lows, weekly BEARISH_STRONG)
P6.10 ema_reclaim      -- synthetic (deterministic, avoids yfinance latency)
P6.11 ema_rejection    -- synthetic (deterministic)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
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


# ─── fixture helpers ──────────────────────────────────────────────────────────

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


# ─── Synthetic EMA-crossover helpers ─────────────────────────────────────────

def _make_ema_reclaim_df() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a daily+weekly DataFrame where EMA50 is reclaimed on the final bar.

    Construction:
    - Bars 0-79: flat at 100 so EMA50 converges to ~100 and weekly stays NEUTRAL
    - Bars 80-118: dip to 97 (clearly below EMA50 which stays ~99-100)
    - Bar 119: jump to 101 (above EMA50 ~97-98) with volume spike
    """
    n = 120
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    close = np.full(n, 100.0)
    close[80:119] = 97.0
    close[119] = 101.0
    high  = close + 0.5
    low   = close - 0.5
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    vol_base = 5_000_000
    np.random.seed(42)
    volume = np.random.randint(vol_base, int(vol_base * 1.2), n).astype(float)
    volume[119] = vol_base * 2.8
    daily = pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=dates)
    weekly = daily.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"}
    ).dropna()
    return daily, weekly


def _make_ema_rejection_df() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a daily+weekly DataFrame where EMA50 is rejected on the final bar.

    Construction (weekly must be bearish; must NOT trigger squeeze/BBL conditions):
    - Bars 0-119: noisy downtrend from 130 to ~90 (daily noise prevents squeeze formation)
    - Bar 118: overridden to 1.02 * EMA50 (one bar above EMA50)
    - Bar 119: overridden to 0.98 * EMA50 (drops below EMA50) + vol spike
    The large daily noise keeps BBL well below close, so compression_break_down
    does not fire and ema_rejection wins.
    """
    n = 120
    dates = pd.date_range("2022-01-03", periods=n, freq="B")
    np.random.seed(99)
    close = np.zeros(n, dtype=float)
    close[0] = 130.0
    for i in range(1, n):
        noise = np.random.normal(0, 1.5)   # large noise -> no squeeze
        close[i] = close[i - 1] * 0.997 + noise
        close[i] = max(close[i], 80.0)

    # Compute approximate EMA50 to place the crossover
    alpha = 2.0 / 51.0
    ema50 = close.copy()
    for i in range(1, n):
        ema50[i] = alpha * close[i] + (1 - alpha) * ema50[i - 1]

    # Crossover: bar 118 above, bar 119 below
    close[118] = ema50[118] * 1.02
    close[119] = ema50[119] * 0.98

    high   = close + abs(np.random.normal(0, 0.5, n))
    low    = close - abs(np.random.normal(0, 0.5, n))
    open_  = np.roll(close, 1)
    open_[0] = close[0]
    vol_base = 5_000_000
    volume = np.random.randint(vol_base, int(vol_base * 1.3), n).astype(float)
    volume[119] = vol_base * 2.8
    daily = pd.DataFrame({
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=dates)
    weekly = daily.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"}
    ).dropna()
    return daily, weekly


# =============================================================================
# P6.6 -- breakout
# =============================================================================

class TestBreakout:
    """AAPL 2023-12-05: broke above the Oct-Nov 2023 resistance on vol surge."""

    FIRE_DATE = "2023-12-05"
    ANTI_DATE = "2023-10-25"  # price well below any swing high

    def test_fires(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert r["pattern"] == "breakout", (
            f"expected breakout, got {r['pattern']} (conf={r['confidence']:.2f})"
        )

    def test_confidence_ge_0_75(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert r["confidence"] >= 0.75, f"conf={r['confidence']:.3f}"

    def test_n_bar_high_in_detail(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert "n_bar_high" in r["detail"], "n_bar_high missing from detail"
        assert r["detail"]["n_bar_high"] > 0

    def test_prior_approaches_ge_1(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert r["detail"].get("prior_approaches", 0) >= 1

    def test_weekly_not_bearish_strong(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] != "BEARISH_STRONG"

    def test_does_not_fire_on_anti_date(self, aapl_daily, aapl_weekly):
        r = detect_pattern(aapl_daily, aapl_weekly, self.ANTI_DATE)
        assert r["pattern"] != "breakout", (
            f"breakout wrongly fired on {self.ANTI_DATE}"
        )


# =============================================================================
# P6.7 -- breakdown
# =============================================================================

class TestBreakdown:
    """SPY 2022-05-11: broke below Apr-May 2022 support on high vol bear market."""

    FIRE_DATE = "2022-05-11"
    ANTI_DATE = "2023-01-06"  # SPY recovering, no breakdown

    def test_fires(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["pattern"] == "breakdown", (
            f"expected breakdown, got {r['pattern']} (conf={r['confidence']:.2f})"
        )

    def test_confidence_ge_0_75(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["confidence"] >= 0.75, f"conf={r['confidence']:.3f}"

    def test_weekly_bearish(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] in ("BEARISH_WEAK", "BEARISH_STRONG"), (
            f"weekly_state={r['detail']['weekly_state']}"
        )

    def test_n_bar_low_in_detail(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert "n_bar_low" in r["detail"]
        assert r["detail"]["n_bar_low"] > 0

    def test_does_not_fire_on_anti_date(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.ANTI_DATE)
        assert r["pattern"] != "breakdown", (
            f"breakdown wrongly fired on {self.ANTI_DATE}"
        )


# =============================================================================
# P6.8 -- base_breakout (VCP)
# =============================================================================

class TestBaseBreakout:
    """NVDA 2023-04-28: tight VCP coil near 50d high before the AI rally."""

    FIRE_DATE = "2023-04-28"
    ANTI_DATE = "2023-07-14"  # SPY bull market, not in a VCP base

    def test_fires(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.FIRE_DATE)
        assert r["pattern"] == "base_breakout", (
            f"expected base_breakout, got {r['pattern']} (conf={r['confidence']:.2f})"
        )

    def test_confidence_ge_0_65(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.FIRE_DATE)
        assert r["confidence"] >= 0.65, f"conf={r['confidence']:.3f}"

    def test_weekly_bullish(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] in ("BULLISH", "BULLISH_EXTENDED"), (
            f"weekly_state={r['detail']['weekly_state']}"
        )

    def test_high_50d_in_detail(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.FIRE_DATE)
        assert "high_50d" in r["detail"]
        assert r["detail"]["high_50d"] > 0

    def test_does_not_fire_on_anti_date(self, nvda_daily, nvda_weekly):
        r = detect_pattern(nvda_daily, nvda_weekly, self.ANTI_DATE)
        assert r["pattern"] != "base_breakout", (
            f"base_breakout wrongly fired on {self.ANTI_DATE}"
        )


# =============================================================================
# P6.9 -- base_breakdown (short VCP)
# =============================================================================

class TestBaseBreakdown:
    """SPY 2022-10-17: coiling in tight range near 50d low, weekly BEARISH_STRONG."""

    FIRE_DATE = "2022-10-17"
    ANTI_DATE = "2023-06-15"  # SPY bull market -- not near 50d low

    def test_fires(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["pattern"] == "base_breakdown", (
            f"expected base_breakdown, got {r['pattern']} (conf={r['confidence']:.2f})"
        )

    def test_confidence_ge_0_65(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["confidence"] >= 0.65, f"conf={r['confidence']:.3f}"

    def test_weekly_bearish(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert r["detail"]["weekly_state"] in ("BEARISH_WEAK", "BEARISH_STRONG"), (
            f"weekly_state={r['detail']['weekly_state']}"
        )

    def test_low_50d_in_detail(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.FIRE_DATE)
        assert "low_50d" in r["detail"]
        assert r["detail"]["low_50d"] > 0

    def test_does_not_fire_on_anti_date(self, spy_daily, spy_weekly):
        r = detect_pattern(spy_daily, spy_weekly, self.ANTI_DATE)
        assert r["pattern"] != "base_breakdown", (
            f"base_breakdown wrongly fired on {self.ANTI_DATE}"
        )


# =============================================================================
# P6.10 -- ema_reclaim
# =============================================================================

class TestEmaReclaim:
    """Synthetic: yesterday below EMA50, today reclaims above EMA50 on vol surge."""

    def test_fires(self):
        daily, weekly = _make_ema_reclaim_df()
        r = detect_pattern(daily, weekly)
        assert r["pattern"] == "ema_reclaim", (
            f"expected ema_reclaim, got {r['pattern']} (conf={r['confidence']:.2f})"
        )

    def test_confidence_ge_0_60(self):
        daily, weekly = _make_ema_reclaim_df()
        r = detect_pattern(daily, weekly)
        assert r["confidence"] >= 0.60, f"conf={r['confidence']:.3f}"

    def test_weekly_not_bearish_strong(self):
        daily, weekly = _make_ema_reclaim_df()
        r = detect_pattern(daily, weekly)
        assert r["detail"]["weekly_state"] != "BEARISH_STRONG", (
            f"weekly_state={r['detail']['weekly_state']} should not be BEARISH_STRONG"
        )

    def test_does_not_fire_when_no_volume(self):
        """If volume is flat (no spike), ema_reclaim should not fire."""
        daily, weekly = _make_ema_reclaim_df()
        daily_mod = daily.copy()
        avg_vol = float(daily_mod["volume"].iloc[-20:-1].mean())
        daily_mod.iloc[-1, daily_mod.columns.get_loc("volume")] = avg_vol * 0.8
        r = detect_pattern(daily_mod, weekly)
        assert r["pattern"] != "ema_reclaim", (
            f"ema_reclaim should not fire when vol is below vol_p55"
        )


# =============================================================================
# P6.11 -- ema_rejection
# =============================================================================

class TestEmaRejection:
    """Synthetic: yesterday above EMA50, today rejected below EMA50 on vol."""

    def test_fires(self):
        daily, weekly = _make_ema_rejection_df()
        r = detect_pattern(daily, weekly)
        assert r["pattern"] == "ema_rejection", (
            f"expected ema_rejection, got {r['pattern']} (conf={r['confidence']:.2f})"
        )

    def test_confidence_ge_0_60(self):
        daily, weekly = _make_ema_rejection_df()
        r = detect_pattern(daily, weekly)
        assert r["confidence"] >= 0.60, f"conf={r['confidence']:.3f}"

    def test_weekly_not_bullish(self):
        daily, weekly = _make_ema_rejection_df()
        r = detect_pattern(daily, weekly)
        assert r["detail"]["weekly_state"] not in ("BULLISH", "BULLISH_EXTENDED"), (
            f"weekly_state={r['detail']['weekly_state']} -- rejection needs bearish/neutral weekly"
        )

    def test_does_not_fire_when_no_volume(self):
        """If volume is flat (no spike), ema_rejection should not fire."""
        daily, weekly = _make_ema_rejection_df()
        daily_mod = daily.copy()
        avg_vol = float(daily_mod["volume"].iloc[-20:-1].mean())
        daily_mod.iloc[-1, daily_mod.columns.get_loc("volume")] = avg_vol * 0.8
        r = detect_pattern(daily_mod, weekly)
        assert r["pattern"] != "ema_rejection", (
            f"ema_rejection should not fire when vol is below vol_p55"
        )
