"""Real-CSV coverage tests for technical.py.

Exercises score_technical across many real-data windows. Fixtures are real
yfinance OHLCV (NVDA/SPY/AAPL, 2.5-3.5 yrs) — no synthetic frames. Walking
many real end-dates drives the full pattern / stop / target / R:R decision tree
through varied RSI/ADX/EMA/volume states.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.factors.base import FactorResult
from eigenview.factors.technical import score_technical

FIXTURES = Path(__file__).parent.parent / "fixtures"
_CSVS = [
    ("NVDA", FIXTURES / "nvda_daily_2022_2024.csv"),
    ("SPY", FIXTURES / "spy_daily_2021_2024.csv"),
    ("AAPL", FIXTURES / "aapl_daily_2022_2024.csv"),
]


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


@pytest.fixture(scope="module")
def frames():
    return [(ticker, _load(path)) for ticker, path in _CSVS]


def test_score_technical_on_full_real_series(frames):
    for ticker, df in frames:
        r = score_technical(df, ticker)
        assert isinstance(r, FactorResult)
        assert r.factor_id == "technical"
        assert 0.0 <= r.strength <= 1.0
        assert isinstance(r.label, str) and r.label


def test_score_technical_rolling_windows(frames):
    seen_labels: set[str] = set()
    calls = 0
    for ticker, df in frames:
        n = len(df)
        for end in range(120, n, 20):
            r = score_technical(df.iloc[:end], ticker)
            assert r.factor_id == "technical"
            assert 0.0 <= r.strength <= 1.0
            assert isinstance(r.firing, bool)
            seen_labels.add(r.label)
            calls += 1
    assert calls > 50, f"expected many windows, ran {calls}"
    # Real multi-year data across 3 tickers surfaces several distinct setups.
    assert len(seen_labels) >= 3, f"only saw labels: {seen_labels}"


def test_score_technical_detail_keys_present(frames):
    ticker, df = frames[0]
    r = score_technical(df, ticker)
    for key in ("pattern", "confidence", "trend", "adx", "rsi"):
        assert key in r.detail, f"missing detail key {key}"


def test_score_technical_short_window_no_fire(frames):
    ticker, df = frames[0]
    r = score_technical(df.iloc[:10], ticker)
    assert r.firing is False
