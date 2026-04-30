from __future__ import annotations

from dataclasses import dataclass, field

from eigenview.config import settings
from eigenview.factors.base import FactorResult


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
    if macro_score < settings.macro_regime_red_threshold:
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


def setup_type(scorecard: TickerScorecard) -> str:
    if scorecard.dormant.firing and scorecard.dormant.strength >= 0.7:
        return "dormant_activation"
    if scorecard.technical.label == "breakout":
        return "breakout"
    if scorecard.technical.label == "pullback_in_trend":
        return "pullback"
    if scorecard.technical.label == "compression_break":
        return "compression"
    return "flow_driven"


def entry_zone(scorecard: TickerScorecard) -> tuple[float, float]:
    swing_low = scorecard.technical.detail.get("swing_low", scorecard.spot_price * 0.98)
    swing_high = scorecard.technical.detail.get("swing_high", scorecard.spot_price * 1.02)
    entry_low = swing_low
    entry_high = swing_low + (swing_high - swing_low) * 0.3
    return round(entry_low, 2), round(entry_high, 2)


def stop_level(scorecard: TickerScorecard) -> float:
    swing_low = scorecard.technical.detail.get("swing_low", scorecard.spot_price * 0.98)
    return round(swing_low * 0.98, 2)
