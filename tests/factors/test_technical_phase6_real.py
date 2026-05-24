"""Real OHLCV → all 21-setup pattern contract tests — no synthetic data."""
from __future__ import annotations

import pytest

from eigenview.data.prices import fetch_prices
from eigenview.factors.base import FactorResult
from eigenview.factors.technical import score_technical

KNOWN_LABELS = {
    "pullback_in_trend", "pullback_deep", "pullback_to_structure",
    "flag_continuation", "rally_in_downtrend",
    "breakout", "breakdown", "compression_break", "compression_break_down",
    "base_breakout", "base_breakdown", "ema_reclaim", "ema_rejection",
    "bos_bullish", "bos_bearish",
    "bullish_reversal", "bearish_reversal", "overbought_reversal",
    "oversold_bounce", "failed_breakdown", "failed_breakout",
    "choch_bullish", "choch_bearish",
    "bb_mean_reversion_long", "bb_mean_reversion_short",
    "ema200_snap_long", "ema200_snap_short",
    # Internal labels used when no setup fires
    "no_pattern", "NO SIGNAL", "NO DATA",
}


@pytest.mark.asyncio
async def test_score_technical_label_is_known_value():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    assert result.label in KNOWN_LABELS, (
        f"Unexpected label '{result.label}' — must be a recognised setup name"
    )


@pytest.mark.asyncio
async def test_score_technical_firing_true_means_strength_above_zero():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    if result.firing:
        assert result.strength > 0.0, "firing=True must have strength > 0"


@pytest.mark.asyncio
async def test_score_technical_firing_false_label_not_empty():
    df = await fetch_prices("AAPL", "1d", 90)
    result = score_technical(df, "AAPL")
    if not result.firing:
        assert result.label in ("NO SIGNAL", "NO DATA", "no_pattern")


@pytest.mark.asyncio
async def test_score_technical_narrative_is_string():
    df = await fetch_prices("AMD", "1d", 90)
    result = score_technical(df, "AMD")
    assert isinstance(result.narrative, str)


@pytest.mark.asyncio
async def test_score_technical_detail_contains_indicators():
    df = await fetch_prices("NVDA", "1d", 90)
    result = score_technical(df, "NVDA")
    if result.firing:
        # At minimum RSI or ADX should appear in detail when firing
        indicator_keys = {"rsi", "adx", "atr", "ema21", "ema50"}
        overlap = indicator_keys.intersection(result.detail.keys())
        assert len(overlap) > 0, (
            f"firing result has no indicator detail keys. Got: {list(result.detail.keys())}"
        )


@pytest.mark.asyncio
async def test_score_technical_tsla_no_crash():
    df = await fetch_prices("TSLA", "1d", 90)
    result = score_technical(df, "TSLA")
    assert isinstance(result, FactorResult)
    assert result.label in KNOWN_LABELS


@pytest.mark.asyncio
async def test_score_technical_meta_no_crash():
    df = await fetch_prices("META", "1d", 90)
    result = score_technical(df, "META")
    assert isinstance(result, FactorResult)
    assert 0.0 <= result.strength <= 1.0
