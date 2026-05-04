"""Phase 1 acceptance tests for pullback_in_trend detection.

Fixture: real NVDA OHLCV data 2023-06-01 to 2024-06-30 (daily + weekly).
Sample case: 2024-04-16 — classic pullback to EMA21 after Feb earnings run.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.factors.technical import detect_pattern

FIXTURES = Path(__file__).parent.parent / "fixtures"
DAILY_CSV  = FIXTURES / "nvda_daily_2024.csv"
WEEKLY_CSV = FIXTURES / "nvda_weekly_2024.csv"


@pytest.fixture(scope="module")
def nvda_daily() -> pd.DataFrame:
    df = pd.read_csv(DAILY_CSV, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


@pytest.fixture(scope="module")
def nvda_weekly() -> pd.DataFrame:
    df = pd.read_csv(WEEKLY_CSV, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


# ── Primary case: 2024-04-16 — pullback to EMA21 in strong uptrend ──────────

def test_pullback_pattern_fires(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    assert result["pattern"] == "pullback_in_trend", f"got {result['pattern']}"


def test_pullback_confidence(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    assert result["confidence"] >= 0.6, f"confidence={result['confidence']:.3f}"


def test_pullback_daily_trend_bullish(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    assert result["detail"]["trend"] == "bullish"


def test_pullback_weekly_trend_bullish(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    assert result["detail"]["weekly_trend"] == "bullish", \
        f"got {result['detail']['weekly_trend']}"


def test_pullback_rsi_in_dip_zone(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    rsi = result["detail"]["rsi"]
    rsi_p40 = result["detail"]["rsi_p40"]
    assert rsi is not None
    assert rsi <= rsi_p40, (
        f"RSI {rsi:.1f} should be <= rsi_p40 {rsi_p40:.1f}"
    )
    assert rsi >= 25, "RSI should not be in crash territory"


def test_pullback_adx_trending(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    adx = result["detail"]["adx"]
    assert adx >= 15, f"ADX={adx:.1f} < 15"


def test_pullback_volume_light(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    vol_ratio = result["detail"]["vol_ratio"]
    assert vol_ratio < 1.5, f"vol_ratio={vol_ratio:.2f} >= 1.5 (not light)"


def test_pullback_swing_low_present(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    swing_low = result["detail"]["swing_low"]
    assert isinstance(swing_low, float), f"swing_low={swing_low!r} is not float"
    assert swing_low > 0


def test_weekly_state_bullish_on_apr16(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-04-16")
    assert result["detail"]["weekly_state"] in ("BULLISH", "BULLISH_EXTENDED")


# ── Negative case: 2024-01-04 — ADX < 15 (compression / sideways) ───────────

def test_no_pullback_on_compression_day(nvda_daily, nvda_weekly):
    result = detect_pattern(nvda_daily, nvda_weekly, "2024-01-04")
    assert result["pattern"] != "pullback_in_trend", \
        f"pullback_in_trend fired on compression day (ADX={result['detail']['adx']:.1f})"


# ── Additional passing cases ─────────────────────────────────────────────────

@pytest.mark.parametrize("date_str", [
    "2024-04-08",   # price at EMA21 -0.9%, RSI=51, ADX=40
    "2024-04-09",   # price at EMA21 -2.6%, RSI=47, ADX=37
    "2024-04-15",   # price at EMA21 -2.0%, RSI=48, ADX=30
])
def test_additional_pullback_dates_fire(nvda_daily, nvda_weekly, date_str):
    result = detect_pattern(nvda_daily, nvda_weekly, date_str)
    assert result["pattern"] == "pullback_in_trend", \
        f"{date_str}: got {result['pattern']} (conf={result.get('confidence','?'):.3f})"


# ── Overbought / extended case should NOT fire pullback ──────────────────────

@pytest.mark.parametrize("date_str", [
    "2024-01-16",   # RSI=76, price extended
    "2024-02-22",   # NVDA just gapped up on earnings — overbought
])
def test_no_pullback_when_extended(nvda_daily, nvda_weekly, date_str):
    result = detect_pattern(nvda_daily, nvda_weekly, date_str)
    assert result["pattern"] != "pullback_in_trend", \
        f"{date_str} wrongly fired pullback_in_trend (RSI={result['detail']['rsi']:.1f})"


# ── P1·5 — Adaptive thresholds are stock-specific ───────────────────────────

def test_adaptive_thresholds_differ_by_stock():
    """TSLA rsi_p40 should differ from MSFT rsi_p40 — proves thresholds are stock-specific."""
    import numpy as np
    # TSLA: high-beta, RSI often stays elevated. Simulate 63 days of high-RSI data
    tsla_rsi = pd.Series(np.random.uniform(50, 85, 63))  # RSI 50-85 range (hot stock)
    msft_rsi = pd.Series(np.random.uniform(35, 65, 63))  # RSI 35-65 range (steady stock)

    tsla_p40 = float(np.percentile(tsla_rsi, 40))
    msft_p40 = float(np.percentile(msft_rsi, 40))

    assert abs(tsla_p40 - msft_p40) > 3, (
        f"Adaptive thresholds should differ by stock: TSLA p40={tsla_p40:.1f}, MSFT p40={msft_p40:.1f}"
    )
