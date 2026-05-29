"""Pure scoring logic for the macro regime gate — real computed inputs, no DB, no mocks.

The NO DATA path is the bug under fix: an all-NULL macro_daily row must NOT score as
a confident RED 0/10 — it must return regime 'NO DATA'.
"""
from __future__ import annotations

from eigenview.factors.macro_regime import score_macro_row


def test_all_none_is_no_data_not_red():
    r = score_macro_row(dix=None, gex_index=None, vix_m1=None, vix_contango_pct=None)
    assert r.label == "NO DATA", f"all-null macro must be NO DATA, got {r.label!r}"
    assert r.firing is False


def test_full_bullish_is_green_10():
    # gex>0 (+3), contango>0 (+2), dix>0.43 (+3), vix<20 (+2) = 10
    r = score_macro_row(dix=0.46, gex_index=1.2, vix_m1=15.3, vix_contango_pct=21.8)
    assert r.detail["score"] == 10
    assert r.label == "GREEN"
    assert r.firing is True


def test_partial_data_scores_not_no_data():
    # Only VIX present (m1<20 +2, contango>0 +2) = 4 → YELLOW, NOT NO DATA
    r = score_macro_row(dix=None, gex_index=None, vix_m1=15.0, vix_contango_pct=10.0)
    assert r.label != "NO DATA", "partial real data must score, not NO DATA"
    assert r.detail["score"] == 4
    assert r.label == "YELLOW"


def test_bearish_present_is_red_not_no_data():
    # negative gex, backwardation, low dix, high vix → 0 but data IS present → RED
    r = score_macro_row(dix=0.30, gex_index=-2.0, vix_m1=28.0, vix_contango_pct=-5.0)
    assert r.detail["score"] == 0
    assert r.label == "RED"
    assert r.firing is False


def test_score_is_derived_not_hardcoded():
    # dix only above threshold (+3), nothing else
    r = score_macro_row(dix=0.50, gex_index=None, vix_m1=None, vix_contango_pct=None)
    assert r.detail["score"] == 3
    assert r.label == "YELLOW"  # 3 >= red_threshold(3) but < green(7)
