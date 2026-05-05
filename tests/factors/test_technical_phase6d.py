"""Phase 6d acceptance tests for P6·12–P6·15 (CHoCH/BOS) and P6·23–P6·26 (mean reversion).

Patterns tested:
  P6·12  choch_bullish             — CHoCH bull + weekly NEUTRAL/BEARISH_WEAK
  P6·13  choch_bearish             — CHoCH bear + weekly NEUTRAL/BULLISH
  P6·14  bos_bullish               — BOS bull + weekly BULLISH
  P6·15  bos_bearish               — BOS bear + weekly BEARISH
  P6·23  bb_mean_reversion_long    — price <= lower BB + ADX<p35 + RSI oversold
  P6·24  bb_mean_reversion_short   — price >= upper BB + ADX<p35 + RSI overbought
  P6·25  ema200_snap_long          — >15% below EMA200 + weekly RSI<35 + up day
  P6·26  ema200_snap_short         — >15% above EMA200 + weekly RSI>70 + down day

All use detect_pattern() (explicit daily + weekly DataFrames).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from eigenview.factors.technical import detect_pattern


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_daily(
    closes: np.ndarray,
    volumes: np.ndarray | None = None,
    opens: np.ndarray | None = None,
    highs: np.ndarray | None = None,
    lows: np.ndarray | None = None,
) -> pd.DataFrame:
    n = len(closes)
    dates = pd.date_range("2021-01-01", periods=n, freq="B")
    if volumes is None:
        volumes = np.full(n, 1_000_000, dtype=float)
    if opens is None:
        opens = closes.copy()
    if highs is None:
        highs = np.maximum(opens, closes) * 1.015
    if lows is None:
        lows = np.minimum(opens, closes) * 0.985
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=pd.DatetimeIndex(dates),
    )


def _make_weekly(closes: np.ndarray) -> pd.DataFrame:
    """Weekly OHLCV from close array for _classify_weekly_state."""
    n = len(closes)
    dates = pd.date_range("2021-01-01", periods=n, freq="W-FRI")
    opens = closes.copy()
    highs = closes * 1.02
    lows  = closes * 0.98
    vols  = np.full(n, 5_000_000, dtype=float)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )


# ---------------------------------------------------------------------------
# P6·12 — choch_bullish
# ---------------------------------------------------------------------------
# Structure: bearish market with clear CHoCH bullish signal in last 30 bars.
# Uses a price series with explicit lower-lows / lower-highs then break above prior swing high.

@pytest.fixture(scope="module")
def df_choch_bullish():
    """150-bar downtrend with bullish CHoCH in final segment.

    Weekly is NEUTRAL (very slow drift, ADX <25) so that BOS bearish
    (which requires BEARISH_WEAK or BEARISH_STRONG) does NOT fire,
    while CHoCH bullish (NEUTRAL or BEARISH_WEAK) can fire.
    """
    n = 150
    prices = np.zeros(n)
    prices[0:20]   = np.linspace(100, 85, 20)
    prices[20:30]  = np.linspace(85, 92, 10)
    prices[30:50]  = np.linspace(92, 78, 20)
    prices[50:60]  = np.linspace(78, 86, 10)
    prices[60:80]  = np.linspace(86, 72, 20)
    prices[80:90]  = np.linspace(72, 80, 10)
    prices[90:110] = np.linspace(80, 66, 20)
    prices[110:120]= np.linspace(66, 95, 10)   # reversal: breaks above prior high 86 → CHoCH!
    prices[120:150]= np.linspace(95, 105, 30)
    daily  = _make_daily(prices)
    # Weekly NEUTRAL: flat with very small net change → EMA8 ≈ EMA21, ADX < 25, no BEARISH_STRONG
    # Use 50 weekly bars with a gentle zigzag so EMA8/21 gap < 2% AND ADX stays < 25
    np.random.seed(77)
    w_close = 95 + np.random.randn(50) * 1.5   # purely sideways weekly → NEUTRAL
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p612_fires(df_choch_bullish):
    daily, weekly = df_choch_bullish
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "choch_bullish", f"got {r['pattern']}"
    assert r["confidence"] >= 0.65


def test_p612_detail_present(df_choch_bullish):
    daily, weekly = df_choch_bullish
    r = detect_pattern(daily, weekly)
    assert r["detail"].get("choch_bullish") is True


def test_p612_antcase_bullish_extended_weekly(df_choch_bullish):
    """BULLISH_EXTENDED weekly blocks choch_bullish (wrong context)."""
    daily, _ = df_choch_bullish
    # Weekly strongly bullish = BULLISH_EXTENDED (RSI>70)
    w_close = np.linspace(70, 130, 30)
    weekly_bull = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bull)
    assert r["pattern"] != "choch_bullish", (
        f"choch_bullish fired in BULLISH_EXTENDED weekly (got {r['pattern']})"
    )


def test_p612_antcase_bearish_strong_weekly(df_choch_bullish):
    """BEARISH_STRONG weekly blocks choch_bullish."""
    daily, _ = df_choch_bullish
    # Steep aggressive decline → BEARISH_STRONG
    w_close = np.linspace(150, 60, 35)
    weekly_bear = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bear)
    assert r["pattern"] != "choch_bullish", (
        f"choch_bullish fired in BEARISH_STRONG weekly (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·13 — choch_bearish
# ---------------------------------------------------------------------------
# Structure: bullish market with CHoCH bearish signal in final segment.

@pytest.fixture(scope="module")
def df_choch_bearish():
    """150-bar uptrend with bearish CHoCH in final segment."""
    n = 150
    prices = np.zeros(n)
    prices[0:20]   = np.linspace(60, 75, 20)    # up
    prices[20:30]  = np.linspace(75, 68, 10)    # pullback (higher low)
    prices[30:50]  = np.linspace(68, 84, 20)    # up (higher high)
    prices[50:60]  = np.linspace(84, 76, 10)    # pullback (higher low)
    prices[60:80]  = np.linspace(76, 93, 20)    # up (higher high)
    prices[80:90]  = np.linspace(93, 84, 10)    # pullback (higher low)
    prices[90:110] = np.linspace(84, 102, 20)   # up (higher high)
    prices[110:120]= np.linspace(102, 72, 10)   # reversal: breaks below prior low 76 → CHoCH!
    prices[120:150]= np.linspace(72, 60, 30)    # continuation
    daily  = _make_daily(prices)
    # Weekly: bullish (EMA8 > EMA21)
    w_close = np.linspace(70, 110, 25)
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p613_fires(df_choch_bearish):
    daily, weekly = df_choch_bearish
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "choch_bearish", f"got {r['pattern']}"
    assert r["confidence"] >= 0.65


def test_p613_detail_present(df_choch_bearish):
    daily, weekly = df_choch_bearish
    r = detect_pattern(daily, weekly)
    assert r["detail"].get("choch_bearish") is True


def test_p613_antcase_bearish_strong_weekly(df_choch_bearish):
    """BEARISH_STRONG weekly blocks choch_bearish (already in downtrend — not reversal context)."""
    daily, _ = df_choch_bearish
    w_close = np.linspace(150, 60, 35)
    weekly_bear = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bear)
    assert r["pattern"] != "choch_bearish", (
        f"choch_bearish fired in BEARISH_STRONG weekly (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·14 — bos_bullish
# ---------------------------------------------------------------------------
# BOS bullish = continuation: higher highs AND higher lows in a bullish trend.
# The BOS fires at the latest continuation swing high break.

@pytest.fixture(scope="module")
def df_bos_bullish():
    """150-bar uptrend with BOS bullish (continuation) signal."""
    n = 150
    prices = np.zeros(n)
    # Clean bullish structure: HH-HL-HH-HL-HH...
    prices[0:20]   = np.linspace(60, 75, 20)
    prices[20:30]  = np.linspace(75, 69, 10)    # pullback (higher low than start)
    prices[30:50]  = np.linspace(69, 85, 20)    # new high (BOS 1)
    prices[50:60]  = np.linspace(85, 78, 10)    # pullback
    prices[60:80]  = np.linspace(78, 96, 20)    # new high (BOS 2)
    prices[80:90]  = np.linspace(96, 88, 10)    # pullback
    prices[90:110] = np.linspace(88, 108, 20)   # new high (BOS 3)
    prices[110:130]= np.linspace(108, 99, 20)   # pullback
    prices[130:150]= np.linspace(99, 120, 20)   # new high (BOS 4 — recent)
    daily  = _make_daily(prices)
    # Weekly: bullish (rising trend)
    w_close = np.linspace(70, 115, 30)
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p614_fires(df_bos_bullish):
    daily, weekly = df_bos_bullish
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "bos_bullish", f"got {r['pattern']}"
    assert r["confidence"] >= 0.60


def test_p614_detail_present(df_bos_bullish):
    daily, weekly = df_bos_bullish
    r = detect_pattern(daily, weekly)
    assert r["detail"].get("bos_bullish") is True


def test_p614_antcase_bearish_weekly(df_bos_bullish):
    """BEARISH_WEAK weekly blocks bos_bullish."""
    daily, _ = df_bos_bullish
    w_close = np.linspace(120, 70, 30)
    weekly_bear = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bear)
    assert r["pattern"] != "bos_bullish", (
        f"bos_bullish fired in BEARISH_WEAK weekly (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·15 — bos_bearish
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df_bos_bearish():
    """150-bar downtrend with BOS bearish (continuation) signal."""
    n = 150
    prices = np.zeros(n)
    # Clean bearish structure: LL-LH-LL-LH-LL...
    prices[0:20]   = np.linspace(120, 105, 20)
    prices[20:30]  = np.linspace(105, 112, 10)  # bounce (lower high)
    prices[30:50]  = np.linspace(112, 96, 20)   # new low (BOS 1)
    prices[50:60]  = np.linspace(96, 103, 10)   # bounce
    prices[60:80]  = np.linspace(103, 87, 20)   # new low (BOS 2)
    prices[80:90]  = np.linspace(87, 94, 10)    # bounce
    prices[90:110] = np.linspace(94, 78, 20)    # new low (BOS 3)
    prices[110:130]= np.linspace(78, 86, 20)    # bounce
    prices[130:150]= np.linspace(86, 68, 20)    # new low (BOS 4 — recent)
    daily  = _make_daily(prices)
    # Weekly: bearish_weak
    w_close = np.linspace(120, 75, 30)
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p615_fires(df_bos_bearish):
    daily, weekly = df_bos_bearish
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "bos_bearish", f"got {r['pattern']}"
    assert r["confidence"] >= 0.60


def test_p615_detail_present(df_bos_bearish):
    daily, weekly = df_bos_bearish
    r = detect_pattern(daily, weekly)
    assert r["detail"].get("bos_bearish") is True


def test_p615_antcase_bullish_weekly(df_bos_bearish):
    """BULLISH weekly blocks bos_bearish."""
    daily, _ = df_bos_bearish
    w_close = np.linspace(70, 120, 30)
    weekly_bull = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bull)
    assert r["pattern"] != "bos_bearish", (
        f"bos_bearish fired in BULLISH weekly (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·23 — bb_mean_reversion_long
# ---------------------------------------------------------------------------
# Price at/below lower Bollinger Band + ADX < p35 (non-trending) + RSI oversold

@pytest.fixture(scope="module")
def df_bb_mr_long():
    """Sideways market with single-bar spike down well below lower BB.

    A single large down day from a flat base avoids creating alternating swing
    highs/lows that would trigger CHoCH/BOS. ADX stays below 20 from the
    preceding sideways period; the spike produces extreme RSI.
    """
    np.random.seed(42)
    n = 150
    # Flat base at 100 for ALL bars (tiny noise)
    prices = 100 + np.random.randn(n) * 0.2
    # Single spike down on last bar — this is below BBL which is ~96 (100 - 2*std=2)
    # But std of tiny-noise data is ~0.2, so BBL = 100 - 2*0.2*sqrt(20) ~ 98.2
    # Actually for tiny noise, std~0.2, BBL ~ 99.1. Need a bigger spike.
    # Let's use slightly larger noise so BBL is more sensible:
    np.random.seed(42)
    prices = 100 + np.random.randn(n) * 1.5  # std ~1.5, BBL ~ 100 - 2*1.5*sqrt(20) ~ 86.6
    # Last bar: spike down to 80 (well below BBL ~86.6)
    prices[-2] = 100.0   # restore near-flat to keep ADX low
    prices[-1] = 80.0    # single spike down: well below lower BB
    opens = prices.copy()
    opens[-1] = 82.0     # close < open so far below BB
    daily  = _make_daily(prices, opens=opens)
    # Weekly: NEUTRAL (flat, no trend)
    np.random.seed(42)
    w_close = 100 + np.random.randn(25) * 0.8
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p623_fires(df_bb_mr_long):
    daily, weekly = df_bb_mr_long
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "bb_mean_reversion_long", f"got {r['pattern']}"
    assert r["confidence"] >= 0.60


def test_p623_detail_has_bbl(df_bb_mr_long):
    daily, weekly = df_bb_mr_long
    r = detect_pattern(daily, weekly)
    assert "bbl" in r["detail"]


def test_p623_antcase_bearish_strong_weekly(df_bb_mr_long):
    """BEARISH_STRONG weekly blocks bb_mean_reversion_long."""
    daily, _ = df_bb_mr_long
    w_close = np.linspace(150, 60, 35)
    weekly_bear = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bear)
    assert r["pattern"] != "bb_mean_reversion_long", (
        f"bb_mean_reversion_long fired in BEARISH_STRONG (got {r['pattern']})"
    )


def test_p623_antcase_high_adx():
    """High ADX (trending) blocks bb_mean_reversion_long (mean reversion needs non-trending)."""
    np.random.seed(5)
    n = 150
    # Strong downtrend: ADX will be high
    prices = np.linspace(130, 80, n)
    prices[-3] = 78.0
    prices[-2] = 75.0
    prices[-1] = 72.0   # below lower BB but in strong downtrend
    daily  = _make_daily(prices)
    w_close = np.linspace(130, 80, 30)
    weekly = _make_weekly(w_close)
    r = detect_pattern(daily, weekly)
    assert r["pattern"] != "bb_mean_reversion_long", (
        f"bb_mean_reversion_long fired with high ADX/trend (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·24 — bb_mean_reversion_short
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df_bb_mr_short():
    """Sideways market with single-bar spike UP well above upper BB.

    A single large up day from a flat base avoids CHoCH/BOS swing structure.
    """
    np.random.seed(99)
    n = 150
    # Flat base with std ~1.5 → BBU ~ 100 + 2*1.5*sqrt(20) ~ 113.4
    prices = 100 + np.random.randn(n) * 1.5
    # Restore second-to-last bar to flat
    prices[-2] = 100.0
    # Spike up on last bar to 122 — well above upper BB ~113
    prices[-1] = 122.0
    opens = prices.copy()
    opens[-1] = 120.0    # open < close: up candle
    daily  = _make_daily(prices, opens=opens)
    # Weekly: BULLISH but NOT BULLISH_EXTENDED (RSI stays < 70).
    # Slower uptrend with small noise to keep RSI moderate.
    # This blocks choch_bullish (needs NEUTRAL/BEARISH_WEAK) and is allowed by bb_mr_short.
    np.random.seed(77)
    w_close = np.linspace(90, 100, 50) + np.random.randn(50) * 0.5  # 50 bars, gentle slope
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p624_fires(df_bb_mr_short):
    daily, weekly = df_bb_mr_short
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "bb_mean_reversion_short", f"got {r['pattern']}"
    assert r["confidence"] >= 0.60


def test_p624_detail_has_bbu(df_bb_mr_short):
    daily, weekly = df_bb_mr_short
    r = detect_pattern(daily, weekly)
    assert "bbu" in r["detail"]


def test_p624_antcase_bullish_extended_weekly(df_bb_mr_short):
    """BULLISH_EXTENDED weekly blocks bb_mean_reversion_short."""
    daily, _ = df_bb_mr_short
    # Weekly RSI > 70 → BULLISH_EXTENDED
    w_close = np.linspace(70, 140, 30)
    weekly_bull = _make_weekly(w_close)
    r = detect_pattern(daily, weekly_bull)
    assert r["pattern"] != "bb_mean_reversion_short", (
        f"bb_mean_reversion_short fired in BULLISH_EXTENDED (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·25 — ema200_snap_long
# ---------------------------------------------------------------------------
# Price > 15% below EMA200 + weekly RSI < 35 + ADX trending + up day

@pytest.fixture(scope="module")
def df_ema200_snap_long():
    """350-bar data: 300-bar sideways building EMA200, then extreme crash >20% below.

    EMA200 of a flat 100 series = 100. Crash to 78 = -22% deviation.
    Weekly: long uptrend then crash to produce weekly RSI < 35.
    """
    n = 350
    prices = np.zeros(n)
    # 300 bars flat at 100 → EMA200 will converge near 100
    prices[:300] = 100.0
    # Then hard crash: 300→348 from 100→78 (~22% below EMA200 which lags at ~98-99)
    prices[300:348] = np.linspace(100, 78, 48)
    prices[348] = 77.0   # low
    prices[349] = 80.0   # up day: close > open
    opens = prices.copy()
    opens[349] = 77.5   # up candle
    highs = np.maximum(opens, prices) * 1.01
    lows  = np.minimum(opens, prices) * 0.99
    vols  = np.full(n, 1_000_000, dtype=float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    # Weekly: long flat then severe crash → weekly RSI < 35
    # Need enough bars for RSI_14 (≥15), and the crash to produce oversold RSI
    w_n = 80
    w_close = np.zeros(w_n)
    w_close[:65] = 100.0             # long flat
    w_close[65:] = np.linspace(100, 72, 15)  # crash → weekly RSI very low
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p625_fires(df_ema200_snap_long):
    daily, weekly = df_ema200_snap_long
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "ema200_snap_long", f"got {r['pattern']}"
    assert r["confidence"] >= 0.60


def test_p625_detail_deviation(df_ema200_snap_long):
    daily, weekly = df_ema200_snap_long
    r = detect_pattern(daily, weekly)
    assert "ema200_deviation_pct" in r["detail"]
    assert r["detail"]["ema200_deviation_pct"] < -14.0


def test_p625_antcase_no_up_day():
    """Without an up day (down candle), ema200_snap_long must NOT fire."""
    n = 350
    prices = np.zeros(n)
    prices[:300] = 100.0
    prices[300:348] = np.linspace(100, 78, 48)
    prices[348] = 77.0
    prices[349] = 75.0   # DOWN bar: close < open
    opens = prices.copy()
    opens[349] = 79.0    # open > close → down candle
    highs = np.maximum(opens, prices) * 1.01
    lows  = np.minimum(opens, prices) * 0.99
    vols  = np.full(n, 1_000_000, dtype=float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    w_n = 80
    w_close = np.zeros(w_n)
    w_close[:65] = 100.0
    w_close[65:] = np.linspace(100, 72, 15)
    weekly = _make_weekly(w_close)
    r = detect_pattern(daily, weekly)
    assert r["pattern"] != "ema200_snap_long", (
        f"ema200_snap_long fired without up day (got {r['pattern']})"
    )


def test_p625_antcase_small_deviation():
    """Only 5% below EMA200 is not enough — must be >15%."""
    n = 350
    prices = np.zeros(n)
    prices[:300] = 100.0
    # Only 5% below EMA200 (~100): ~95
    prices[300:348] = np.linspace(100, 95, 48)
    prices[348] = 94.5
    prices[349] = 96.0   # up day
    opens = prices.copy()
    opens[349] = 94.0
    highs = np.maximum(opens, prices) * 1.01
    lows  = np.minimum(opens, prices) * 0.99
    vols  = np.full(n, 1_000_000, dtype=float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    w_n = 80
    w_close = np.zeros(w_n)
    w_close[:65] = 100.0
    w_close[65:] = np.linspace(100, 93, 15)
    weekly = _make_weekly(w_close)
    r = detect_pattern(daily, weekly)
    assert r["pattern"] != "ema200_snap_long", (
        f"ema200_snap_long fired with only 5%% deviation (got {r['pattern']})"
    )


# ---------------------------------------------------------------------------
# P6·26 — ema200_snap_short
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df_ema200_snap_short():
    """250-bar data: 200-bar build, then rally >15% above EMA200 + overbought."""
    n = 250
    prices = np.zeros(n)
    prices[:200] = np.linspace(80, 100, 200)   # EMA200 builds ~90-100
    # Then parabolic rally: >15% above EMA200 (~100) = 115+
    prices[200:248] = np.linspace(100, 122, 48)
    prices[248] = 123.0
    prices[249] = 121.0   # DOWN bar: close < open
    opens = prices.copy()
    opens[249] = 124.0    # open > close → down candle
    highs = np.maximum(opens, prices) * 1.01
    lows  = np.minimum(opens, prices) * 0.99
    vols  = np.full(n, 1_000_000, dtype=float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    # Weekly: overbought RSI > 70
    w_n = 60
    w_close = np.zeros(w_n)
    w_close[:50] = np.linspace(80, 100, 50)
    w_close[50:] = np.linspace(100, 122, 10)  # rally → weekly RSI very high
    weekly = _make_weekly(w_close)
    return daily, weekly


def test_p626_fires(df_ema200_snap_short):
    daily, weekly = df_ema200_snap_short
    r = detect_pattern(daily, weekly)
    assert r["pattern"] == "ema200_snap_short", f"got {r['pattern']}"
    assert r["confidence"] >= 0.60


def test_p626_detail_deviation(df_ema200_snap_short):
    daily, weekly = df_ema200_snap_short
    r = detect_pattern(daily, weekly)
    assert "ema200_deviation_pct" in r["detail"]
    assert r["detail"]["ema200_deviation_pct"] > 14.0


def test_p626_antcase_no_down_day():
    """Without a down day (up candle), ema200_snap_short must NOT fire."""
    n = 250
    prices = np.zeros(n)
    prices[:200] = np.linspace(80, 100, 200)
    prices[200:248] = np.linspace(100, 122, 48)
    prices[248] = 123.0
    prices[249] = 125.0   # UP bar: close > open
    opens = prices.copy()
    opens[249] = 123.0    # open < close → up candle
    highs = np.maximum(opens, prices) * 1.01
    lows  = np.minimum(opens, prices) * 0.99
    vols  = np.full(n, 1_000_000, dtype=float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    w_close = np.concatenate([np.linspace(80, 100, 50), np.linspace(100, 122, 10)])
    weekly = _make_weekly(w_close)
    r = detect_pattern(daily, weekly)
    assert r["pattern"] != "ema200_snap_short", (
        f"ema200_snap_short fired without down day (got {r['pattern']})"
    )


def test_p626_antcase_small_deviation():
    """Only 5% above EMA200 is not enough."""
    n = 250
    prices = np.zeros(n)
    prices[:200] = np.linspace(80, 100, 200)
    prices[200:248] = np.linspace(100, 106, 48)   # ~6% above EMA200
    prices[248] = 106.0
    prices[249] = 104.0  # down day
    opens = prices.copy()
    opens[249] = 107.0
    highs = np.maximum(opens, prices) * 1.01
    lows  = np.minimum(opens, prices) * 0.99
    vols  = np.full(n, 1_000_000, dtype=float)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols},
        index=pd.DatetimeIndex(dates),
    )
    w_close = np.concatenate([np.linspace(80, 100, 50), np.linspace(100, 106, 10)])
    weekly = _make_weekly(w_close)
    r = detect_pattern(daily, weekly)
    assert r["pattern"] != "ema200_snap_short", (
        f"ema200_snap_short fired with only 6%% deviation (got {r['pattern']})"
    )
