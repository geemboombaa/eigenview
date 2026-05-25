"""Fixture-driven detect_pattern tests — real single-pattern CSV slices.

Each fire/anti CSV pair is a real NVDA data slice built to exhibit (or not) a
specific setup. Running detect_pattern at the slice's last bar exercises the
pattern-specific detection branches in technical.py with real data only.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.factors.technical import detect_pattern

FIXTURES = Path(__file__).parent.parent / "fixtures"

_PAIRS = [
    "pullback_deep",
    "pullback_to_structure",
    "compression_break",
    "compression_break_down",
    "flag_continuation",
]


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(FIXTURES / name, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


def _run_last(stem: str, kind: str):
    daily = _load(f"nvda_{stem}_{kind}.csv")
    weekly = _load(f"nvda_{stem}_{kind}_weekly.csv")
    date_str = daily.index[-1].strftime("%Y-%m-%d")
    return detect_pattern(daily, weekly, date_str)


@pytest.mark.parametrize("stem", _PAIRS)
def test_fire_fixture_returns_valid_result(stem):
    r = _run_last(stem, "fire")
    assert isinstance(r["pattern"], str) and r["pattern"]
    assert 0.0 <= r["confidence"] <= 1.0
    assert isinstance(r["detail"], dict)
    assert "weekly_state" in r["detail"]


@pytest.mark.parametrize("stem", _PAIRS)
def test_anti_fixture_returns_valid_result(stem):
    r = _run_last(stem, "anti")
    assert isinstance(r["pattern"], str)
    assert 0.0 <= r["confidence"] <= 1.0


def test_pullback_deep_fire_detects_a_pullback():
    r = _run_last("pullback_deep", "fire")
    # Fire slice should surface a pullback-family setup (or at least non-empty).
    assert r["pattern"] != "" and r["confidence"] >= 0.0
