from __future__ import annotations

from dataclasses import dataclass, field

from eigenview.config import settings
from eigenview.factors.base import FactorResult

SHORT_SETUP_PATTERNS = {
    "bearish_reversal", "breakdown", "rally_in_downtrend",
    "compression_break_down", "ema_rejection", "base_breakdown",
    "overbought_reversal", "failed_breakout",
}


@dataclass
class TickerScorecard:
    ticker: str
    macro: FactorResult
    technical: FactorResult
    gex: FactorResult
    flow: FactorResult
    dormant: FactorResult
    sentiment: FactorResult
    spot_price: float = 0.0


def qualify_pick(scorecard: TickerScorecard, macro_score: int) -> bool:
    is_short = scorecard.technical.label in SHORT_SETUP_PATTERNS
    # RED macro: no long picks (short picks still qualify)
    if macro_score < settings.macro_regime_red_threshold and not is_short:
        return False
    if not scorecard.technical.firing:
        return False
    if not scorecard.gex.firing:
        return False
    soft_firing = sum([scorecard.flow.firing, scorecard.dormant.firing, scorecard.sentiment.firing])
    return soft_firing >= 2


def conviction_score(scorecard: TickerScorecard) -> int:
    base = sum([
        scorecard.technical.strength,
        scorecard.gex.strength,
        scorecard.flow.strength,
        scorecard.dormant.strength,
        scorecard.sentiment.strength,
    ])
    raw = base / 5.0
    if raw >= 0.8:
        return 5
    if raw >= 0.6:
        return 4
    if raw >= 0.4:
        return 3
    if raw >= 0.2:
        return 2
    return 1


def tier_score(scorecard: TickerScorecard, macro_score: int) -> str | None:
    """Return tier A/B/C/D or None (not worth surfacing)."""
    if qualify_pick(scorecard, macro_score):
        return "A"
    ta = scorecard.technical.firing
    gex = scorecard.gex.firing
    soft = sum([scorecard.flow.firing, scorecard.dormant.firing, scorecard.sentiment.firing])
    # B: both hard gates + 1 soft (near miss — was 1 soft short)
    if ta and gex and soft >= 1:
        return "B"
    # C: one hard gate missing + at least 1 soft
    if (ta or gex) and soft >= 1:
        return "C"
    # D: strong unusual single signal (no hard gates needed)
    if scorecard.flow.firing and scorecard.flow.strength >= 0.7:
        return "D"
    if scorecard.dormant.firing and scorecard.dormant.strength >= 0.6:
        return "D"
    return None


def setup_type(scorecard: TickerScorecard) -> str:
    lbl = scorecard.technical.label
    if scorecard.dormant.firing and scorecard.dormant.strength >= 0.7:
        return "dormant_activation"
    _map = {
        "breakout": "breakout",
        "pullback_in_trend": "pullback",
        "compression_break": "compression",
        "ema_reclaim": "ema_reclaim",
        "base_breakout": "base_breakout",
        "oversold_bounce": "oversold_bounce",
        "failed_breakdown": "failed_breakdown",
        "bullish_reversal": "bullish_reversal",
        "breakdown": "breakdown",
        "rally_in_downtrend": "short_rally",
        "compression_break_down": "compression_short",
        "ema_rejection": "ema_rejection",
        "base_breakdown": "base_breakdown",
        "overbought_reversal": "overbought_reversal",
        "failed_breakout": "failed_breakout",
        "bearish_reversal": "bearish_reversal",
    }
    return _map.get(lbl, "flow_driven")


def entry_zone(scorecard: TickerScorecard) -> tuple[float, float]:
    is_short = scorecard.technical.label in SHORT_SETUP_PATTERNS
    swing_low = scorecard.technical.detail.get("swing_low", scorecard.spot_price * 0.98)
    swing_high = scorecard.technical.detail.get("swing_high", scorecard.spot_price * 1.02)
    if is_short:
        entry_high = swing_high
        entry_low = swing_high - (swing_high - swing_low) * 0.15
        return round(entry_low, 2), round(entry_high, 2)
    entry_low = swing_low
    entry_high = swing_low + (swing_high - swing_low) * 0.3
    return round(entry_low, 2), round(entry_high, 2)


def stop_level(scorecard: TickerScorecard) -> float:
    is_short = scorecard.technical.label in SHORT_SETUP_PATTERNS
    swing_low = scorecard.technical.detail.get("swing_low", scorecard.spot_price * 0.98)
    swing_high = scorecard.technical.detail.get("swing_high", scorecard.spot_price * 1.02)
    if is_short:
        return round(swing_high * 1.02, 2)
    return round(swing_low * 0.98, 2)
