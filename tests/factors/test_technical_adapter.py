"""Adapter-contract tests for score_technical over detect_pattern.

Real yfinance CSV series (NVDA/SPY/AAPL) — no synthetic frames. Drives the
Phase-A adapter: structural firing, confirmations-count strength, optional
gex_levels confluence kwarg.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.factors.base import FactorResult
from eigenview.factors.technical import SETUP_TAXONOMY, score_technical

FIXTURES = Path(__file__).parent.parent / "fixtures"
_CSVS = [
    ("NVDA", FIXTURES / "nvda_daily_2022_2024.csv"),
    ("SPY", FIXTURES / "spy_daily_2021_2024.csv"),
    ("AAPL", FIXTURES / "aapl_daily_2022_2024.csv"),
]
_VALID_LABELS = set(SETUP_TAXONOMY) | {"no_pattern", "NO SIGNAL", "NO DATA"}


def _load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


@pytest.fixture(scope="module")
def frames():
    return [(ticker, _load(path)) for ticker, path in _CSVS]


def _first_firing_window(df: pd.DataFrame, ticker: str):
    """Walk real end-dates, return (window_df, FactorResult) of first fire."""
    n = len(df)
    for end in range(120, n + 1, 5):
        window = df.iloc[:end]
        r = score_technical(window, ticker)
        if r.firing:
            return window, r
    return None, None


def test_gex_levels_kwarg_accepted(frames):
    """Adapter must accept optional gex_levels without error (new signature)."""
    ticker, df = frames[0]
    levels = {
        "call_wall": float(df["close"].iloc[-60:].max()),
        "put_wall": float(df["close"].iloc[-60:].min()),
        "gamma_flip": float(df["close"].iloc[-1]),
    }
    r = score_technical(df, ticker, gex_levels=levels)
    assert isinstance(r, FactorResult)
    assert r.factor_id == "technical"


def test_firing_includes_confirmations_in_detail(frames):
    """A firing result carries an objective confirmations count (1..4)."""
    found = False
    for ticker, df in frames:
        window, r = _first_firing_window(df, ticker)
        if r is None:
            continue
        found = True
        assert "confirmations" in r.detail, "firing result missing confirmations count"
        c = r.detail["confirmations"]
        assert isinstance(c, int) and 1 <= c <= 4, f"confirmations={c!r} out of [1,4]"
        assert r.strength > 0.0, "firing must have strength > 0"
        assert r.label in _VALID_LABELS, f"unknown label {r.label}"
    assert found, "no firing window across real NVDA/SPY/AAPL series"


def test_gex_confluence_raises_or_holds_strength(frames):
    """Supplying confluent gex_levels never lowers strength (strength-only boost)."""
    for ticker, df in frames:
        window, base = _first_firing_window(df, ticker)
        if base is None:
            continue
        close = float(window["close"].iloc[-1])
        is_short = base.detail.get("direction") == "short"
        # Build levels that confluence-support the fired direction.
        if is_short:
            levels = {"gamma_flip": close * 1.10, "put_wall": close * 1.001}
        else:
            levels = {"gamma_flip": close * 0.90, "call_wall": close * 0.999}
        boosted = score_technical(window, ticker, gex_levels=levels)
        assert boosted.detail.get("confirmations", 0) >= base.detail.get("confirmations", 0)
        assert boosted.strength >= base.strength
        return
    pytest.skip("no firing window across real series")


def test_detail_keys_preserved(frames):
    """Adapter preserves the legacy detail keys downstream code relies on."""
    ticker, df = frames[0]
    r = score_technical(df, ticker)
    for key in ("pattern", "confidence", "trend", "adx", "rsi"):
        assert key in r.detail, f"missing detail key {key}"
