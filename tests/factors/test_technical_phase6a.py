"""Phase 6A tests for detect_pattern(): P6.1-P6.5 setups.

Fixtures: real NVDA OHLCV data (daily + weekly CSVs).
Each setup has:
  - a fire case that asserts pattern == expected setup
  - an anti case that asserts pattern != expected setup
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.factors.technical import detect_pattern

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ─── Fixture loaders ──────────────────────────────────────────────────────────

def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(FIXTURES / name, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


@pytest.fixture(scope="module")
def p61_fire_daily():
    return load("nvda_pullback_deep_fire.csv")


@pytest.fixture(scope="module")
def p61_fire_weekly():
    return load("nvda_pullback_deep_fire_weekly.csv")


@pytest.fixture(scope="module")
def p61_anti_daily():
    return load("nvda_pullback_deep_anti.csv")


@pytest.fixture(scope="module")
def p61_anti_weekly():
    return load("nvda_pullback_deep_anti_weekly.csv")


@pytest.fixture(scope="module")
def p62_fire_daily():
    return load("nvda_pullback_to_structure_fire.csv")


@pytest.fixture(scope="module")
def p62_fire_weekly():
    return load("nvda_pullback_to_structure_fire_weekly.csv")


@pytest.fixture(scope="module")
def p62_anti_daily():
    return load("nvda_pullback_to_structure_anti.csv")


@pytest.fixture(scope="module")
def p62_anti_weekly():
    return load("nvda_pullback_to_structure_anti_weekly.csv")


@pytest.fixture(scope="module")
def p63_fire_daily():
    return load("nvda_flag_continuation_fire.csv")


@pytest.fixture(scope="module")
def p63_fire_weekly():
    return load("nvda_flag_continuation_fire_weekly.csv")


@pytest.fixture(scope="module")
def p63_anti_daily():
    return load("nvda_flag_continuation_anti.csv")


@pytest.fixture(scope="module")
def p63_anti_weekly():
    return load("nvda_flag_continuation_anti_weekly.csv")


@pytest.fixture(scope="module")
def p64_fire_daily():
    return load("nvda_compression_break_fire.csv")


@pytest.fixture(scope="module")
def p64_fire_weekly():
    return load("nvda_compression_break_fire_weekly.csv")


@pytest.fixture(scope="module")
def p64_anti_daily():
    return load("nvda_compression_break_anti.csv")


@pytest.fixture(scope="module")
def p64_anti_weekly():
    return load("nvda_compression_break_anti_weekly.csv")


@pytest.fixture(scope="module")
def p65_fire_daily():
    return load("nvda_compression_break_down_fire.csv")


@pytest.fixture(scope="module")
def p65_fire_weekly():
    return load("nvda_compression_break_down_fire_weekly.csv")


@pytest.fixture(scope="module")
def p65_anti_daily():
    return load("nvda_compression_break_down_anti.csv")


@pytest.fixture(scope="module")
def p65_anti_weekly():
    return load("nvda_compression_break_down_anti_weekly.csv")


# ─── P6.1 pullback_deep ───────────────────────────────────────────────────────

class TestPullbackDeep:

    def test_fire_pattern(self, p61_fire_daily, p61_fire_weekly):
        r = detect_pattern(p61_fire_daily, p61_fire_weekly, "2023-12-04")
        assert r["pattern"] == "pullback_deep", f"got {r['pattern']}"

    def test_fire_confidence(self, p61_fire_daily, p61_fire_weekly):
        r = detect_pattern(p61_fire_daily, p61_fire_weekly, "2023-12-04")
        assert r["confidence"] >= 0.6, f"confidence={r['confidence']:.3f}"

    def test_fire_trend_bullish(self, p61_fire_daily, p61_fire_weekly):
        r = detect_pattern(p61_fire_daily, p61_fire_weekly, "2023-12-04")
        assert r["detail"]["trend"] == "bullish"

    def test_fire_weekly_bullish(self, p61_fire_daily, p61_fire_weekly):
        r = detect_pattern(p61_fire_daily, p61_fire_weekly, "2023-12-04")
        assert r["detail"]["weekly_state"] in ("BULLISH", "BULLISH_EXTENDED"), \
            f"got {r['detail']['weekly_state']}"

    def test_fire_rsi_in_dip_zone(self, p61_fire_daily, p61_fire_weekly):
        r = detect_pattern(p61_fire_daily, p61_fire_weekly, "2023-12-04")
        rsi = r["detail"]["rsi"]
        rsi_p25 = r["detail"].get("rsi_p25")
        rsi_p50 = r["detail"].get("rsi_p50")
        assert rsi is not None
        if rsi_p25 is not None:
            assert rsi >= rsi_p25, f"RSI {rsi:.1f} < rsi_p25 {rsi_p25:.1f}"
        if rsi_p50 is not None:
            assert rsi <= rsi_p50, f"RSI {rsi:.1f} > rsi_p50 {rsi_p50:.1f}"

    def test_fire_swing_low_present(self, p61_fire_daily, p61_fire_weekly):
        r = detect_pattern(p61_fire_daily, p61_fire_weekly, "2023-12-04")
        sw = r["detail"]["swing_low"]
        assert isinstance(sw, (float, int)) or sw is not None

    def test_anti_does_not_fire(self, p61_anti_daily, p61_anti_weekly):
        r = detect_pattern(p61_anti_daily, p61_anti_weekly, "2024-01-16")
        assert r["pattern"] != "pullback_deep", \
            f"pullback_deep wrongly fired on anti case (date 2024-01-16)"


# ─── P6.2 pullback_to_structure ───────────────────────────────────────────────

class TestPullbackToStructure:

    def test_fire_pattern(self, p62_fire_daily, p62_fire_weekly):
        r = detect_pattern(p62_fire_daily, p62_fire_weekly, "2023-02-28")
        assert r["pattern"] == "pullback_to_structure", f"got {r['pattern']}"

    def test_fire_confidence(self, p62_fire_daily, p62_fire_weekly):
        r = detect_pattern(p62_fire_daily, p62_fire_weekly, "2023-02-28")
        assert r["confidence"] >= 0.6, f"confidence={r['confidence']:.3f}"

    def test_fire_prior_swing_high_in_detail(self, p62_fire_daily, p62_fire_weekly):
        r = detect_pattern(p62_fire_daily, p62_fire_weekly, "2023-02-28")
        assert "prior_swing_high" in r["detail"], "prior_swing_high missing from detail"
        assert r["detail"]["prior_swing_high"] > 0

    def test_fire_trend_bullish(self, p62_fire_daily, p62_fire_weekly):
        r = detect_pattern(p62_fire_daily, p62_fire_weekly, "2023-02-28")
        assert r["detail"]["trend"] == "bullish"

    def test_fire_weekly_bullish(self, p62_fire_daily, p62_fire_weekly):
        r = detect_pattern(p62_fire_daily, p62_fire_weekly, "2023-02-28")
        assert r["detail"]["weekly_state"] in ("BULLISH", "BULLISH_EXTENDED")

    def test_anti_does_not_fire(self, p62_anti_daily, p62_anti_weekly):
        r = detect_pattern(p62_anti_daily, p62_anti_weekly, "2023-06-15")
        assert r["pattern"] != "pullback_to_structure", \
            f"pullback_to_structure wrongly fired on anti case"


# ─── P6.3 flag_continuation ───────────────────────────────────────────────────

class TestFlagContinuation:

    def test_fire_pattern(self, p63_fire_daily, p63_fire_weekly):
        r = detect_pattern(p63_fire_daily, p63_fire_weekly, "2023-03-06")
        assert r["pattern"] == "flag_continuation", f"got {r['pattern']}"

    def test_fire_confidence(self, p63_fire_daily, p63_fire_weekly):
        r = detect_pattern(p63_fire_daily, p63_fire_weekly, "2023-03-06")
        assert r["confidence"] >= 0.65, f"confidence={r['confidence']:.3f}"

    def test_fire_impulse_in_detail(self, p63_fire_daily, p63_fire_weekly):
        r = detect_pattern(p63_fire_daily, p63_fire_weekly, "2023-03-06")
        assert "impulse_pct" in r["detail"], "impulse_pct missing from detail"
        assert r["detail"]["impulse_pct"] > 5.0, \
            f"impulse_pct={r['detail']['impulse_pct']:.1f}% < 5%"

    def test_fire_weekly_not_bearish_strong(self, p63_fire_daily, p63_fire_weekly):
        r = detect_pattern(p63_fire_daily, p63_fire_weekly, "2023-03-06")
        assert r["detail"]["weekly_state"] != "BEARISH_STRONG"

    def test_anti_does_not_fire(self, p63_anti_daily, p63_anti_weekly):
        r = detect_pattern(p63_anti_daily, p63_anti_weekly, "2022-06-30")
        assert r["pattern"] != "flag_continuation", \
            f"flag_continuation wrongly fired on anti case (2022-06-30 downtrend)"


# ─── P6.4 compression_break ───────────────────────────────────────────────────

class TestCompressionBreak:

    def test_fire_pattern(self, p64_fire_daily, p64_fire_weekly):
        r = detect_pattern(p64_fire_daily, p64_fire_weekly)
        assert r["pattern"] == "compression_break", f"got {r['pattern']}"

    def test_fire_confidence(self, p64_fire_daily, p64_fire_weekly):
        r = detect_pattern(p64_fire_daily, p64_fire_weekly)
        assert r["confidence"] >= 0.70, f"confidence={r['confidence']:.3f}"

    def test_fire_bbu_in_detail(self, p64_fire_daily, p64_fire_weekly):
        r = detect_pattern(p64_fire_daily, p64_fire_weekly)
        assert "bbu" in r["detail"], "bbu missing from detail"
        assert r["detail"]["bbu"] > 0

    def test_fire_vol_surge(self, p64_fire_daily, p64_fire_weekly):
        r = detect_pattern(p64_fire_daily, p64_fire_weekly)
        vol_ratio = r["detail"]["vol_ratio"]
        assert vol_ratio > 1.5, f"vol_ratio={vol_ratio:.2f} < 1.5 — not a surge"

    def test_anti_does_not_fire(self, p64_anti_daily, p64_anti_weekly):
        r = detect_pattern(p64_anti_daily, p64_anti_weekly, "2023-05-25")
        assert r["pattern"] != "compression_break", \
            f"compression_break wrongly fired on anti case"


# ─── P6.5 compression_break_down ─────────────────────────────────────────────

class TestCompressionBreakDown:

    def test_fire_pattern(self, p65_fire_daily, p65_fire_weekly):
        r = detect_pattern(p65_fire_daily, p65_fire_weekly)
        assert r["pattern"] == "compression_break_down", f"got {r['pattern']}"

    def test_fire_confidence(self, p65_fire_daily, p65_fire_weekly):
        r = detect_pattern(p65_fire_daily, p65_fire_weekly)
        assert r["confidence"] >= 0.70, f"confidence={r['confidence']:.3f}"

    def test_fire_bbl_in_detail(self, p65_fire_daily, p65_fire_weekly):
        r = detect_pattern(p65_fire_daily, p65_fire_weekly)
        assert "bbl" in r["detail"], "bbl missing from detail"
        assert r["detail"]["bbl"] > 0

    def test_fire_vol_surge(self, p65_fire_daily, p65_fire_weekly):
        r = detect_pattern(p65_fire_daily, p65_fire_weekly)
        vol_ratio = r["detail"]["vol_ratio"]
        assert vol_ratio > 1.5, f"vol_ratio={vol_ratio:.2f} < 1.5"

    def test_fire_not_bullish_weekly(self, p65_fire_daily, p65_fire_weekly):
        r = detect_pattern(p65_fire_daily, p65_fire_weekly)
        assert r["detail"]["weekly_state"] not in ("BULLISH", "BULLISH_EXTENDED"), \
            f"compression_break_down fired in bullish weekly: {r['detail']['weekly_state']}"

    def test_anti_does_not_fire(self, p65_anti_daily, p65_anti_weekly):
        r = detect_pattern(p65_anti_daily, p65_anti_weekly, "2024-06-01")
        assert r["pattern"] != "compression_break_down", \
            f"compression_break_down wrongly fired on anti case (2024-06-01 strong bull)"
