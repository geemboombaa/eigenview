from __future__ import annotations

from eigenview.factors.base import FactorResult
from eigenview.synthesis.gate import (
    TickerScorecard,
    conviction_score,
    qualify_pick,
    setup_type,
)


def _fr(factor_id: str, firing: bool, strength: float = 0.5, label: str = "ok") -> FactorResult:
    return FactorResult(factor_id=factor_id, firing=firing, strength=strength, label=label)


def _real_ticker() -> str:
    import asyncio
    from eigenview.data.universe import get_universe
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return "AAPL"
        tickers = loop.run_until_complete(get_universe("ndx100"))
        return tickers[0] if tickers else "AAPL"
    except Exception:
        return "AAPL"


def make_scorecard(
    ta: bool = True,
    gex: bool = True,
    flow: bool = True,
    dormant: bool = True,
    sentiment: bool = True,
    dormant_strength: float = 0.7,
    dormant_label: str = "ACTIVE",
) -> TickerScorecard:
    ticker = _real_ticker()
    return TickerScorecard(
        ticker=ticker,
        macro=FactorResult(factor_id="macro_regime", firing=True, strength=0.8, label="GREEN"),
        technical=FactorResult(factor_id="technical", firing=ta, strength=0.8, label="breakout"),
        gex=FactorResult(factor_id="gex", firing=gex, strength=0.7, label="short_gamma"),
        flow=FactorResult(factor_id="flow", firing=flow, strength=0.9, label="calls"),
        dormant=FactorResult(factor_id="dormant", firing=dormant, strength=dormant_strength, label=dormant_label),
        sentiment=FactorResult(factor_id="sentiment", firing=sentiment, strength=0.6, label="bullish"),
        spot_price=500.0,
    )


def test_qualify_all_gates_pass() -> None:
    sc = make_scorecard()
    assert qualify_pick(sc, macro_score=8) is True


def test_qualify_red_macro_does_not_block_long() -> None:
    # Macro is context only — it never gates pick direction (user-locked 2026-05-29).
    # A fully-gated LONG pick qualifies even when macro is RED.
    sc = make_scorecard()  # technical label "breakout" = long
    assert qualify_pick(sc, macro_score=2) is True


def test_qualify_green_macro_does_not_block_short() -> None:
    # Strong (GREEN) macro must not gate a SHORT pick.
    sc = make_scorecard()
    sc.technical = FactorResult(factor_id="technical", firing=True, strength=0.8, label="breakdown")
    assert qualify_pick(sc, macro_score=9) is True


def test_qualify_ta_gate_blocks() -> None:
    sc = make_scorecard(ta=False)
    assert qualify_pick(sc, macro_score=8) is False


def test_qualify_only_1_soft_fails() -> None:
    sc = make_scorecard(flow=True, dormant=False, sentiment=False)
    assert qualify_pick(sc, macro_score=8) is False


def test_conviction_score_high() -> None:
    sc = make_scorecard(dormant_strength=0.9)
    result = conviction_score(sc)
    assert result in (4, 5)


def test_setup_type_keeps_ta_label_with_high_dormant() -> None:
    # Dormant is its own flag — it must NOT overwrite the real TA setup name (user-locked 2026-05-29).
    # A breakdown short with high dormant stays "breakdown", not "dormant_activation".
    sc = make_scorecard(dormant_strength=1.0)
    sc.technical = FactorResult(factor_id="technical", firing=True, strength=0.8, label="breakdown")
    assert setup_type(sc) == "breakdown"


def test_qualify_gex_off_still_qualifies() -> None:
    # GEX demoted from hard gate → conviction modifier (2026-05-30). A pick with
    # TA + dormant + sentiment qualifies even when GEX does not fire.
    sc = make_scorecard(gex=False)
    assert qualify_pick(sc, macro_score=8) is True


def test_qualify_requires_dormant_and_sentiment() -> None:
    # Soft gate is now dormant AND sentiment (2 of 2). Either one missing → no pick.
    assert qualify_pick(make_scorecard(dormant=True, sentiment=False), macro_score=8) is False
    assert qualify_pick(make_scorecard(dormant=False, sentiment=True), macro_score=8) is False
    assert qualify_pick(make_scorecard(dormant=True, sentiment=True), macro_score=8) is True


def test_qualify_flow_does_not_substitute() -> None:
    # Flow is kept in code but NOT counted toward qualifying. It cannot stand in
    # for a missing dormant/sentiment.
    sc = make_scorecard(flow=True, dormant=True, sentiment=False)
    assert qualify_pick(sc, macro_score=8) is False


def test_conviction_short_gamma_bumps_over_long_gamma() -> None:
    # GEX regime modifies conviction: short_gamma (moves amplified) bumps,
    # long_gamma (pinning fights the move) trims.
    sc_short = make_scorecard(dormant_strength=0.6)
    sc_short.gex = FactorResult(factor_id="gex", firing=True, strength=0.5, label="short_gamma")
    sc_long = make_scorecard(dormant_strength=0.6)
    sc_long.gex = FactorResult(factor_id="gex", firing=True, strength=0.5, label="long_gamma")
    assert conviction_score(sc_short) > conviction_score(sc_long)


def test_qualify_absent_macro_does_not_block() -> None:
    # Macro NO DATA is not a gate — a stock pick stands on its own TA+GEX+soft factors.
    sc = TickerScorecard(
        ticker=_real_ticker(),
        macro=FactorResult.no_data("macro_regime", "no macro data in DB"),
        technical=FactorResult(factor_id="technical", firing=True, strength=0.8, label="breakdown"),
        gex=FactorResult(factor_id="gex", firing=True, strength=0.7, label="short_gamma"),
        flow=FactorResult(factor_id="flow", firing=True, strength=0.9, label="puts"),
        dormant=FactorResult(factor_id="dormant", firing=True, strength=0.7, label="ACTIVE"),
        sentiment=FactorResult(factor_id="sentiment", firing=True, strength=0.6, label="bearish"),
        spot_price=500.0,
    )
    assert qualify_pick(sc, macro_score=0) is True
