"""
Spec compliance tests — one test per GIVEN/THEN AC from .boss/spec-factor-modules.md
Covers behaviors not yet in baseline test files.
Requirement: make use of existing implementations; patch gaps, not rewrites.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import MacroDaily
from eigenview.factors.base import FactorResult
from eigenview.factors.flow import score_flow
from eigenview.factors.gex import score_gex
from eigenview.synthesis.gate import (
    SHORT_SETUP_PATTERNS,
    TickerScorecard,
    entry_zone,
    stop_level,
    tier_score,
)


# ── Shared mock types ─────────────────────────────────────────────────────────

@dataclass
class MockChain:
    strike: float
    call_put: str
    volume: int
    oi: int
    gamma: float
    bid: float = 5.0
    ask: float = 5.2
    iv: float = 0.3
    delta: float = 0.5
    expiry: date = field(default_factory=lambda: date.today() + timedelta(days=30))
    snapshot_date: date = field(default_factory=date.today)


def _call(strike: float, gamma: float, oi: int = 1000, expiry_days: int = 30) -> MockChain:
    return MockChain(strike=strike, call_put="C", volume=100, oi=oi, gamma=gamma,
                     expiry=date.today() + timedelta(days=expiry_days))


def _put(strike: float, gamma: float, oi: int = 1000, expiry_days: int = 30) -> MockChain:
    return MockChain(strike=strike, call_put="P", volume=100, oi=oi, gamma=gamma,
                     expiry=date.today() + timedelta(days=expiry_days))


def _fc(call_put: str, bid: float, ask: float, volume: int, oi: int) -> MockChain:
    """Flow chain — uses same MockChain with bid/ask."""
    return MockChain(strike=600.0, call_put=call_put, volume=volume, oi=oi,
                     gamma=0.001, bid=bid, ask=ask)


def fr(factor_id: str, firing: bool, strength: float = 0.5, label: str = "ok",
       detail: dict | None = None) -> FactorResult:
    return FactorResult(factor_id=factor_id, firing=firing, strength=strength,
                        label=label, detail=detail or {})


def make_sc(
    ta: bool = True, gex: bool = True, flow: bool = True,
    dormant: bool = True, sentiment: bool = True,
    ta_label: str = "breakout",
    flow_strength: float = 0.9,
    dormant_strength: float = 0.7,
    swing_low: float = 480.0,
    swing_high: float = 520.0,
) -> TickerScorecard:
    return TickerScorecard(
        ticker="NVDA",
        macro=fr("macro_regime", True, 0.8, "GREEN"),
        technical=fr("technical", ta, 0.8, ta_label,
                     {"swing_low": swing_low, "swing_high": swing_high}),
        gex=fr("gex", gex, 0.7, "short_gamma"),
        flow=fr("flow", flow, flow_strength, "calls"),
        dormant=fr("dormant", dormant, dormant_strength, "ACTIVE"),
        sentiment=fr("sentiment", sentiment, 0.6, "bullish"),
        spot_price=500.0,
    )


SPOT = 600.0


# ── REQ-GEX-4 — Gamma flip via linear interpolation ──────────────────────────

def test_gex4_gamma_flip_between_sign_change_strikes():
    """Gamma flip is interpolated between the two strikes where net GEX crosses zero."""
    # call at 590 → positive net GEX; put at 610 → negative net GEX
    # flip must be between 590 and 610
    chains = [
        _call(590, gamma=0.0001, oi=5000),
        _put(610, gamma=0.0001, oi=6000),
    ]
    result = score_gex(chains, SPOT)
    gf = result.detail.get("gamma_flip")
    assert gf is not None, "gamma_flip must be returned"
    assert 590 < gf < 610, f"gamma_flip {gf} must be between sign-change strikes 590 and 610"


def test_gex4_gamma_flip_nearest_strike_when_no_sign_change():
    """gamma_flip returns the nearest-to-zero-net-GEX strike when no sign change exists.
    When dealers are uniformly positioned, returns the closest potential flip point."""
    # All calls → net_gex always positive → no zero crossing → returns nearest to zero
    chains = [
        _call(580, gamma=0.005, oi=1000),
        _call(600, gamma=0.005, oi=1000),
        _call(620, gamma=0.005, oi=1000),
    ]
    result = score_gex(chains, SPOT)
    gf = result.detail.get("gamma_flip")
    assert gf is not None, "gamma_flip must always be a price level"
    assert gf in (580, 600, 620), f"gamma_flip {gf} must be one of the available strikes"


# ── REQ-GEX-5 — Expiry bucketing ─────────────────────────────────────────────

def test_gex5_gex_by_expiry_key_present():
    """result.detail must contain 'gex_by_expiry' dict."""
    chains = [_call(620, gamma=0.005, oi=1000, expiry_days=20)]
    result = score_gex(chains, SPOT)
    assert "gex_by_expiry" in result.detail
    assert isinstance(result.detail["gex_by_expiry"], dict)


def test_gex5_expiry_bucket_0dte():
    chains = [_call(620, gamma=0.005, oi=1000, expiry_days=0)]
    result = score_gex(chains, SPOT)
    assert "0dte" in result.detail["gex_by_expiry"]


def test_gex5_expiry_bucket_weekly():
    chains = [_call(620, gamma=0.005, oi=1000, expiry_days=5)]
    result = score_gex(chains, SPOT)
    assert "weekly" in result.detail["gex_by_expiry"]


def test_gex5_expiry_bucket_monthly():
    chains = [_call(620, gamma=0.005, oi=1000, expiry_days=20)]
    result = score_gex(chains, SPOT)
    assert "monthly" in result.detail["gex_by_expiry"]


def test_gex5_expiry_bucket_quarterly():
    chains = [_call(620, gamma=0.005, oi=1000, expiry_days=60)]
    result = score_gex(chains, SPOT)
    assert "quarterly" in result.detail["gex_by_expiry"]


def test_gex5_only_populated_buckets_present():
    """Only buckets with contributions appear in gex_by_expiry."""
    chains = [_call(620, gamma=0.005, oi=1000, expiry_days=20)]  # monthly only
    result = score_gex(chains, SPOT)
    gbe = result.detail["gex_by_expiry"]
    valid_keys = {"0dte", "weekly", "monthly", "quarterly"}
    assert set(gbe.keys()) <= valid_keys
    assert "monthly" in gbe
    assert "weekly" not in gbe
    assert "quarterly" not in gbe


# ── REQ-GEX-6 — Gamma cluster / pinning risk ─────────────────────────────────

def test_gex6_gamma_cluster_key_present():
    """result.detail must contain 'gamma_cluster' dict."""
    chains = [_call(620, gamma=0.005), _put(580, gamma=0.005)]
    result = score_gex(chains, SPOT)
    assert "gamma_cluster" in result.detail
    gc = result.detail["gamma_cluster"]
    assert "pinning_risk" in gc
    assert "pin_strike" in gc


def test_gex6_pinning_risk_bool():
    chains = [_call(620, gamma=0.005), _put(580, gamma=0.005)]
    result = score_gex(chains, SPOT)
    assert isinstance(result.detail["gamma_cluster"]["pinning_risk"], bool)


def test_gex6_pinning_risk_true_within_1pct():
    """pinning_risk=True when spot within 1% of pin_strike."""
    # Spot=600, both strike=600 → pin_strike=600, dist=0%
    chains = [
        _call(600, gamma=0.01, oi=5000),
        _put(600, gamma=0.01, oi=5000),
    ]
    result = score_gex(chains, 600.0)
    assert result.detail["gamma_cluster"]["pinning_risk"] is True


def test_gex6_pinning_risk_false_far_from_spot():
    """pinning_risk=False when pin_strike far from spot."""
    chains = [
        _call(650, gamma=0.01, oi=5000),  # pin at 650, spot=600, dist=8.3%
        _put(550, gamma=0.005, oi=1000),
    ]
    result = score_gex(chains, 600.0)
    assert result.detail["gamma_cluster"]["pinning_risk"] is False


# ── REQ-FLOW-3 — No qualified sweeps detail completeness ─────────────────────

def test_flow3_no_flow_label():
    """Below-threshold chain → label='NO FLOW'."""
    chain = _fc("C", bid=0.5, ask=0.6, volume=10, oi=100)  # tiny premium
    result = score_flow([chain])
    assert result.firing is False
    assert result.label == "NO FLOW"


def test_flow3_no_flow_detail_all_required_fields():
    """NO FLOW detail has all spec-required keys with zero values."""
    chain = _fc("C", bid=0.5, ask=0.6, volume=10, oi=100)
    result = score_flow([chain])
    d = result.detail
    assert d["largest_sweep_usd"] == 0
    assert d["total_qualified"] == 0
    assert d["call_premium"] == 0
    assert d["put_premium"] == 0
    assert d["dominant_side"] == "none"


# ── REQ-FLOW-4 — Narrative format ────────────────────────────────────────────

def test_flow4_narrative_mentions_dominant_side():
    """Firing narrative contains dominant side name."""
    chain = _fc("C", bid=4.9, ask=5.1, volume=1600, oi=400)
    result = score_flow([chain])
    assert result.firing is True
    assert "calls" in result.narrative.lower()


def test_flow4_narrative_mentions_sweep_count():
    chain = _fc("C", bid=4.9, ask=5.1, volume=1600, oi=400)
    result = score_flow([chain])
    assert "sweep" in result.narrative.lower()


def test_flow4_infinity_ratio_when_no_puts():
    """Ratio shown as ∞ when put_premium = 0."""
    chain = _fc("C", bid=4.9, ask=5.1, volume=1600, oi=400)
    result = score_flow([chain])
    assert "∞" in result.narrative


# ── REQ-FLOW-5 — Thresholds configurable ─────────────────────────────────────

def test_flow5_strength_capped_at_one():
    """strength = min(1.0, largest / flow_strength_max_usd) — never exceeds 1.0."""
    # Giant sweep: mid=50, vol=50000 → premium=250M >> 2M max
    chain = _fc("C", bid=49.9, ask=50.1, volume=50_000, oi=1000)
    result = score_flow([chain])
    assert result.strength <= 1.0


def test_flow5_strength_proportional():
    """Smaller sweep → lower strength than larger sweep."""
    small = _fc("C", bid=4.9, ask=5.1, volume=1200, oi=240)   # 600K
    large = _fc("C", bid=4.9, ask=5.1, volume=3000, oi=400)   # 1.5M
    r_small = score_flow([small])
    r_large = score_flow([large])
    assert r_small.strength < r_large.strength


# ── REQ-MACRO-5 — Detail dict completeness ───────────────────────────────────

@pytest.mark.asyncio
async def test_macro5_all_detail_keys_present(db_session: AsyncSession) -> None:
    """Macro detail must contain: score, dix, gex_index, vix_m1, vix_contango_pct."""
    from eigenview.factors.macro_regime import score_macro_regime
    db_session.add(MacroDaily(
        id=1, date=date.today(), dix=0.45, gex_index=1.0,
        vix_m1=18.0, vix_contango_pct=0.03,
    ))
    await db_session.commit()
    result = await score_macro_regime(db_session)
    for key in ("score", "dix", "gex_index", "vix_m1", "vix_contango_pct"):
        assert key in result.detail, f"Missing key '{key}' in macro detail"


# ── REQ-MACRO-6 — Narrative format ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_macro6_narrative_contains_regime_name(db_session: AsyncSession) -> None:
    from eigenview.factors.macro_regime import score_macro_regime
    db_session.add(MacroDaily(
        id=1, date=date.today(), dix=0.50, gex_index=2.0,
        vix_m1=14.0, vix_contango_pct=0.05,
    ))
    await db_session.commit()
    result = await score_macro_regime(db_session)
    assert any(r in result.narrative for r in ("GREEN", "YELLOW", "RED")), \
        f"narrative missing regime name: {result.narrative!r}"


@pytest.mark.asyncio
async def test_macro6_narrative_contains_score_out_of_10(db_session: AsyncSession) -> None:
    from eigenview.factors.macro_regime import score_macro_regime
    db_session.add(MacroDaily(
        id=1, date=date.today(), dix=0.50, gex_index=2.0,
        vix_m1=14.0, vix_contango_pct=0.05,
    ))
    await db_session.commit()
    result = await score_macro_regime(db_session)
    assert "/10" in result.narrative, f"narrative missing '/10': {result.narrative!r}"


# ── REQ-SYNTH-4 — Tier classification ────────────────────────────────────────

def test_synth4_tier_a_all_gates_2_soft():
    sc = make_sc(ta=True, gex=True, flow=True, dormant=True, sentiment=True)
    assert tier_score(sc, macro_score=8) == "A"


def test_synth4_tier_b_both_hard_one_soft():
    sc = make_sc(ta=True, gex=True, flow=True, dormant=False, sentiment=False)
    assert tier_score(sc, macro_score=8) == "B"


def test_synth4_tier_c_one_hard_one_soft():
    sc = make_sc(ta=True, gex=False, flow=True, dormant=False, sentiment=False)
    assert tier_score(sc, macro_score=8) == "C"


def test_synth4_tier_d_strong_flow_no_hard_gates():
    sc = make_sc(ta=False, gex=False, flow=True, flow_strength=0.75,
                 dormant=False, sentiment=False)
    assert tier_score(sc, macro_score=8) == "D"


def test_synth4_tier_d_strong_dormant_no_hard_gates():
    sc = make_sc(ta=False, gex=False, flow=False,
                 dormant=True, dormant_strength=0.65, sentiment=False)
    assert tier_score(sc, macro_score=8) == "D"


def test_synth4_tier_none_nothing():
    sc = make_sc(ta=False, gex=False, flow=False, flow_strength=0.3,
                 dormant=False, dormant_strength=0.1, sentiment=False)
    assert tier_score(sc, macro_score=8) is None


# ── REQ-SYNTH-6 — Entry zone ─────────────────────────────────────────────────

def test_synth6_long_entry_low_equals_swing_low():
    sc = make_sc(ta_label="breakout", swing_low=480.0, swing_high=520.0)
    low, _ = entry_zone(sc)
    assert low == pytest.approx(480.0)


def test_synth6_long_entry_high_is_30pct_of_range():
    sc = make_sc(ta_label="breakout", swing_low=480.0, swing_high=520.0)
    _, high = entry_zone(sc)
    assert high == pytest.approx(480.0 + (520.0 - 480.0) * 0.3)


def test_synth6_short_entry_high_equals_swing_high():
    sc = make_sc(ta_label="breakdown", swing_low=480.0, swing_high=520.0)
    _, high = entry_zone(sc)
    assert high == pytest.approx(520.0)


def test_synth6_short_entry_low_is_15pct_below_high():
    sc = make_sc(ta_label="breakdown", swing_low=480.0, swing_high=520.0)
    low, _ = entry_zone(sc)
    assert low == pytest.approx(520.0 - (520.0 - 480.0) * 0.15)


# ── REQ-SYNTH-7 — Stop level ─────────────────────────────────────────────────

def test_synth7_long_stop_is_swing_low_times_098():
    sc = make_sc(ta_label="breakout", swing_low=480.0, swing_high=520.0)
    stop = stop_level(sc)
    assert stop == pytest.approx(480.0 * 0.98)


def test_synth7_short_stop_is_swing_high_times_102():
    sc = make_sc(ta_label="breakdown", swing_low=480.0, swing_high=520.0)
    stop = stop_level(sc)
    assert stop == pytest.approx(520.0 * 1.02)


# ── REQ-SYNTH-9 — Short setup pattern set ────────────────────────────────────

def test_synth9_all_spec_short_patterns_in_set():
    """Every pattern named in the spec must be in SHORT_SETUP_PATTERNS."""
    required = {
        "bearish_reversal", "breakdown", "rally_in_downtrend",
        "compression_break_down", "ema_rejection", "base_breakdown",
        "overbought_reversal", "failed_breakout",
    }
    missing = required - SHORT_SETUP_PATTERNS
    assert not missing, f"Missing short patterns: {missing}"


def test_synth9_breakdown_gives_short_entry_zone():
    """breakdown label → short entry_zone (entry_high = swing_high)."""
    sc = make_sc(ta_label="breakdown", swing_low=480.0, swing_high=520.0)
    _, high = entry_zone(sc)
    assert high == pytest.approx(520.0)


def test_synth9_breakout_gives_long_entry_zone():
    """breakout label → long entry_zone (entry_low = swing_low)."""
    sc = make_sc(ta_label="breakout", swing_low=480.0, swing_high=520.0)
    low, _ = entry_zone(sc)
    assert low == pytest.approx(480.0)
