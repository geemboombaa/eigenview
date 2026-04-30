from __future__ import annotations

from eigenview.factors.base import FactorResult
from eigenview.synthesis.gate import (
    TickerScorecard,
    conviction_score,
    qualify_pick,
    setup_type,
)


def fr(factor_id: str, firing: bool, strength: float = 0.5, label: str = "ok") -> FactorResult:
    return FactorResult(factor_id=factor_id, firing=firing, strength=strength, label=label)


def make_scorecard(
    ta: bool = True,
    gex: bool = True,
    flow: bool = True,
    dormant: bool = True,
    sentiment: bool = True,
    dormant_strength: float = 0.7,
    dormant_label: str = "ACTIVE",
) -> TickerScorecard:
    return TickerScorecard(
        ticker="NVDA",
        macro=fr("macro_regime", True, 0.8, "GREEN"),
        technical=fr("technical", ta, 0.8, "breakout"),
        gex=fr("gex", gex, 0.7, "short_gamma"),
        flow=fr("flow", flow, 0.9, "calls"),
        dormant=fr("dormant", dormant, dormant_strength, dormant_label),
        sentiment=fr("sentiment", sentiment, 0.6, "bullish"),
        spot_price=500.0,
    )


def test_qualify_all_gates_pass() -> None:
    sc = make_scorecard()
    assert qualify_pick(sc, macro_score=8) is True


def test_qualify_red_macro_blocks() -> None:
    sc = make_scorecard()
    assert qualify_pick(sc, macro_score=2) is False


def test_qualify_ta_gate_blocks() -> None:
    sc = make_scorecard(ta=False)
    assert qualify_pick(sc, macro_score=8) is False


def test_qualify_only_1_soft_fails() -> None:
    # Only flow fires; dormant and sentiment do not
    sc = make_scorecard(flow=True, dormant=False, sentiment=False)
    assert qualify_pick(sc, macro_score=8) is False


def test_conviction_score_high() -> None:
    sc = make_scorecard(dormant_strength=0.9)
    # All strengths >= 0.7 → raw = (0.8+0.7+0.9+0.9+0.6)/5 = 0.78 → 4
    result = conviction_score(sc)
    assert result in (4, 5)


def test_setup_type_priority() -> None:
    sc = make_scorecard(dormant_strength=0.8)
    assert setup_type(sc) == "dormant_activation"
