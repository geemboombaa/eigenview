from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from eigenview.factors.technical import score_technical


def make_df(n: int = 90, trend: str = "up", vol_spike: bool = False) -> pd.DataFrame:
    np.random.seed(42)
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]
    closes = np.linspace(100, 130 if trend == "up" else 70, n) + np.random.randn(n) * 0.5
    volumes = np.full(n, 1_000_000, dtype=float)
    if vol_spike:
        volumes[-1] = 2_000_000.0
    return pd.DataFrame(
        {
            "open": closes * 0.99,
            "high": closes * 1.01,
            "low": closes * 0.98,
            "close": closes,
            "volume": volumes,
        },
        index=pd.DatetimeIndex(dates),
    )


def test_breakout_fires() -> None:
    df = make_df(n=90, trend="up", vol_spike=True)
    closes = df["close"].values.copy()
    closes[-1] = closes[-20:-1].max() + 5.0
    df["close"] = closes
    df["high"] = df["close"] * 1.01

    result = score_technical(df)
    assert result.firing is True
    assert result.label == "breakout"


def test_pullback_fires() -> None:
    n = 100
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]
    # 80-bar uptrend then 20 bars flat oscillation → EMA_21>EMA_50, RSI ~48
    base = np.linspace(100, 140, 80)
    flat = 140 + np.array([1, -1, 1, -1, 1, -1, 1, -1, 1, -1,
                            1, -1, 1, -1, 1, -1, 1, -1, 1, -1], dtype=float)
    closes = np.concatenate([base, flat])
    df = pd.DataFrame(
        {
            "open": closes * 0.995,
            "high": closes * 1.005,
            "low": closes * 0.995,
            "close": closes,
            "volume": np.full(n, 1_000_000, dtype=float),
        },
        index=pd.DatetimeIndex(dates),
    )
    result = score_technical(df)
    assert result.firing is True
    assert result.label == "pullback_in_trend"


def test_no_pattern() -> None:
    np.random.seed(7)
    n = 90
    dates = [date.today() - timedelta(days=n - i) for i in range(n)]
    closes = 100 + np.random.randn(n) * 0.3
    df = pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": closes * 1.001,
            "low": closes * 0.999,
            "close": closes,
            "volume": np.full(n, 1_000_000, dtype=float),
        },
        index=pd.DatetimeIndex(dates),
    )
    result = score_technical(df)
    assert result.firing is False


def test_insufficient_data() -> None:
    df = make_df(n=10)
    result = score_technical(df)
    assert result.firing is False
    assert result.label == "NO DATA"
    assert result.factor_id == "technical"


def test_bearish_trend_blocks() -> None:
    df = make_df(n=90, trend="down", vol_spike=True)
    closes = df["close"].values.copy()
    closes[-1] = closes[-20:-1].max() + 5.0
    df["close"] = closes
    df["high"] = df["close"] * 1.01

    result = score_technical(df)
    assert result.firing is False
