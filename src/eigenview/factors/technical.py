from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers df.ta accessor
from scipy.signal import argrelextrema

from eigenview.config import settings
from eigenview.factors.base import FactorResult

# Empirical RSI/ADX percentile estimates for low-history tickers (<60 bars).
# Used ONLY as fallbacks when the rolling-percentile window is too short to
# compute per-ticker percentiles, mirroring the rolling-percentile design in
# CLAUDE.md's TA spec. Keys are percentile ranks; values are the estimated levels.
_RSI_FALLBACK_PCTL: dict[int, float] = {
    10: 28.0, 12: 30.0, 15: 32.0, 20: 32.0, 25: 38.0, 40: 45.0, 43: 47.0,
    55: 55.0, 60: 57.0, 62: 58.0, 65: 60.0, 80: 68.0, 85: 72.0, 88: 75.0,
    90: 78.0, 93: 80.0,
}
_ADX_FALLBACK_PCTL: dict[int, float] = {25: 15.0, 30: 17.0, 40: 20.0, 70: 25.0, 75: 30.0}


@dataclass
class WeeklyContext:
    ema8: float | None
    ema21: float | None
    adx: float | None
    rsi: float | None
    bb_squeeze: bool


def _compute_weekly_context(df: pd.DataFrame) -> WeeklyContext:
    """Resample daily prices to weekly, compute EMA 8/21 + ADX + RSI + BB."""
    df_indexed = df.copy()
    if not isinstance(df_indexed.index, pd.DatetimeIndex):
        # Try to set date index if 'date' column exists
        if 'date' in df_indexed.columns:
            df_indexed = df_indexed.set_index(pd.to_datetime(df_indexed['date']))
        else:
            return WeeklyContext(None, None, None, None, False)
    weekly = df_indexed.resample('W-FRI').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    ).dropna()
    if len(weekly) < 15:
        return WeeklyContext(None, None, None, None, False)
    weekly = weekly.copy()
    weekly.ta.ema(length=8, append=True)
    weekly.ta.ema(length=21, append=True)
    weekly.ta.adx(length=14, append=True)
    weekly.ta.rsi(length=14, append=True)
    weekly.ta.bbands(length=20, append=True)
    last = weekly.iloc[-1]
    ema8  = last.get('EMA_8')
    ema21 = last.get('EMA_21')
    adx_w = last.get('ADX_14')
    rsi_w = last.get('RSI_14')
    bbu_w = last.get('BBU_20_2.0')
    bbl_w = last.get('BBL_20_2.0')
    close_w = last['close']
    bb_squeeze = False
    if bbu_w and bbl_w and close_w and not pd.isna(bbu_w) and not pd.isna(bbl_w):
        bb_squeeze = (bbu_w - bbl_w) / close_w < 0.15
    return WeeklyContext(
        ema8=float(ema8) if ema8 is not None and not pd.isna(ema8) else None,
        ema21=float(ema21) if ema21 is not None and not pd.isna(ema21) else None,
        adx=float(adx_w) if adx_w is not None and not pd.isna(adx_w) else None,
        rsi=float(rsi_w) if rsi_w is not None and not pd.isna(rsi_w) else None,
        bb_squeeze=bb_squeeze,
    )


def _weekly_trend(wc: WeeklyContext) -> str:
    """'bullish' | 'bearish_strong' | 'bearish_weak' | 'unknown'"""
    if wc.ema8 is None or wc.ema21 is None:
        return 'unknown'
    if wc.ema8 > wc.ema21:
        return 'bullish'
    if wc.adx and wc.adx > 25:
        return 'bearish_strong'
    return 'bearish_weak'


def _vol_character(df: pd.DataFrame, n: int = 5) -> str:
    """'declining' | 'expanding' | 'neutral' based on slope of last N bars."""
    if len(df) < n + 2:
        return 'neutral'
    vols = df['volume'].iloc[-(n + 1):-1].values.astype(float)
    if len(vols) < 2:
        return 'neutral'
    x = np.arange(len(vols), dtype=float)
    slope = float(np.polyfit(x, vols, 1)[0])
    avg = float(np.mean(vols))
    if avg == 0:
        return 'neutral'
    rel = slope / avg
    if rel < -0.05:
        return 'declining'
    if rel > 0.05:
        return 'expanding'
    return 'neutral'


def _rsi_divergence(df: pd.DataFrame, lookback: int = 20) -> tuple[bool, bool]:
    """Return (bull_div, bear_div). Bull: price lower low + RSI higher low."""
    if 'RSI_14' not in df.columns or len(df) < lookback + 2:
        return False, False
    recent_price = df['close'].values[-lookback:]
    recent_rsi   = df['RSI_14'].values[-lookback:]

    p_lows, r_lows, p_highs, r_highs = [], [], [], []
    for i in range(1, len(recent_price) - 1):
        if recent_price[i] < recent_price[i-1] and recent_price[i] < recent_price[i+1]:
            p_lows.append(recent_price[i]);  r_lows.append(recent_rsi[i])
        if recent_price[i] > recent_price[i-1] and recent_price[i] > recent_price[i+1]:
            p_highs.append(recent_price[i]); r_highs.append(recent_rsi[i])

    bull_div = (len(p_lows) >= 2 and
                p_lows[-1] < p_lows[-2] and
                r_lows[-1] > r_lows[-2] and
                not np.isnan(r_lows[-1]) and not np.isnan(r_lows[-2]))
    bear_div = (len(p_highs) >= 2 and
                p_highs[-1] > p_highs[-2] and
                r_highs[-1] < r_highs[-2] and
                not np.isnan(r_highs[-1]) and not np.isnan(r_highs[-2]))
    return bull_div, bear_div


def _compute_fib_levels(df: pd.DataFrame, lookback: int = 90) -> dict:
    """Fibonacci retracement levels from recent swing high/low."""
    s = df['close'].iloc[-lookback:] if len(df) >= lookback else df['close']
    hi, lo = float(s.max()), float(s.min())
    rng = hi - lo
    if rng == 0:
        return {}
    return {
        "high": round(hi, 2), "low": round(lo, 2),
        "f236": round(hi - rng * 0.236, 2),
        "f382": round(hi - rng * 0.382, 2),
        "f500": round(hi - rng * 0.500, 2),
        "f618": round(hi - rng * 0.618, 2),
        "f786": round(hi - rng * 0.786, 2),
    }


_SHORT_PATTERNS: frozenset[str] = frozenset({
    "bearish_reversal", "breakdown", "rally_in_downtrend",
    "compression_break_down", "ema_rejection", "base_breakdown",
    "overbought_reversal", "failed_breakout",
    "bos_bearish", "choch_bearish",
    "bb_mean_reversion_short", "ema200_snap_short",
})

# Strong weekly states count toward confirmation (vs weak NEUTRAL/BEARISH_WEAK).
_STRONG_WEEKLY: frozenset[str] = frozenset({"BULLISH", "BULLISH_EXTENDED", "BEARISH_STRONG"})

# Setups whose detection IS itself a structural break (BOS/CHoCH/level break).
_STRUCTURAL_BREAK: frozenset[str] = frozenset({
    "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish",
    "breakout", "breakdown", "base_breakout", "base_breakdown",
    "failed_breakout", "failed_breakdown",
    "compression_break", "compression_break_down",
})


def _build_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV → weekly (W-FRI) for detect_pattern."""
    d = df.copy()
    if not isinstance(d.index, pd.DatetimeIndex):
        if "date" in d.columns:
            d.index = pd.to_datetime(d["date"])
        else:
            d.index = pd.to_datetime(d.index)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    return d.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()


def _gex_confluence(pattern: str, close: float, gex_levels: dict | None) -> bool:
    """True when price sits on a GEX level supporting the trade direction."""
    if not gex_levels or close <= 0:
        return False
    flip = gex_levels.get("gamma_flip")
    call_wall = gex_levels.get("call_wall")
    put_wall = gex_levels.get("put_wall")
    if pattern in _SHORT_PATTERNS:
        if flip is not None and close <= float(flip):
            return True
        if put_wall is not None and close <= float(put_wall) * 1.02:
            return True
    else:
        if flip is not None and close >= float(flip):
            return True
        if call_wall is not None and close >= float(call_wall) * 0.98:
            return True
    return False


def score_technical(
    df: pd.DataFrame, ticker: str = "", gex_levels: dict | None = None
) -> FactorResult:
    """Thin adapter over detect_pattern — the single live TA engine.

    Fires on the structural gates inside detect_pattern (no confidence floor,
    no calibration). strength = normalized count of confirmations that stacked
    (weekly alignment, structural break, GEX confluence, strong volume) and is
    used for ranking only. Optional gex_levels (call_wall/put_wall/gamma_flip)
    add a confluence confirmation but never block firing.
    """
    if df is None or len(df) < 30:
        return FactorResult.no_data("technical", "insufficient price history")

    daily = df.copy()
    if not isinstance(daily.index, pd.DatetimeIndex):
        if "date" in daily.columns:
            daily.index = pd.to_datetime(daily["date"])
        else:
            daily.index = pd.to_datetime(daily.index)

    weekly = _build_weekly(daily)
    as_of_str = pd.Timestamp(daily.index[-1]).strftime("%Y-%m-%d")

    res = detect_pattern(daily, weekly, as_of_str)
    pattern = res.get("pattern", "no_pattern")
    pdetail = res.get("detail", {}) or {}
    confidence = float(res.get("confidence", 0.0) or 0.0)

    firing = pattern not in ("no_pattern", "no_data", "NO DATA", "", None)

    close_now = float(daily["close"].iloc[-1])
    weekly_state = pdetail.get("weekly_state")
    is_short = pattern in _SHORT_PATTERNS
    direction = "short" if is_short else "long"

    gex_conf = _gex_confluence(pattern, close_now, gex_levels) if firing else False
    confirmations = 0
    if firing:
        confirmations = 1  # the structural setup itself
        if weekly_state in _STRONG_WEEKLY:
            confirmations += 1
        structure = (
            pattern in _STRUCTURAL_BREAK
            or pdetail.get("bos_bullish") or pdetail.get("bos_bearish")
            or pdetail.get("choch_bullish") or pdetail.get("choch_bearish")
        )
        if structure:
            confirmations += 1
        if gex_conf:
            confirmations += 1
        vr = pdetail.get("vol_ratio")
        if vr is not None and float(vr) >= 1.3:
            confirmations += 1
        confirmations = min(4, confirmations)

    strength = confirmations / 4.0 if firing else 0.0

    detail = {
        "pattern": pattern,
        "confidence": round(confidence, 3),
        "confirmations": confirmations,
        "direction": direction,
        "gex_confluence": gex_conf,
        "trend": pdetail.get("trend"),
        "weekly_trend": pdetail.get("weekly_trend"),
        "weekly_state": weekly_state,
        "adx": pdetail.get("adx"),
        "rsi": pdetail.get("rsi"),
        "rsi_p40": pdetail.get("rsi_p40"),
        "vol_ratio": pdetail.get("vol_ratio"),
        "swing_high": pdetail.get("swing_high"),
        "swing_low": pdetail.get("swing_low"),
    }
    for k in (
        "prior_swing_high", "n_bar_high", "n_bar_low", "bbu", "bbl",
        "ema200", "ema200_deviation_pct", "impulse_pct", "high_50d", "low_50d",
        "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish",
        "bullish_reversal", "bearish_reversal", "overbought_reversal",
        "oversold_bounce", "failed_breakdown", "failed_breakout",
        "rally_in_downtrend", "bull_divergence", "bear_divergence",
    ):
        if k in pdetail:
            detail[k] = pdetail[k]

    if not firing:
        narrative = f"No qualifying setup ({pattern}). Weekly: {weekly_state}."
    else:
        narrative = (
            f"{direction.capitalize()} {pattern.replace('_', ' ')} — "
            f"{confirmations}/4 confirmations"
            f"{' (GEX confluence)' if gex_conf else ''}. "
            f"ADX {detail['adx']}, RSI {detail['rsi']}, vol {detail['vol_ratio']}x. "
            f"Weekly: {weekly_state}."
        )

    return FactorResult(
        factor_id="technical",
        firing=firing,
        strength=strength,
        label=pattern,
        detail=detail,
        narrative=narrative,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: detect_pattern — explicit daily + weekly DataFrames
# ─────────────────────────────────────────────────────────────────────────────

_WEEKLY_STATES = ("BULLISH", "BULLISH_EXTENDED", "NEUTRAL", "BEARISH_WEAK", "BEARISH_STRONG")


def _classify_weekly_state(weekly_df: pd.DataFrame, as_of: pd.Timestamp) -> str:
    """5-state weekly trend classifier. Uses bars up to (and including) as_of."""
    wdf = weekly_df[weekly_df.index <= as_of].copy()
    if len(wdf) < 15:
        return "NEUTRAL"
    wdf.ta.ema(length=8, append=True)
    wdf.ta.ema(length=21, append=True)
    wdf.ta.adx(length=14, append=True)
    wdf.ta.rsi(length=14, append=True)
    last = wdf.iloc[-1]
    ema8  = last.get("EMA_8")
    ema21 = last.get("EMA_21")
    adx   = last.get("ADX_14")
    rsi   = last.get("RSI_14")
    if ema8 is None or ema21 is None or pd.isna(ema8) or pd.isna(ema21):
        return "NEUTRAL"
    ema8f, ema21f = float(ema8), float(ema21)
    rsi_f = float(rsi) if rsi is not None and not pd.isna(rsi) else None
    adx_f = float(adx) if adx is not None and not pd.isna(adx) else None
    if ema8f > ema21f:
        if rsi_f is not None and rsi_f > 70:
            return "BULLISH_EXTENDED"
        return "BULLISH"
    gap_pct = (ema21f - ema8f) / ema21f if ema21f > 0 else 1.0
    if gap_pct < 0.02:
        return "NEUTRAL"
    if adx_f is not None and adx_f > 25:
        return "BEARISH_STRONG"
    return "BEARISH_WEAK"


def _swing_low(closes: np.ndarray, order: int = 5) -> float | None:
    """Most recent local minimum in closes array using argrelextrema."""
    if len(closes) < order * 2 + 1:
        return None
    minima_idx = argrelextrema(closes, np.less, order=order)[0]
    if len(minima_idx) == 0:
        return None
    return float(closes[minima_idx[-1]])


def _swing_high(closes: np.ndarray, order: int = 5) -> float | None:
    """Most recent local maximum in closes array using argrelextrema."""
    if len(closes) < order * 2 + 1:
        return None
    maxima_idx = argrelextrema(closes, np.greater, order=order)[0]
    if len(maxima_idx) == 0:
        return None
    return float(closes[maxima_idx[-1]])


def detect_pattern(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    as_of_date: str | None = None,
) -> dict:
    """Detect technical pattern using explicit daily + weekly DataFrames.

    Returns a plain dict (not FactorResult) so tests can assert field by field:
      pattern, confidence, detail: {trend, weekly_trend, weekly_state,
        rsi, adx, vol_ratio, swing_low, swing_high, ...}
    """
    ddf = daily_df.copy()
    if not isinstance(ddf.index, pd.DatetimeIndex):
        ddf.index = pd.to_datetime(ddf.index)
    if ddf.index.tz is not None:
        ddf.index = ddf.index.tz_localize(None)

    as_of_ts = pd.Timestamp(as_of_date) if as_of_date else ddf.index[-1]
    ddf = ddf[ddf.index <= as_of_ts]

    _empty_detail = {
        "trend": None, "weekly_trend": None, "weekly_state": None,
        "rsi": None, "rsi_p40": None, "adx": None,
        "vol_ratio": None, "swing_low": None, "swing_high": None,
    }

    if len(ddf) < 30:
        return {"pattern": "no_pattern", "confidence": 0.0, "detail": _empty_detail}

    # Daily indicators
    ddf.ta.ema(length=21, append=True)
    ddf.ta.ema(length=50, append=True)
    ddf.ta.ema(length=200, append=True)
    ddf.ta.adx(length=14, append=True)
    ddf.ta.rsi(length=14, append=True)

    last = ddf.iloc[-1]
    ema21 = last.get("EMA_21")
    ema50 = last.get("EMA_50")
    adx   = last.get("ADX_14")
    rsi   = last.get("RSI_14")

    if any(v is None or (isinstance(v, float) and pd.isna(v)) for v in [ema21, ema50, adx]):
        return {"pattern": "no_pattern", "confidence": 0.0, "detail": _empty_detail}

    ema21f, ema50f = float(ema21), float(ema50)
    adxf = float(adx)
    rsif = float(rsi) if rsi is not None and not pd.isna(rsi) else None
    close_now = float(last["close"])

    # Volume
    vol_now = float(ddf["volume"].iloc[-1])
    vol_avg = float(ddf["volume"].iloc[-20:-1].mean()) if len(ddf) >= 21 else vol_now
    vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 1.0

    # Rolling percentile thresholds for detect_pattern (63-bar = 3 calendar months)
    # rsi_p40: upper bound — RSI must be in lower 40% of recent readings (relative dip)
    # rsi_p15_dp: oversold-crash floor — capped at 35 so strong-trend stocks don't block pullbacks
    lookback_rsi = ddf["RSI_14"].dropna().tail(63)
    if len(lookback_rsi) >= 10:
        rsi_p40    = float(np.percentile(lookback_rsi, 40))
        rsi_p15_dp = min(35.0, float(np.percentile(lookback_rsi, 15)))
    else:
        rsi_p40    = 58.0
        rsi_p15_dp = 30.0

    # ADX percentile for sideways threshold — capped at 25 to avoid over-sensitivity
    # in strong-trending regimes where even p25 can be very high (e.g. NVDA 2024 bull).
    lookback_adx = ddf["ADX_14"].dropna().tail(63)
    if len(lookback_adx) >= 10:
        adx_p25_dp = min(25.0, float(np.percentile(lookback_adx, 25)))
    else:
        adx_p25_dp = 15.0

    # Vol ratio percentile -- used by pullback, breakout, breakdown, VCP, EMA setups
    _dp_vols = ddf['volume'].dropna().tail(64).values
    if len(_dp_vols) >= 21:
        _dp_avgs = np.array([
            float(np.mean(_dp_vols[max(0, i-20):i])) if i > 0 else float(_dp_vols[0])
            for i in range(len(_dp_vols))
        ])
        _dp_ratios = np.where(_dp_avgs > 0, _dp_vols / _dp_avgs, 1.0)
        vol_p35_dp = float(np.percentile(_dp_ratios, 35))
        vol_p40_dp = float(np.percentile(_dp_ratios, 40))
        vol_p50_dp = float(np.percentile(_dp_ratios, 50))
        vol_p55_dp = float(np.percentile(_dp_ratios, 55))
        vol_p60_dp = float(np.percentile(_dp_ratios, 60))
        vol_p70_dp = float(np.percentile(_dp_ratios, 70))
        vol_p72_dp = float(np.percentile(_dp_ratios, 72))
    else:
        vol_p35_dp = 0.9
        vol_p40_dp = 0.95
        vol_p50_dp = 1.0
        vol_p55_dp = 1.1
        vol_p60_dp = 1.2
        vol_p70_dp = 1.4
        vol_p72_dp = 1.5

    # Swing levels
    closes_arr = ddf["close"].values.astype(float)
    sw_low  = _swing_low(closes_arr)
    sw_high = _swing_high(closes_arr)

    # Daily trend
    if adxf < adx_p25_dp:
        daily_trend = "sideways"
    elif ema21f > ema50f:
        daily_trend = "bullish"
    else:
        daily_trend = "bearish"

    # Weekly 5-state classifier
    weekly_state = _classify_weekly_state(weekly_df, as_of_ts)
    weekly_trend = "bullish" if weekly_state in ("BULLISH", "BULLISH_EXTENDED") else \
                   "bearish" if weekly_state in ("BEARISH_STRONG", "BEARISH_WEAK") else "neutral"

    detail = {
        "trend":        daily_trend,
        "weekly_trend": weekly_trend,
        "weekly_state": weekly_state,
        "rsi":          round(rsif, 2) if rsif is not None else None,
        "rsi_p40":      round(rsi_p40, 2),
        "adx":          round(adxf, 2),
        "vol_ratio":    vol_ratio,
        "swing_low":    sw_low,
        "swing_high":   sw_high,
    }


    # P6 setup prerequisites: RSI/ADX percentiles + BB + Squeeze (computed once)
    _rsi_full = ddf["RSI_14"].dropna().tail(63).values
    if len(_rsi_full) >= 10:
        rsi_p25_dp = float(np.percentile(_rsi_full, 25))
        rsi_p30_dp = float(np.percentile(_rsi_full, 30))
        rsi_p45_dp = float(np.percentile(_rsi_full, 45))
        rsi_p50_dp = float(np.percentile(_rsi_full, 50))
        rsi_p55_dp = float(np.percentile(_rsi_full, 55))
        rsi_p65_dp = float(np.percentile(_rsi_full, 65))
    else:
        rsi_p25_dp = 38.0
        rsi_p30_dp = 40.0
        rsi_p45_dp = 48.0
        rsi_p50_dp = 52.0
        rsi_p55_dp = 56.0
        rsi_p65_dp = 63.0

    _adx_full = ddf["ADX_14"].dropna().tail(63).values
    adx_p30_dp = float(np.percentile(_adx_full, 30)) if len(_adx_full) >= 10 else 18.0

    ddf.ta.bbands(length=20, append=True)
    _bb_last = ddf.iloc[-1]
    _bbu_key = "BBU_20_2.0_2.0" if "BBU_20_2.0_2.0" in ddf.columns else "BBU_20_2.0"
    _bbl_key = "BBL_20_2.0_2.0" if "BBL_20_2.0_2.0" in ddf.columns else "BBL_20_2.0"
    _bbu_raw = _bb_last.get(_bbu_key)
    _bbl_raw = _bb_last.get(_bbl_key)
    bbu_dp = float(_bbu_raw) if _bbu_raw is not None and not pd.isna(_bbu_raw) else None
    bbl_dp = float(_bbl_raw) if _bbl_raw is not None and not pd.isna(_bbl_raw) else None

    try:
        _sqz_dp = ta.squeeze_pro(ddf["high"], ddf["low"], ddf["close"])
        _sq_on_dp = bool(
            _sqz_dp["SQZPRO_ON_NARROW"].iloc[-1]
            or _sqz_dp["SQZPRO_ON_NORMAL"].iloc[-1]
            or _sqz_dp["SQZPRO_ON_WIDE"].iloc[-1]
        )
        _sq_off_dp = bool(_sqz_dp["SQZPRO_OFF"].iloc[-1])
        _squeeze_released_dp = _sq_off_dp and not _sq_on_dp
    except Exception:
        _sq_on_dp = False
        _sq_off_dp = False
        _squeeze_released_dp = False

    # ── P6.1 pullback_deep (before pullback_in_trend — deeper dip to EMA50) ──
    if (
        weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and daily_trend == "bullish"
        and rsif is not None
        and rsi_p25_dp <= rsif <= rsi_p50_dp
        and -0.05 <= (close_now / ema50f - 1) <= 0.01
        and vol_ratio < vol_p60_dp
        and adxf >= adx_p30_dp
    ):
        confidence = 0.65
        if vol_ratio < vol_p40_dp:
            confidence += 0.05
        if close_now >= ema50f * 0.98:
            confidence += 0.05
        confidence = round(min(1.0, confidence), 3)
        detail.update({"rsi_p25": round(rsi_p25_dp, 2), "rsi_p50": round(rsi_p50_dp, 2)})
        return {"pattern": "pullback_deep", "confidence": confidence, "detail": detail}
    # ── pullback_in_trend detection ──────────────────────────────────────────
    # Requirements:
    #   1. Daily trend bullish (EMA21>EMA50, ADX>=adx_p25)
    #   2. Weekly state BULLISH or BULLISH_EXTENDED
    #   3. RSI in adaptive dip zone (rsi_p15 ≤ rsi ≤ rsi_p40)
    #   4. Price within 4% below EMA21 (pulling back to support)
    #   5. Volume light (vol_ratio < vol_p72)
    if (
        daily_trend == "bullish"
        and weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and rsif is not None
        and rsif <= rsi_p40                 # relative dip: in lower 40% of recent RSI readings
        and rsif >= rsi_p15_dp              # adaptive floor: not crashed/oversold_bounce territory
        and close_now >= ema21f * 0.96      # within 4% of EMA21
        and close_now <= ema21f * 1.04      # not far above EMA21
        and vol_ratio < vol_p72_dp          # volume light on pullback (adaptive)
    ):
        confidence = 0.70
        if vol_ratio < vol_p35_dp:
            confidence += 0.05             # extra light = healthier pullback
        if close_now >= ema21f * 0.99:
            confidence += 0.05             # touching EMA21 (ideal entry)
        confidence = round(min(1.0, confidence), 3)
        return {"pattern": "pullback_in_trend", "confidence": confidence, "detail": detail}

    # ── P6.2 pullback_to_structure ───────────────────────────────────────────
    if (
        weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and daily_trend == "bullish"
        and rsif is not None
        and rsi_p30_dp <= rsif <= rsi_p55_dp
        and vol_ratio < vol_p60_dp
        and len(ddf) >= 60
    ):
        _highs_60 = ddf["high"].values[-60:].astype(float)
        _hi_idx = argrelextrema(_highs_60, np.greater, order=5)[0]
        if len(_hi_idx) >= 2:
            _prior_swing_hi = _highs_60[_hi_idx[-2]]
            if abs(close_now / _prior_swing_hi - 1) < 0.02:
                confidence = 0.68
                if vol_ratio < vol_p40_dp:
                    confidence += 0.05
                confidence = round(min(1.0, confidence), 3)
                detail["prior_swing_high"] = round(_prior_swing_hi, 2)
                detail.update({"rsi_p30": round(rsi_p30_dp, 2), "rsi_p55": round(rsi_p55_dp, 2)})
                return {"pattern": "pullback_to_structure", "confidence": confidence, "detail": detail}

    # ── P6.3 flag_continuation ───────────────────────────────────────────────
    if (
        weekly_state != "BEARISH_STRONG"
        and rsif is not None
        and rsi_p45_dp <= rsif <= rsi_p65_dp
        and vol_ratio < vol_p50_dp
        and _sq_on_dp
        and len(ddf) >= 12
    ):
        _impulse = (float(ddf["close"].iloc[-1]) / float(ddf["close"].iloc[-11]) - 1) * 100
        if _impulse > 5.0:
            confidence = 0.70
            if _impulse > 10.0:
                confidence += 0.05
            if vol_ratio < vol_p40_dp:
                confidence += 0.03
            confidence = round(min(1.0, confidence), 3)
            detail["impulse_pct"] = round(_impulse, 2)
            detail.update({"rsi_p45": round(rsi_p45_dp, 2), "rsi_p65": round(rsi_p65_dp, 2)})
            return {"pattern": "flag_continuation", "confidence": confidence, "detail": detail}

    # ── P6.3b bull_flag — long-only, requires weekly BULLISH ─────────────────
    if (
        weekly_state == "BULLISH"
        and rsif is not None
        and 45 <= rsif <= 65
        and vol_ratio < 1.2
        and _sq_on_dp
        and len(ddf) >= 12
    ):
        _impulse = (float(ddf["close"].iloc[-1]) / float(ddf["close"].iloc[-11]) - 1) * 100
        if _impulse > 5.0:
            confidence = 0.72
            if _impulse > 10.0:
                confidence += 0.05
            if weekly_state == "BULLISH":
                confidence += 0.03
            confidence = round(min(1.0, confidence), 3)
            detail["impulse_pct"] = round(_impulse, 2)
            detail.update({"rsi_p45": round(rsi_p45_dp, 2), "rsi_p65": round(rsi_p65_dp, 2)})
            return {"pattern": "bull_flag", "confidence": confidence, "detail": detail}

    # ── P6.4 compression_break ───────────────────────────────────────────────
    if (
        _squeeze_released_dp
        and bbu_dp is not None
        and close_now > bbu_dp
        and vol_ratio > vol_p70_dp
        and float(ddf["open"].iloc[-1]) < close_now
        and (rsif is None or rsif < 90.0)
    ):
        confidence = 0.75
        if vol_ratio > vol_p72_dp:
            confidence += 0.05
        if weekly_state in ("BULLISH", "BULLISH_EXTENDED"):
            confidence += 0.03
        if weekly_state == "BEARISH_STRONG":
            confidence -= 0.20
        confidence = round(min(1.0, max(0.0, confidence)), 3)
        detail["bbu"] = round(bbu_dp, 2)
        return {"pattern": "compression_break", "confidence": confidence, "detail": detail}

    # ── P6.5 compression_break_down ──────────────────────────────────────────
    if (
        _squeeze_released_dp
        and bbl_dp is not None
        and close_now < bbl_dp
        and vol_ratio > vol_p70_dp
        and float(ddf["open"].iloc[-1]) > close_now
        and weekly_state not in ("BULLISH", "BULLISH_EXTENDED")
    ):
        confidence = 0.73
        if vol_ratio > vol_p72_dp:
            confidence += 0.05
        if weekly_state == "BEARISH_STRONG":
            confidence += 0.05
        confidence = round(min(1.0, confidence), 3)
        detail["bbl"] = round(bbl_dp, 2)
        return {"pattern": "compression_break_down", "confidence": confidence, "detail": detail}
    # P6.6 breakout: close > N-bar swing high (scipy), level tested >=2x, vol surge
    if weekly_state != "BEARISH_STRONG" and len(ddf) >= 60:
        highs_60 = ddf["high"].values[-60:].astype(float)
        _sh_idx = argrelextrema(highs_60, np.greater, order=5)[0]
        if len(_sh_idx) > 0:
            _n_bar_high = highs_60[_sh_idx[-1]]
            _prior_approaches = int(np.sum(
                np.abs(highs_60[:_sh_idx[-1]] / _n_bar_high - 1) < 0.01
            ))
            if (
                close_now > _n_bar_high
                and vol_ratio > vol_p70_dp
                and _prior_approaches >= 1
            ):
                confidence = 0.80
                if vol_ratio > vol_p72_dp:
                    confidence += 0.05
                confidence = round(min(1.0, confidence), 3)
                detail["n_bar_high"] = round(_n_bar_high, 2)
                detail["prior_approaches"] = _prior_approaches
                return {"pattern": "breakout", "confidence": confidence, "detail": detail}

    # P6.7 breakdown: close < N-bar swing low (scipy), vol surge, weekly bearish
    if weekly_state in ("BEARISH_WEAK", "BEARISH_STRONG") and len(ddf) >= 60:
        lows_60 = ddf["low"].values[-60:].astype(float)
        _sl_idx = argrelextrema(lows_60, np.less, order=5)[0]
        if len(_sl_idx) > 0:
            _n_bar_low = lows_60[_sl_idx[-1]]
            if (
                close_now < _n_bar_low
                and vol_ratio > vol_p70_dp
            ):
                confidence = 0.78
                if weekly_state == "BEARISH_STRONG":
                    confidence += 0.05
                if vol_ratio > vol_p72_dp:
                    confidence += 0.05
                confidence = round(min(1.0, confidence), 3)
                detail["n_bar_low"] = round(_n_bar_low, 2)
                return {"pattern": "breakdown", "confidence": confidence, "detail": detail}

    # P6.8 base_breakout (VCP): tight 20-bar base near 50d high, squeeze_on, vol light, weekly bullish
    if weekly_state in ("BULLISH", "BULLISH_EXTENDED") and len(ddf) >= 50:
        _std_series = ddf["close"].rolling(20).std().dropna()
        if len(_std_series) >= 10:
            _close_std_20 = float(_std_series.iloc[-1])
            _std_p25 = float(np.percentile(_std_series.tail(63), 25))
            _high_50d = float(ddf["close"].tail(50).max())
            _near_high = (close_now / _high_50d - 1) > -0.03
            _tight_base = _close_std_20 < _std_p25
            try:
                _sqz = ta.squeeze_pro(ddf["high"], ddf["low"], ddf["close"])
                _sq_on = bool(
                    _sqz["SQZPRO_ON_NARROW"].iloc[-1]
                    or _sqz["SQZPRO_ON_NORMAL"].iloc[-1]
                    or _sqz["SQZPRO_ON_WIDE"].iloc[-1]
                )
            except Exception:
                _sq_on = False
            if _near_high and _tight_base and _sq_on and vol_ratio < vol_p40_dp:
                confidence = 0.70
                if _close_std_20 < _std_p25 * 0.75:
                    confidence += 0.05
                confidence = round(min(1.0, confidence), 3)
                detail["high_50d"] = round(_high_50d, 2)
                return {"pattern": "base_breakout", "confidence": confidence, "detail": detail}

    # P6.9 base_breakdown (short VCP): tight base near 50d low, squeeze_on, vol light, weekly bearish
    if weekly_state in ("BEARISH_WEAK", "BEARISH_STRONG") and len(ddf) >= 50:
        _std_series_b = ddf["close"].rolling(20).std().dropna()
        if len(_std_series_b) >= 10:
            _close_std_20b = float(_std_series_b.iloc[-1])
            _std_p25_b = float(np.percentile(_std_series_b.tail(63), 25))
            _low_50d = float(ddf["close"].tail(50).min())
            _near_low = (close_now / _low_50d - 1) < 0.03
            _tight_base_b = _close_std_20b < _std_p25_b
            try:
                _sqz_b = ta.squeeze_pro(ddf["high"], ddf["low"], ddf["close"])
                _sq_on_b = bool(
                    _sqz_b["SQZPRO_ON_NARROW"].iloc[-1]
                    or _sqz_b["SQZPRO_ON_NORMAL"].iloc[-1]
                    or _sqz_b["SQZPRO_ON_WIDE"].iloc[-1]
                )
            except Exception:
                _sq_on_b = False
            if _near_low and _tight_base_b and _sq_on_b and vol_ratio < vol_p40_dp:
                confidence = 0.68
                if weekly_state == "BEARISH_STRONG":
                    confidence += 0.05
                confidence = round(min(1.0, confidence), 3)
                detail["low_50d"] = round(_low_50d, 2)
                return {"pattern": "base_breakdown", "confidence": confidence, "detail": detail}

    # P6.10 ema_reclaim: yesterday close < EMA50, today > EMA50, moderate vol
    if (
        weekly_state != "BEARISH_STRONG"
        and len(ddf) >= 2
        and float(ddf["close"].iloc[-2]) < float(ddf["EMA_50"].iloc[-2])
        and close_now > ema50f
        and vol_ratio > vol_p55_dp
    ):
        confidence = 0.65
        if vol_ratio > vol_p70_dp:
            confidence += 0.05
        confidence = round(min(1.0, confidence), 3)
        return {"pattern": "ema_reclaim", "confidence": confidence, "detail": detail}

    # P6.11 ema_rejection: yesterday close > EMA50, today < EMA50, moderate vol
    if (
        weekly_state in ("BEARISH_WEAK", "BEARISH_STRONG", "NEUTRAL")
        and len(ddf) >= 2
        and float(ddf["close"].iloc[-2]) > float(ddf["EMA_50"].iloc[-2])
        and close_now < ema50f
        and vol_ratio > vol_p55_dp
    ):
        confidence = 0.63
        if weekly_state == "BEARISH_STRONG":
            confidence += 0.07
        if vol_ratio > vol_p70_dp:
            confidence += 0.05
        confidence = round(min(1.0, confidence), 3)
        return {"pattern": "ema_rejection", "confidence": confidence, "detail": detail}

    # ── P6.12–P6.15 CHoCH / BOS (smartmoneyconcepts) ───────────────────────
    # Signals are placed at historical swing indices; BrokenIndex marks confirmation.
    # A signal is "recent" if either:
    #   (a) the signal's own bar index falls in the last 60 bars, OR
    #   (b) its BrokenIndex (when the level was actually broken) is in the last 60 bars.
    # This is necessary because the SMC library places the signal at the SWING POINT
    # (which can be 10-30 bars before the break bar).
    _choch_bullish_signal = False
    _choch_bearish_signal = False
    _bos_bullish_signal   = False
    _bos_bearish_signal   = False
    if len(ddf) >= 40:
        try:
            import os as _os
            _os.environ['PYTHONUTF8'] = '1'
            import smartmoneyconcepts.smc as _smc
            _shl = _smc.swing_highs_lows(ddf, swing_length=10)
            _bc  = _smc.bos_choch(ddf, _shl, close_break=True)
            _n   = len(ddf)
            _recent_window = 60  # look back 60 bars for signal or its confirmation
            _bi  = _bc['BrokenIndex'].values  # nan or bar index (float)
            _bos_vals   = _bc['BOS'].values
            _choch_vals = _bc['CHOCH'].values
            for _iloc in range(len(_bc)):
                _bos_v   = _bos_vals[_iloc]
                _choch_v = _choch_vals[_iloc]
                # Skip if both BOS and CHOCH are nan at this position
                _bos_active   = not (isinstance(_bos_v,   float) and np.isnan(_bos_v))
                _choch_active = not (isinstance(_choch_v, float) and np.isnan(_choch_v))
                if not _bos_active and not _choch_active:
                    continue
                # Check recency: signal bar index OR BrokenIndex in last 60 bars
                _bi_val = _bi[_iloc]
                _bi_recent = (
                    _bi_val is not None
                    and not (isinstance(_bi_val, float) and np.isnan(_bi_val))
                    and int(_bi_val) >= _n - _recent_window
                )
                _sig_recent = _iloc >= _n - _recent_window
                if not (_bi_recent or _sig_recent):
                    continue
                if _bos_active and _bos_v == 1:
                    _bos_bullish_signal = True
                if _bos_active and _bos_v == -1:
                    _bos_bearish_signal = True
                if _choch_active and _choch_v == 1:
                    _choch_bullish_signal = True
                if _choch_active and _choch_v == -1:
                    _choch_bearish_signal = True
        except Exception:
            pass  # graceful fallback — all signals remain False

    # P6.12 choch_bullish — CHoCH bullish reversal (trend change from down to up)
    if (
        _choch_bullish_signal
        and weekly_state in ("NEUTRAL", "BEARISH_WEAK")
    ):
        confidence = 0.70
        confidence = round(min(1.0, confidence), 3)
        detail["choch_bullish"] = True
        return {"pattern": "choch_bullish", "confidence": confidence, "detail": detail}

    # P6.13 choch_bearish — CHoCH bearish reversal (trend change from up to down)
    if (
        _choch_bearish_signal
        and weekly_state in ("NEUTRAL", "BULLISH", "BULLISH_EXTENDED")
    ):
        confidence = 0.70
        confidence = round(min(1.0, confidence), 3)
        detail["choch_bearish"] = True
        return {"pattern": "choch_bearish", "confidence": confidence, "detail": detail}

    # P6.14 bos_bullish — BOS bullish (continuation break, not reversal)
    if (
        _bos_bullish_signal
        and weekly_state in ("BULLISH", "BULLISH_EXTENDED")
    ):
        confidence = 0.68
        confidence = round(min(1.0, confidence), 3)
        detail["bos_bullish"] = True
        return {"pattern": "bos_bullish", "confidence": confidence, "detail": detail}

    # P6.15 bos_bearish — BOS bearish (continuation break downward)
    if (
        _bos_bearish_signal
        and weekly_state in ("BEARISH_WEAK", "BEARISH_STRONG")
    ):
        confidence = 0.68
        confidence = round(min(1.0, confidence), 3)
        detail["bos_bearish"] = True
        return {"pattern": "bos_bearish", "confidence": confidence, "detail": detail}

    # ── P6.23 bb_mean_reversion_long ─────────────────────────────────────────
    # Price at/below lower BB + ADX low (non-trending) + RSI oversold
    # Requires Bollinger bands already computed (_bbl_dp)
    if bbl_dp is not None and rsif is not None:
        _adx_full_mr = ddf["ADX_14"].dropna().tail(63).values
        # Floor at 20: in purely sideways markets the p35 can be very low (5-10);
        # using max(..., 20) ensures we don't exclude genuinely low-ADX conditions.
        _adx_p35_mr = max(20.0, float(np.percentile(_adx_full_mr, 35)) if len(_adx_full_mr) >= 10 else 20.0)
        _rsi_full_mr = ddf["RSI_14"].dropna().tail(63).values
        _rsi_p30_mr  = float(np.percentile(_rsi_full_mr, 30)) if len(_rsi_full_mr) >= 10 else 35.0
        if (
            close_now <= bbl_dp * 1.005                  # at or within 0.5% of lower BB
            and adxf < _adx_p35_mr                       # low trend strength
            and rsif < _rsi_p30_mr                       # oversold
            and weekly_state not in ("BULLISH_EXTENDED", "BEARISH_STRONG")
        ):
            confidence = 0.65
            if close_now <= bbl_dp:
                confidence += 0.05  # at or below lower band
            if rsif < _rsi_p30_mr * 0.85:
                confidence += 0.05  # deeply oversold
            confidence = round(min(1.0, confidence), 3)
            detail["bbl"] = round(bbl_dp, 2)
            detail["adx_p35"] = round(_adx_p35_mr, 2)
            return {"pattern": "bb_mean_reversion_long", "confidence": confidence, "detail": detail}

    # ── P6.24 bb_mean_reversion_short ────────────────────────────────────────
    # Price at/above upper BB + ADX low + RSI overbought
    if bbu_dp is not None and rsif is not None:
        _adx_full_mr2 = ddf["ADX_14"].dropna().tail(63).values
        _adx_p35_mr2 = max(20.0, float(np.percentile(_adx_full_mr2, 35)) if len(_adx_full_mr2) >= 10 else 20.0)
        _rsi_full_mr2 = ddf["RSI_14"].dropna().tail(63).values
        _rsi_p70_mr2  = float(np.percentile(_rsi_full_mr2, 70)) if len(_rsi_full_mr2) >= 10 else 65.0
        if (
            close_now >= bbu_dp * 0.995                  # at or within 0.5% of upper BB
            and adxf < _adx_p35_mr2                      # low trend strength
            and rsif > _rsi_p70_mr2                      # overbought
            and weekly_state not in ("BEARISH_STRONG", "BULLISH_EXTENDED")
        ):
            confidence = 0.65
            if close_now >= bbu_dp:
                confidence += 0.05  # at or above upper band
            if rsif > _rsi_p70_mr2 * 1.05:
                confidence += 0.05  # deeply overbought
            confidence = round(min(1.0, confidence), 3)
            detail["bbu"] = round(bbu_dp, 2)
            detail["adx_p35"] = round(_adx_p35_mr2, 2)
            return {"pattern": "bb_mean_reversion_short", "confidence": confidence, "detail": detail}

    # ── P6.25 ema200_snap_long ────────────────────────────────────────────────
    # Price > 15% below EMA200 + weekly RSI < 35 + ADX trending (not sideways) + up day
    _ema200_dp = ddf["EMA_200"].iloc[-1] if "EMA_200" in ddf.columns else None
    if _ema200_dp is not None and not pd.isna(_ema200_dp) and rsif is not None:
        _ema200_dp_f = float(_ema200_dp)
        _deviation_dp = (close_now / _ema200_dp_f - 1) if _ema200_dp_f > 0 else 0.0
        _adx_full_snap = ddf["ADX_14"].dropna().tail(63).values
        _adx_p40_snap  = float(np.percentile(_adx_full_snap, 40)) if len(_adx_full_snap) >= 10 else 20.0
        _wkly_rsi_snap = None
        if hasattr(weekly_df, 'index') and len(weekly_df) >= 15:
            _wdf_snap = weekly_df[weekly_df.index <= as_of_ts].copy()
            if len(_wdf_snap) >= 15:
                _wdf_snap.ta.rsi(length=14, append=True)
                _wkly_rsi_snap_raw = _wdf_snap.iloc[-1].get("RSI_14")
                _wkly_rsi_snap = float(_wkly_rsi_snap_raw) if _wkly_rsi_snap_raw is not None and not pd.isna(_wkly_rsi_snap_raw) else None
        _up_day_snap = (
            len(ddf) >= 2
            and "open" in ddf.columns
            and float(ddf["close"].iloc[-1]) > float(ddf["open"].iloc[-1])
        )
        # ADX threshold: use max(p40, 20) so in extreme crash regimes where p40 can
        # shoot to 100 (flat + sudden trend), a 20-floor ensures the check is fair.
        _adx_thresh_snap = min(_adx_p40_snap, 50.0)  # cap so ADX>50 always passes
        if (
            _deviation_dp < -0.15                        # >15% below EMA200
            and adxf > _adx_thresh_snap                  # trending (not sideways)
            and (_wkly_rsi_snap is None or _wkly_rsi_snap < 35.0)  # weekly deeply oversold
            and _up_day_snap
        ):
            confidence = 0.68
            if _deviation_dp < -0.20:
                confidence += 0.05  # extreme deviation bonus
            if _wkly_rsi_snap is not None and _wkly_rsi_snap < 25.0:
                confidence += 0.05
            confidence = round(min(1.0, confidence), 3)
            detail["ema200"] = round(_ema200_dp_f, 2)
            detail["ema200_deviation_pct"] = round(_deviation_dp * 100, 2)
            return {"pattern": "ema200_snap_long", "confidence": confidence, "detail": detail}

    # ── P6.26 ema200_snap_short ───────────────────────────────────────────────
    # Price > 15% above EMA200 + weekly RSI > 70 + down day
    if _ema200_dp is not None and not pd.isna(_ema200_dp) and rsif is not None:
        _ema200_dp_f2 = float(_ema200_dp)
        _deviation_dp2 = (close_now / _ema200_dp_f2 - 1) if _ema200_dp_f2 > 0 else 0.0
        _wkly_rsi_snap2 = None
        if hasattr(weekly_df, 'index') and len(weekly_df) >= 15:
            _wdf_snap2 = weekly_df[weekly_df.index <= as_of_ts].copy()
            if len(_wdf_snap2) >= 15:
                _wdf_snap2.ta.rsi(length=14, append=True)
                _wkly_rsi_snap2_raw = _wdf_snap2.iloc[-1].get("RSI_14")
                _wkly_rsi_snap2 = float(_wkly_rsi_snap2_raw) if _wkly_rsi_snap2_raw is not None and not pd.isna(_wkly_rsi_snap2_raw) else None
        _down_day_snap2 = (
            len(ddf) >= 2
            and "open" in ddf.columns
            and float(ddf["close"].iloc[-1]) < float(ddf["open"].iloc[-1])
        )
        if (
            _deviation_dp2 > 0.15                        # >15% above EMA200
            and (_wkly_rsi_snap2 is None or _wkly_rsi_snap2 > 70.0)  # weekly overbought
            and _down_day_snap2
        ):
            confidence = 0.68
            if _deviation_dp2 > 0.25:
                confidence += 0.05
            if _wkly_rsi_snap2 is not None and _wkly_rsi_snap2 > 80.0:
                confidence += 0.05
            confidence = round(min(1.0, confidence), 3)
            detail["ema200"] = round(_ema200_dp_f2, 2)
            detail["ema200_deviation_pct"] = round(_deviation_dp2 * 100, 2)
            return {"pattern": "ema200_snap_short", "confidence": confidence, "detail": detail}

    # ── P6.16–P6.22 reversal / failed setups (appended last; existing detection
    #    priority above is unchanged — these only catch bars that fell through) ──
    _bull_div, _bear_div = _rsi_divergence(ddf)
    detail["bull_divergence"] = _bull_div
    detail["bear_divergence"] = _bear_div

    # Weekly RSI + ADX (exhaustion / non-trend gates for reversals)
    _wk_rsi = None
    _wk_adx = None
    if hasattr(weekly_df, "index") and len(weekly_df) >= 15:
        _wk = weekly_df[weekly_df.index <= as_of_ts].copy()
        if len(_wk) >= 15:
            _wk.ta.rsi(length=14, append=True)
            _wk.ta.adx(length=14, append=True)
            _wkr = _wk.iloc[-1].get("RSI_14")
            _wka = _wk.iloc[-1].get("ADX_14")
            _wk_rsi = float(_wkr) if _wkr is not None and not pd.isna(_wkr) else None
            _wk_adx = float(_wka) if _wka is not None and not pd.isna(_wka) else None

    # Extra RSI/ADX percentiles needed by reversal gates
    _rf = ddf["RSI_14"].dropna().tail(63).values
    if len(_rf) >= 10:
        rsi_p20r = float(np.percentile(_rf, 20))
        rsi_p43r = float(np.percentile(_rf, 43))
        rsi_p55r = float(np.percentile(_rf, 55))
        rsi_p62r = float(np.percentile(_rf, 62))
        rsi_p80r = float(np.percentile(_rf, 80))
        rsi_p85r = float(np.percentile(_rf, 85))
    else:
        rsi_p20r, rsi_p43r, rsi_p55r = 32.0, 47.0, 55.0
        rsi_p62r, rsi_p80r, rsi_p85r = 58.0, 68.0, 72.0
    _af = ddf["ADX_14"].dropna().tail(63).values
    if len(_af) >= 10:
        adx_p30r = float(np.percentile(_af, 30))
        adx_p40r = float(np.percentile(_af, 40))
        adx_p70r = float(np.percentile(_af, 70))
    else:
        adx_p30r, adx_p40r, adx_p70r = 17.0, 20.0, 25.0

    # Volume-ratio percentiles (own rolling array — independent of P6 _dp block)
    _rv = ddf["volume"].dropna().tail(64).values
    if len(_rv) >= 21:
        _ra = np.array([
            float(np.mean(_rv[max(0, i - 20):i])) if i > 0 else float(_rv[0])
            for i in range(len(_rv))
        ])
        _rr = np.where(_ra > 0, _rv / _ra, 1.0)
        vol_p55r = float(np.percentile(_rr, 55))
        vol_p60r = float(np.percentile(_rr, 60))
        vol_p65r = float(np.percentile(_rr, 65))
        vol_p75r = float(np.percentile(_rr, 75))
    else:
        vol_p55r, vol_p60r, vol_p65r, vol_p75r = 1.1, 1.2, 1.3, 1.6

    _e200 = ddf["EMA_200"].iloc[-1] if "EMA_200" in ddf.columns else None
    _e200f = float(_e200) if _e200 is not None and not pd.isna(_e200) else None
    _prev_close = float(ddf["close"].iloc[-2]) if len(ddf) >= 2 else close_now
    _open_now = float(ddf["open"].iloc[-1]) if "open" in ddf.columns else close_now
    _recent20 = ddf.iloc[-20:]
    _recent_high = float(_recent20["close"].iloc[:-1].max()) if len(_recent20) >= 2 else close_now

    # P6.16 bullish_reversal — downtrend exhaustion + bull divergence + vol spike
    if (
        ema21f < ema50f and adxf > adx_p25_dp
        and (_bull_div or (rsif is not None and len(ddf) > 11
             and rsif > float(ddf["RSI_14"].iloc[-11])
             and close_now < float(ddf["close"].iloc[-11])))
        and vol_ratio > vol_p75r
        and adxf >= adx_p30r
        and _prev_close < close_now
        and rsif is not None and rsif < rsi_p55r
        and weekly_state == "BEARISH_WEAK"
        and (_wk_rsi is None or _wk_rsi < 35.0)
    ):
        confidence = 0.70
        detail["bullish_reversal"] = True
        return {"pattern": "bullish_reversal", "confidence": round(confidence, 3), "detail": detail}

    # P6.17 overbought_reversal (short) — extended bull trend + down day + vol
    if (
        daily_trend == "bullish" and adxf > adx_p40r
        and rsif is not None and rsif > rsi_p80r
        and _prev_close > close_now and close_now < _open_now
        and vol_ratio > vol_p65r
        and weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and (_wk_rsi is None or _wk_rsi > 65.0)
    ):
        confidence = 0.62
        if _bear_div:
            confidence += 0.08
        detail["overbought_reversal"] = True
        return {"pattern": "overbought_reversal", "confidence": round(min(1.0, confidence), 3), "detail": detail}

    # P6.18 bearish_reversal (short, strict) — strong-trend top + bear divergence
    if (
        daily_trend == "bullish" and adxf > adx_p70r
        and _bear_div
        and vol_ratio > vol_p75r
        and rsif is not None and rsif > rsi_p85r
        and weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and (_wk_rsi is None or _wk_rsi > 65.0)
    ):
        confidence = 0.66
        detail["bearish_reversal"] = True
        return {"pattern": "bearish_reversal", "confidence": round(confidence, 3), "detail": detail}

    # P6.19 oversold_bounce (long) — capitulation + reversal day above EMA200
    if (
        rsif is not None and rsif < rsi_p20r
        and _prev_close < close_now and close_now > _open_now
        and (_e200f is None or close_now > _e200f)
        and not (_wk_adx is not None and _wk_adx > 30.0)
        and weekly_state != "BEARISH_STRONG"
        and vol_ratio > vol_p60r
    ):
        confidence = 0.62
        if _bull_div:
            confidence += 0.08
        detail["oversold_bounce"] = True
        return {"pattern": "oversold_bounce", "confidence": round(min(1.0, confidence), 3), "detail": detail}

    # P6.20 failed_breakdown (long) — dipped below EMA21, reclaimed on volume
    _ema21_ewm = ddf["close"].ewm(span=21, adjust=False).mean()
    if (
        "low" in ddf.columns and len(ddf) >= 6
        and weekly_state in ("BULLISH", "BULLISH_EXTENDED", "NEUTRAL", "BEARISH_WEAK")
        and close_now <= _recent_high
        and close_now > float(_ema21_ewm.iloc[-1])
        and int((ddf["close"].iloc[-5:-1].values < _ema21_ewm.iloc[-5:-1].values).sum()) >= 2
        and vol_ratio > vol_p65r
    ):
        confidence = 0.68
        detail["failed_breakdown"] = True
        return {"pattern": "failed_breakdown", "confidence": round(confidence, 3), "detail": detail}

    # P6.21 failed_breakout (short) — exceeded a prior swing high, closed back below
    if (
        len(ddf) >= 64
        and weekly_state in ("BEARISH_STRONG", "BEARISH_WEAK", "NEUTRAL")
    ):
        _highs = ddf["high"].values[-60:].astype(float)
        _shi = argrelextrema(_highs, np.greater, order=5)[0]
        _prior = _shi[_shi < 56]
        if len(_prior) > 0:
            _spH = float(_highs[_prior[-1]])
            if (
                bool((ddf["high"].iloc[-4:-1] > _spH).any())
                and close_now < _spH
                and vol_ratio < vol_p55r
            ):
                confidence = 0.70
                detail["failed_breakout"] = True
                detail["prior_swing_high"] = round(_spH, 2)
                return {"pattern": "failed_breakout", "confidence": round(confidence, 3), "detail": detail}

    # P6.22 rally_in_downtrend (short) — weak low-vol bounce into EMA21 in downtrend
    if (
        weekly_state in ("BEARISH_STRONG", "BEARISH_WEAK")
        and rsif is not None and rsi_p43r <= rsif <= rsi_p62r
        and ema21f < ema50f
        and ema21f * 0.98 <= close_now <= ema21f
        and vol_ratio < vol_p55r
    ):
        confidence = 0.68
        detail["rally_in_downtrend"] = True
        return {"pattern": "rally_in_downtrend", "confidence": round(confidence, 3), "detail": detail}

    return {"pattern": "no_pattern", "confidence": 0.0, "detail": detail}


SETUP_TAXONOMY: list[str] = [
    "pullback_in_trend", "pullback_deep", "pullback_to_structure",
    "flag_continuation", "bull_flag", "rally_in_downtrend",
    "breakout", "breakdown", "compression_break", "compression_break_down",
    "base_breakout", "base_breakdown", "ema_reclaim", "ema_rejection",
    "bos_bullish", "bos_bearish",
    "bullish_reversal", "bearish_reversal", "overbought_reversal",
    "oversold_bounce", "failed_breakdown", "failed_breakout",
    "choch_bullish", "choch_bearish",
    "bb_mean_reversion_long", "bb_mean_reversion_short",
    "ema200_snap_long", "ema200_snap_short",
]
