"""Phase 6c acceptance tests for P6·16 – P6·22 pattern detection.

Patterns tested:
  P6·16  bullish_reversal     — guard: weekly RSI < 35 + bearish_weak weekly
  P6·17  bearish_reversal     — guard: weekly RSI > 65 + bullish weekly
  P6·18  oversold_bounce      — positive synthetic
  P6·19  overbought_reversal  — positive synthetic
  P6·20  failed_breakdown     — positive synthetic
  P6·21  failed_breakout      — positive synthetic (needs prior swing high < bar-4)
  P6·22  rally_in_downtrend   — positive synthetic

All use score_technical() (single-timeframe public API).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from eigenview.factors.technical import score_technical


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_df(
    closes: np.ndarray,
    volumes: np.ndarray | None = None,
    opens: np.ndarray | None = None,
    highs: np.ndarray | None = None,
    lows: np.ndarray | None = None,
) -> pd.DataFrame:
    n = len(closes)
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]
    if volumes is None:
        volumes = np.full(n, 1_000_000, dtype=float)
    if opens is None:
        opens = closes.copy()
    if highs is None:
        highs = np.maximum(opens, closes) * 1.01
    if lows is None:
        lows = np.minimum(opens, closes) * 0.99
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=pd.DatetimeIndex(dates),
    )


# ---------------------------------------------------------------------------
# P6·18 — oversold_bounce (positive)
# ---------------------------------------------------------------------------
# Construction:
#   75-bar uptrend (100→135), 4-bar crash (130, 124, 118.5, 111), 1 up-bounce bar (114).
#   Last bar: open=109 (below close=114) → up candle. Weekly has < 15 bars → wc.adx=None.
#   RSI < rsi_p20, not BEARISH_STRONG weekly, vol spike confirms.

@pytest.fixture(scope="module")
def df_oversold_bounce() -> pd.DataFrame:
    n = 80
    up = np.linspace(100, 135, 75)
    crash = np.array([130.0, 124.0, 118.5, 111.0])
    all_c = np.concatenate([up, crash, [114.0]])
    assert len(all_c) == n
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-1] = 1_500_000
    opens = all_c.copy()
    opens[-1] = 109.0  # up candle: open < close
    return _make_df(all_c, vols, opens)


def test_p618_fires(df_oversold_bounce):
    r = score_technical(df_oversold_bounce)
    assert r.label == "oversold_bounce", f"got {r.label}"
    assert r.firing is True


def test_p618_confidence_adequate(df_oversold_bounce):
    r = score_technical(df_oversold_bounce)
    assert r.detail["confidence"] >= 0.60


def test_p618_rsi_low(df_oversold_bounce):
    r = score_technical(df_oversold_bounce)
    rsi = r.detail["rsi"]
    assert rsi is not None
    assert rsi < 35, f"RSI {rsi:.1f} not low enough for oversold bounce"


def test_p618_up_candle(df_oversold_bounce):
    # Up candle = close > open on last bar. The fixture sets open[-1]=109 < close[-1]=114.
    assert df_oversold_bounce["close"].iloc[-1] > df_oversold_bounce["open"].iloc[-1]


def test_p618_antcase_no_up_candle():
    """Without an up candle (open == close), oversold_bounce must NOT fire."""
    n = 80
    up = np.linspace(100, 135, 75)
    crash = np.array([130.0, 124.0, 118.5, 111.0])
    all_c = np.concatenate([up, crash, [114.0]])
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-1] = 1_500_000
    # No up candle: open equals close
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "oversold_bounce", (
        f"oversold_bounce fired without up candle (label={r.label})"
    )


# ---------------------------------------------------------------------------
# P6·19 — overbought_reversal (positive)
# ---------------------------------------------------------------------------
# Construction:
#   60-bar baseline (95→100), 89-bar sideways noise (RSI ~50),
#   10-bar explosive +4%/bar run, 1 down bar (close = prev * 0.97).
#   open[-1] = prev close → down candle. 160 bars → 24 weekly bars.
#   RSI stays above rsi_p80 because sideways keeps p80 low (~55).

@pytest.fixture(scope="module")
def df_overbought_reversal() -> pd.DataFrame:
    np.random.seed(7)
    n = 160
    baseline = np.linspace(95, 100, 60)
    sideways = np.linspace(100, 100, 89) + np.random.randn(89) * 0.5
    prices_run = [100.0]
    for _ in range(10):
        prices_run.append(prices_run[-1] * 1.04)
    run = np.array(prices_run[1:])  # 10 bars
    down = run[-1] * 0.97
    all_c = np.concatenate([baseline, sideways, run, [down]])
    assert len(all_c) == n
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-1] = 2_000_000
    opens = all_c.copy()
    opens[-1] = run[-1]  # open > close → down candle
    return _make_df(all_c, vols, opens)


def test_p619_fires(df_overbought_reversal):
    r = score_technical(df_overbought_reversal)
    assert r.label == "overbought_reversal", f"got {r.label}"
    assert r.firing is True


def test_p619_confidence_adequate(df_overbought_reversal):
    r = score_technical(df_overbought_reversal)
    assert r.detail["confidence"] >= 0.60


def test_p619_weekly_bullish(df_overbought_reversal):
    r = score_technical(df_overbought_reversal)
    assert r.detail["weekly_trend"] == "bullish"


def test_p619_down_candle(df_overbought_reversal):
    df = df_overbought_reversal
    assert df["close"].iloc[-1] < df["open"].iloc[-1], "last bar must be a down candle"


def test_p619_antcase_no_weekly_rsi():
    """Without weekly RSI > 65, pattern must NOT fire."""
    # Use a shorter series (< 21 weekly bars) → wc.rsi = None → guard blocks
    # 60 sideways + 10 run + 1 down = 71 bars (~10 weekly bars, not enough for RSI_14)
    np.random.seed(7)
    sideways = np.linspace(100, 100, 60) + np.random.randn(60) * 0.5
    prices_run = [100.0]
    for _ in range(10):
        prices_run.append(prices_run[-1] * 1.04)
    run = np.array(prices_run[1:])
    all_c = np.concatenate([sideways, run, [run[-1] * 0.97]])
    n = len(all_c)  # 71
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-1] = 2_000_000
    opens = all_c.copy()
    opens[-1] = run[-1]
    df = _make_df(all_c, vols, opens)
    r = score_technical(df)
    # weekly_rsi = None because not enough weekly bars → overbought_reversal blocked
    assert r.label != "overbought_reversal", (
        f"overbought_reversal fired without sufficient weekly RSI (got {r.label})"
    )


# ---------------------------------------------------------------------------
# P6·20 — failed_breakdown (positive)
# ---------------------------------------------------------------------------
# Construction:
#   132-bar uptrend (100→140), 2-bar sharp crash [134, 131.5] (below EMA21),
#   4-bar recovery [135.5, 137, 139.5, 141].
#   EMA21 lags → bars at 134/131.5 were below EMA21. Current bar = 141 > EMA21.

@pytest.fixture(scope="module")
def df_failed_breakdown() -> pd.DataFrame:
    # 130-bar uptrend (100→140), 2-bar hard crash [128, 122] (below EMA21 ~136),
    # 6-bar recovery [124→127→130→133→136→139] — exceeds EMA21 but stays below
    # the 20-bar close-high of 140.  This satisfies the `close_now <= recent_high`
    # guard that separates failed_breakdown from a clean breakout.
    n = 138
    up = np.linspace(100, 140, 130)
    crash = np.array([128.0, 122.0])
    recover = np.array([124.0, 127.0, 130.0, 133.0, 136.0, 139.0])
    all_c = np.concatenate([up, crash, recover])
    assert len(all_c) == n
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-1] = 1_800_000
    return _make_df(all_c, vols)


def test_p620_fires(df_failed_breakdown):
    r = score_technical(df_failed_breakdown)
    assert r.label == "failed_breakdown", f"got {r.label}"
    assert r.firing is True


def test_p620_confidence_adequate(df_failed_breakdown):
    r = score_technical(df_failed_breakdown)
    assert r.detail["confidence"] >= 0.60


def test_p620_antcase_bearish_strong_weekly():
    """BEARISH_STRONG weekly must block failed_breakdown."""
    # Build a steep downtrend (weekly bearish_strong) with a fake dip + recovery
    n = 160
    np.random.seed(5)
    # Steep decline: each bar -1.0, with noise
    prices = [150.0]
    for i in range(n - 1):
        prices.append(prices[-1] - 1.0 + np.random.randn() * 0.2)
    all_c = np.array(prices)
    # Force last bars: sharp crash then recovery (should look like failed_breakdown)
    all_c[-6] = all_c[-7] - 8.0   # crash
    all_c[-5] = all_c[-7] - 10.0  # deeper crash
    all_c[-4] = all_c[-7] - 5.0   # recovery
    all_c[-3] = all_c[-7] - 3.0
    all_c[-2] = all_c[-7] - 1.0
    all_c[-1] = all_c[-7]          # fully recovered
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-1] = 2_000_000
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "failed_breakdown", (
        f"failed_breakdown fired in BEARISH_STRONG weekly (weekly={r.detail['weekly_trend']})"
    )


# ---------------------------------------------------------------------------
# P6·21 — failed_breakout (positive)
# ---------------------------------------------------------------------------
# Construction:
#   160-bar zigzag downtrend (-0.8/+0.5 per 9-bar cycle, net -4/cycle).
#   Natural swing high at ~bar -17 (highs_base[-17] ≈ 68.68).
#   Bar -3 high forced to 70.0 (above 68.68) → fake breakout.
#   Bars -2, -1 close back below swing high.
#   Vol last 3 bars: [700K, 750K, 800K] (< 20-bar avg ≈ 965K).
#   Weekly = bearish_strong (required, guards weekly not in ('bullish',)).
#
# NOTE: The production code uses prior_swing_idx (< 56 in 60-bar window) so the
# spike bar at -3 (index 57) is excluded from swing detection, allowing a genuine
# prior swing to serve as spH.

@pytest.fixture(scope="module")
def df_failed_breakout() -> pd.DataFrame:
    n = 160
    np.random.seed(9)
    zigzag = []
    p = 100.0
    for i in range(n):
        p -= 0.8 if i % 9 < 5 else -0.5
        zigzag.append(p)
    all_c = np.array(zigzag)
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-3:] = [700_000, 750_000, 800_000]
    highs = (all_c * 1.01).copy()
    opens = all_c.copy()
    highs[-3] = 70.0   # spike above prior swing high (~68.68)
    opens[-3] = 69.0
    return _make_df(all_c, vols, opens, highs)


def test_p621_fires(df_failed_breakout):
    r = score_technical(df_failed_breakout)
    assert r.label == "failed_breakout", f"got {r.label}"
    assert r.firing is True


def test_p621_confidence_adequate(df_failed_breakout):
    r = score_technical(df_failed_breakout)
    assert r.detail["confidence"] >= 0.60


def test_p621_weekly_not_bullish(df_failed_breakout):
    r = score_technical(df_failed_breakout)
    assert r.detail["weekly_trend"] != "bullish", (
        f"failed_breakout should not fire when weekly is bullish (got {r.detail['weekly_trend']})"
    )


def test_p621_antcase_bullish_weekly():
    """Weekly bullish context must block failed_breakout."""
    # Strong uptrend → weekly_trend = bullish → guard blocks
    n = 160
    np.random.seed(3)
    all_c = np.linspace(80, 160, n)
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-3:] = [700_000, 750_000, 800_000]
    # Fake spike above recent high then close back
    highs = (all_c * 1.01).copy()
    highs[-3] = all_c[-20:-3].max() + 5.0  # spike
    df = _make_df(all_c, vols, highs=highs)
    r = score_technical(df)
    assert r.label != "failed_breakout", (
        f"failed_breakout fired with bullish weekly (weekly={r.detail['weekly_trend']})"
    )


def test_p621_antcase_vol_expanding():
    """Expanding volume (not declining) should block failed_breakout."""
    n = 160
    np.random.seed(9)
    zigzag = []
    p = 100.0
    for i in range(n):
        p -= 0.8 if i % 9 < 5 else -0.5
        zigzag.append(p)
    all_c = np.array(zigzag)
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-3:] = [1_500_000, 2_000_000, 2_500_000]  # expanding, NOT declining
    highs = (all_c * 1.01).copy()
    opens = all_c.copy()
    highs[-3] = 70.0
    opens[-3] = 69.0
    df = _make_df(all_c, vols, opens, highs)
    r = score_technical(df)
    assert r.label != "failed_breakout", (
        f"failed_breakout fired with expanding volume (label={r.label})"
    )


# ---------------------------------------------------------------------------
# P6·22 — rally_in_downtrend (positive)
# ---------------------------------------------------------------------------
# Construction:
#   160-bar sawtooth: 5 bars down -0.8, 4 bars up +0.64, repeating.
#   Net decline: weekly bearish_strong.
#   Vol last 3 bars: [800K, 750K, 700K] (declining, < 20-bar avg).
#   RSI settles near mid-zone [rsi_p43, rsi_p62].
#   Price just below EMA21 (within 2%).

@pytest.fixture(scope="module")
def df_rally_in_downtrend() -> pd.DataFrame:
    n = 160
    np.random.seed(11)
    cycle = []
    p = 140.0
    for i in range(n):
        if i % 9 < 5:
            p -= 0.8
        else:
            p += 0.64
        cycle.append(p)
    all_c = np.array(cycle)
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-3:] = [800_000, 750_000, 700_000]
    return _make_df(all_c, vols)


def test_p622_fires(df_rally_in_downtrend):
    r = score_technical(df_rally_in_downtrend)
    assert r.label == "rally_in_downtrend", f"got {r.label}"
    assert r.firing is True


def test_p622_confidence_adequate(df_rally_in_downtrend):
    r = score_technical(df_rally_in_downtrend)
    assert r.detail["confidence"] >= 0.60


def test_p622_weekly_bearish(df_rally_in_downtrend):
    r = score_technical(df_rally_in_downtrend)
    assert r.detail["weekly_trend"] in ("bearish_strong", "bearish_weak"), (
        f"expected bearish weekly, got {r.detail['weekly_trend']}"
    )


def test_p622_antcase_bullish_weekly():
    """rally_in_downtrend must NOT fire in bullish weekly context."""
    np.random.seed(11)
    n = 160
    # Strong uptrend → weekly bullish → guard blocks
    all_c = np.linspace(80, 140, n)
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-3:] = [800_000, 750_000, 700_000]
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "rally_in_downtrend", (
        f"rally_in_downtrend fired with bullish weekly (weekly={r.detail['weekly_trend']})"
    )


def test_p622_antcase_high_volume():
    """High volume (expanding) should block rally_in_downtrend (vol < vol_p55 required)."""
    np.random.seed(11)
    n = 160
    cycle = []
    p = 140.0
    for i in range(n):
        if i % 9 < 5:
            p -= 0.8
        else:
            p += 0.64
        cycle.append(p)
    all_c = np.array(cycle)
    vols = np.full(n, 1_000_000, dtype=float)
    vols[-3:] = [2_000_000, 2_500_000, 3_000_000]  # high vol = not declining bounce
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "rally_in_downtrend", (
        f"rally_in_downtrend fired with expanding volume (label={r.label})"
    )


# ---------------------------------------------------------------------------
# P6·16 — bullish_reversal guard tests (anti-case only)
# ---------------------------------------------------------------------------
# Positive case is mathematically difficult to synthesize: requires simultaneous
# weekly RSI < 35 (prolonged selling) AND weekly ADX <= 25 (bearish_weak =
# slow drift, not panic). These are near-contradictory in synthetic data.
# We test the guard conditions by verifying the pattern does NOT fire when
# the P6·16-specific guards are absent.

def test_p616_antcase_bearish_strong_weekly():
    """bullish_reversal must NOT fire when weekly is BEARISH_STRONG (not bearish_weak)."""
    n = 160
    np.random.seed(42)
    # Steep decline → bearish_strong
    prices = [140.0]
    for _ in range(n - 1):
        prices.append(prices[-1] - 0.5 + np.random.randn() * 0.3)
    all_c = np.array(prices)
    # Bounce at end (two-bar confirm)
    all_c[-1] = all_c[-2] + 2.0
    vols = np.full(n, 2_000_000, dtype=float)  # high vol
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "bullish_reversal", (
        f"bullish_reversal fired in BEARISH_STRONG weekly (weekly={r.detail['weekly_trend']})"
    )


def test_p616_antcase_flat_trend():
    """bullish_reversal must NOT fire when trend is not a downtrend (in_downtrend_20 = False)."""
    n = 90
    np.random.seed(0)
    # Sideways → EMA21 ≈ EMA50, ADX low → in_downtrend_20 = False
    all_c = 100 + np.random.randn(n) * 1.0
    vols = np.full(n, 1_000_000, dtype=float)
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "bullish_reversal", (
        f"bullish_reversal fired in sideways market (label={r.label})"
    )


# ---------------------------------------------------------------------------
# P6·17 — bearish_reversal guard tests (anti-case only)
# ---------------------------------------------------------------------------
# Positive case requires: wc.rsi > 65 + bullish weekly + bear_div + RSI > rsi_p85.
# bear_div requires price making higher high while RSI makes lower high over 20 bars.
# This is extremely hard to engineer synthetically without it being caught by
# overbought_reversal (higher in elif chain). We test the guards only.

def test_p617_antcase_insufficient_weekly_bars():
    """bearish_reversal must NOT fire when wc.rsi is None (not enough weekly bars)."""
    np.random.seed(7)
    n = 80  # ~11 weekly bars → wc.rsi = None → guard wc.rsi > 65 fails
    all_c = np.linspace(100, 140, n)
    vols = np.full(n, 1_500_000, dtype=float)
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "bearish_reversal", (
        f"bearish_reversal fired without sufficient weekly RSI (label={r.label})"
    )


def test_p617_antcase_bearish_daily_trend():
    """bearish_reversal requires daily_trend == 'bullish'; must NOT fire in downtrend."""
    np.random.seed(3)
    n = 160
    all_c = np.linspace(140, 90, n)  # strong decline → bearish daily
    vols = np.full(n, 1_500_000, dtype=float)
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "bearish_reversal", (
        f"bearish_reversal fired in bearish daily trend (label={r.label})"
    )


def test_p617_antcase_weekly_not_bullish():
    """bearish_reversal requires weekly_trend == 'bullish'; must NOT fire in bearish weekly."""
    # A stock with bearish weekly won't hit the 'bullish' weekly check
    np.random.seed(9)
    n = 160
    cycle = []
    p = 140.0
    for i in range(n):
        if i % 9 < 5:
            p -= 0.8
        else:
            p += 0.5
        cycle.append(p)
    all_c = np.array(cycle)
    vols = np.full(n, 1_500_000, dtype=float)
    df = _make_df(all_c, vols)
    r = score_technical(df)
    assert r.label != "bearish_reversal", (
        f"bearish_reversal fired with non-bullish weekly (weekly={r.detail['weekly_trend']})"
    )
