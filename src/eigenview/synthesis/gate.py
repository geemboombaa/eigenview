from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from scipy.signal import argrelextrema

from eigenview.config import settings

if TYPE_CHECKING:
    import pandas as pd
from eigenview.factors.base import FactorResult

SHORT_SETUP_PATTERNS = {
    "breakdown", "ema_rejection", "rally_short", "reversal_short",
    "failed_breakout", "bb_mr_short", "ema200_snap_short",
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
    # Macro data entirely absent → regime cannot be validated → no picks (long or short)
    if scorecard.macro.label == "NO DATA":
        return False
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
    factors = [scorecard.technical, scorecard.gex, scorecard.flow,
               scorecard.dormant, scorecard.sentiment]
    firing = [f for f in factors if f.firing]
    if not firing:
        return 1
    avg_strength = sum(f.strength for f in firing) / len(firing)
    # count_ratio: 0 when minimum 2 fire, 1 when all 5 fire
    # qualify_pick requires TA+GEX+≥2soft = min 4, so effective range 4-5
    count_ratio = max(0.0, (len(firing) - 2) / (len(factors) - 2))
    composite = avg_strength * settings.conviction_strength_weight + count_ratio * settings.conviction_count_weight
    if composite >= settings.conviction_t5_threshold:
        return 5
    if composite >= settings.conviction_t4_threshold:
        return 4
    if composite >= settings.conviction_t3_threshold:
        return 3
    if composite >= settings.conviction_t2_threshold:
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
    if scorecard.flow.firing and scorecard.flow.strength >= settings.tier_d_flow_strength:
        return "D"
    if scorecard.dormant.firing and scorecard.dormant.strength >= settings.tier_d_dormant_strength:
        return "D"
    return None


def setup_type(scorecard: TickerScorecard) -> str:
    lbl = scorecard.technical.label
    if scorecard.dormant.firing and scorecard.dormant.strength >= 0.7:
        return "dormant_activation"
    _map = {
        "pullback": "pullback",
        "breakout": "breakout",
        "ema_reclaim": "ema_reclaim",
        "reversal_long": "reversal_long",
        "rally_short": "rally_short",
        "breakdown": "breakdown",
        "ema_rejection": "ema_rejection",
        "reversal_short": "reversal_short",
        "pullback_structure": "pullback_structure",
        "flag": "flag",
        "failed_breakdown": "failed_breakdown",
        "failed_breakout": "failed_breakout",
        "bb_mr_long": "bb_mr_long",
        "bb_mr_short": "bb_mr_short",
        "ema200_snap_long": "ema200_snap_long",
        "ema200_snap_short": "ema200_snap_short",
    }
    return _map.get(lbl, "flow_driven")


def entry_zone(scorecard: TickerScorecard) -> tuple[float, float]:
    is_short = scorecard.technical.label in SHORT_SETUP_PATTERNS
    swing_low = scorecard.technical.detail.get("swing_low", scorecard.spot_price * (1 - settings.swing_fallback_pct))
    swing_high = scorecard.technical.detail.get("swing_high", scorecard.spot_price * (1 + settings.swing_fallback_pct))
    if is_short:
        entry_high = swing_high
        entry_low = swing_high - (swing_high - swing_low) * settings.entry_zone_short_frac
        return round(entry_low, 2), round(entry_high, 2)
    entry_low = swing_low
    entry_high = swing_low + (swing_high - swing_low) * settings.entry_zone_long_frac
    return round(entry_low, 2), round(entry_high, 2)


def stop_level(scorecard: TickerScorecard) -> float:
    is_short = scorecard.technical.label in SHORT_SETUP_PATTERNS
    swing_low = scorecard.technical.detail.get("swing_low", scorecard.spot_price * (1 - settings.swing_fallback_pct))
    swing_high = scorecard.technical.detail.get("swing_high", scorecard.spot_price * (1 + settings.swing_fallback_pct))
    if is_short:
        return round(swing_high * (1 + settings.stop_buffer_pct), 2)
    return round(swing_low * (1 - settings.stop_buffer_pct), 2)


def estimate_target(
    pattern: str,
    detail: dict,
    entry: float,
    stop: float,
    df: "pd.DataFrame",
) -> float | None:
    """Estimate price target for R:R computation.

    Uses pattern-specific logic:
    - Longs: nearest prior swing HIGH above entry
    - Shorts: nearest prior swing LOW below entry
    - Pattern-specific fallbacks (breakout measured move, BB midline, EMA200)

    Returns None when a target cannot be determined from available data.
    """
    is_short = pattern in SHORT_SETUP_PATTERNS
    risk = abs(entry - stop)
    if risk <= 0:
        return None

    highs = df["high"].values.astype(float) if "high" in df.columns else df["close"].values.astype(float)
    lows  = df["low"].values.astype(float)  if "low"  in df.columns else df["close"].values.astype(float)
    closes = df["close"].values.astype(float)

    if not is_short:
        # Primary: nearest swing high above entry
        hi_idx = argrelextrema(highs, np.greater, order=5)[0]
        above  = [highs[i] for i in hi_idx if highs[i] > entry * 1.005]
        if above:
            return float(min(above))
        # Breakout measured move: level + (level - recent_base)
        if pattern == "breakout" and detail.get("n_bar_high"):
            nbh = float(detail["n_bar_high"])
            base = float(np.min(closes[-20:]))
            return round(nbh + (nbh - base) * 0.5, 2)
        # BB mean reversion: upper band
        if pattern == "bb_mr_long" and detail.get("bbl"):
            bbl = float(detail["bbl"])
            bbu = detail.get("bbu")
            if bbu:
                return round(float(bbl) + (float(bbu) - bbl) * 0.5, 2)
        # EMA200 snap: target = EMA200
        if pattern == "ema200_snap_long" and detail.get("ema200"):
            return float(detail["ema200"])
        return None

    else:
        # Primary: nearest swing low below entry
        lo_idx = argrelextrema(lows, np.less, order=5)[0]
        below  = [lows[i] for i in lo_idx if lows[i] < entry * 0.995]
        if below:
            return float(max(below))
        # Breakdown measured move: level - (recent_peak - level)
        if pattern == "breakdown" and detail.get("n_bar_low"):
            nbl = float(detail["n_bar_low"])
            peak = float(np.max(closes[-20:]))
            return round(nbl - (peak - nbl) * 0.5, 2)
        # BB mean reversion: lower band
        if pattern == "bb_mr_short" and detail.get("bbu"):
            bbu = float(detail["bbu"])
            bbl = detail.get("bbl")
            if bbl:
                return round(float(bbu) - (bbu - float(bbl)) * 0.5, 2)
        # EMA200 snap: target = EMA200
        if pattern == "ema200_snap_short" and detail.get("ema200"):
            return float(detail["ema200"])
        return None
