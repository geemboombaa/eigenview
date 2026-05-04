"""Verify score_technical() detail includes all fields the API contract requires.

These tests will FAIL until score_technical() is updated to include
weekly_state and rsi_p40 in its detail dict.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _make_df(n: int = 120) -> pd.DataFrame:
    """Minimal price DataFrame with DatetimeIndex."""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 400.0 + np.cumsum(np.random.default_rng(42).normal(0, 2, n))
    vol = np.random.default_rng(42).integers(1_000_000, 5_000_000, n).astype(float)
    df = pd.DataFrame({
        "open":   close * 0.999,
        "high":   close * 1.005,
        "low":    close * 0.995,
        "close":  close,
        "volume": vol,
    }, index=dates)
    return df


def test_score_technical_has_weekly_state():
    from eigenview.factors.technical import score_technical
    df = _make_df()
    result = score_technical(df, "TEST")
    assert "weekly_state" in result.detail, (
        "score_technical detail missing 'weekly_state' — add it alongside weekly_trend"
    )


def test_score_technical_has_rsi_p40():
    from eigenview.factors.technical import score_technical
    df = _make_df()
    result = score_technical(df, "TEST")
    assert "rsi_p40" in result.detail, (
        "score_technical detail missing 'rsi_p40' — expose rolling RSI percentile"
    )
