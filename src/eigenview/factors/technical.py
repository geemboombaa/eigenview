from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers df.ta accessor
from scipy.signal import argrelextrema

from eigenview.config import settings
from eigenview.factors.base import FactorResult

# smartmoneyconcepts prints a Unicode banner on first import; on Windows cp1252
# consoles that raises UnicodeEncodeError, which the previous in-function
# `try/except Exception: pass` silently swallowed -- leaving BOS/CHoCH signals
# permanently False. Import once at module load with stdout redirected so the
# library is actually available to detect_pattern.
import contextlib as _contextlib
import io as _io
import os as _os
_os.environ.setdefault("PYTHONUTF8", "1")
try:
    with _contextlib.redirect_stdout(_io.StringIO()):
        import smartmoneyconcepts.smc as _smc  # noqa: E402
except Exception:  # pragma: no cover -- truly missing dep
    _smc = None

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
    "breakdown", "ema_rejection", "rally_short", "reversal_short",
    "failed_breakout", "bb_mr_short", "ema200_snap_short",
})

# Strong weekly states count toward confirmation (vs weak NEUTRAL/BEARISH_WEAK).
_STRONG_WEEKLY: frozenset[str] = frozenset({"BULLISH", "BULLISH_EXTENDED", "BEARISH_STRONG"})

# Setups that involve a structural break signal (BOS/CHoCH or level break).
_STRUCTURAL_BREAK: frozenset[str] = frozenset({
    "breakout", "breakdown", "ema_reclaim", "ema_rejection",
    "reversal_long", "reversal_short", "flag",
    "failed_breakdown", "failed_breakout",
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
        "vol_ratio": pdetail.get("vol_ratio"),
        "swing_high": pdetail.get("swing_high"),
        "swing_low": pdetail.get("swing_low"),
    }
    for k in (
        "probability_tier", "sub_type",
        "prior_swing_high", "n_bar_high", "n_bar_low", "bbu", "bbl",
        "ema200", "ema200_deviation_pct", "impulse_pct", "high_50d", "low_50d",
        "bull_divergence", "bear_divergence",
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


def _weekly_state_from(
    ema8: float,
    ema21: float,
    rsi_now: float | None,
    rsi_prev: float | None,
    adx: float | None,
) -> str:
    """Pure 5-state classifier from computed weekly indicators.

    'Extended' = genuine exhaustion only: an uptrend whose weekly RSI is above 85
    AND rolling over (this week below last week). A strong-but-intact uptrend
    (high RSI still rising) stays BULLISH so long setups are not switched off.
    """
    if ema8 > ema21:
        rolling_over = rsi_prev is not None and rsi_now is not None and rsi_now < rsi_prev
        if rsi_now is not None and rsi_now > 85 and rolling_over:
            return "BULLISH_EXTENDED"
        return "BULLISH"
    gap_pct = (ema21 - ema8) / ema21 if ema21 > 0 else 1.0
    if gap_pct < 0.02:
        return "NEUTRAL"
    if adx is not None and adx > 25:
        return "BEARISH_STRONG"
    return "BEARISH_WEAK"


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
    rsi_f = float(rsi) if rsi is not None and not pd.isna(rsi) else None
    adx_f = float(adx) if adx is not None and not pd.isna(adx) else None
    # Prior week's weekly RSI for the momentum-rollover check.
    rsi_prev = None
    if len(wdf) >= 2:
        _p = wdf.iloc[-2].get("RSI_14")
        rsi_prev = float(_p) if _p is not None and not pd.isna(_p) else None
    return _weekly_state_from(float(ema8), float(ema21), rsi_f, rsi_prev, adx_f)


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
    """Detect technical pattern. 16 setups: 8 HIGH + 8 SPECULATIVE.

    Returns {pattern, confidence (1.0 if firing), detail}.
    detail includes: trend, weekly_state, rsi, adx, vol_ratio, sub_type,
    probability_tier, direction, swing_low, swing_high.
    """
    ddf = daily_df.copy()
    if not isinstance(ddf.index, pd.DatetimeIndex):
        ddf.index = pd.to_datetime(ddf.index)
    if ddf.index.tz is not None:
        ddf.index = ddf.index.tz_localize(None)

    as_of_ts = pd.Timestamp(as_of_date) if as_of_date else ddf.index[-1]
    ddf = ddf[ddf.index <= as_of_ts]

    _empty = {
        "trend": None, "weekly_trend": None, "weekly_state": None,
        "rsi": None, "adx": None, "vol_ratio": None,
        "swing_low": None, "swing_high": None,
    }

    if len(ddf) < 30:
        return {"pattern": "no_pattern", "confidence": 0.0, "detail": _empty}

    # ── Daily indicators ──────────────────────────────────────────────────────
    ddf.ta.ema(length=21, append=True)
    ddf.ta.ema(length=50, append=True)
    ddf.ta.ema(length=200, append=True)
    ddf.ta.adx(length=14, append=True)
    ddf.ta.rsi(length=14, append=True)

    last  = ddf.iloc[-1]
    ema21 = last.get("EMA_21")
    ema50 = last.get("EMA_50")
    adx   = last.get("ADX_14")
    rsi   = last.get("RSI_14")

    if any(v is None or (isinstance(v, float) and pd.isna(v)) for v in [ema21, ema50, adx]):
        return {"pattern": "no_pattern", "confidence": 0.0, "detail": _empty}

    ema21f, ema50f = float(ema21), float(ema50)
    adxf  = float(adx)
    rsif  = float(rsi) if rsi is not None and not pd.isna(rsi) else None
    close_now = float(last["close"])

    vol_now = float(ddf["volume"].iloc[-1])
    vol_avg = float(ddf["volume"].iloc[-20:-1].mean()) if len(ddf) >= 21 else vol_now
    vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 1.0

    # ── UNIFIED PERCENTILE BLOCK (one computation, no _dp / _r suffix split) ──
    _rsi_s = ddf["RSI_14"].dropna().tail(63).values
    if len(_rsi_s) >= 10:
        rsi_p15 = min(35.0, float(np.percentile(_rsi_s, 15)))
        rsi_p20 = float(np.percentile(_rsi_s, 20))
        rsi_p25 = float(np.percentile(_rsi_s, 25))
        rsi_p30 = float(np.percentile(_rsi_s, 30))
        rsi_p40 = float(np.percentile(_rsi_s, 40))
        rsi_p55 = float(np.percentile(_rsi_s, 55))
        rsi_p60 = float(np.percentile(_rsi_s, 60))
        rsi_p65 = float(np.percentile(_rsi_s, 65))
        rsi_p70 = float(np.percentile(_rsi_s, 70))
        rsi_p80 = float(np.percentile(_rsi_s, 80))
        rsi_p85 = float(np.percentile(_rsi_s, 85))
    else:
        rsi_p15, rsi_p20, rsi_p25 = 32.0, 35.0, 38.0
        rsi_p30, rsi_p40, rsi_p55 = 40.0, 45.0, 55.0
        rsi_p60, rsi_p65, rsi_p70 = 57.0, 60.0, 63.0
        rsi_p80, rsi_p85 = 68.0, 72.0

    _adx_s = ddf["ADX_14"].dropna().tail(63).values
    if len(_adx_s) >= 10:
        adx_p25 = min(25.0, float(np.percentile(_adx_s, 25)))
        adx_p30 = float(np.percentile(_adx_s, 30))
        adx_p35 = max(20.0, float(np.percentile(_adx_s, 35)))
        adx_p40 = float(np.percentile(_adx_s, 40))
        adx_p70 = float(np.percentile(_adx_s, 70))
    else:
        adx_p25, adx_p30, adx_p35 = 15.0, 18.0, 20.0
        adx_p40, adx_p70 = 20.0, 25.0

    _vol_a = ddf["volume"].dropna().tail(64).values
    if len(_vol_a) >= 21:
        _va = np.array([
            float(np.mean(_vol_a[max(0, i - 20):i])) if i > 0 else float(_vol_a[0])
            for i in range(len(_vol_a))
        ])
        _vr = np.where(_va > 0, _vol_a / _va, 1.0)
        vol_p65 = float(np.percentile(_vr, 65))
        vol_p85 = float(np.percentile(_vr, 85))
    else:
        vol_p65 = 1.3
        vol_p85 = 2.0

    # ── Swing levels ──────────────────────────────────────────────────────────
    _closes = ddf["close"].values.astype(float)
    sw_low  = _swing_low(_closes)
    sw_high = _swing_high(_closes)

    # ── Daily trend (uses adx_p25 as sideways floor) ──────────────────────────
    daily_trend = "sideways" if adxf < adx_p25 else ("bullish" if ema21f > ema50f else "bearish")

    # ── Weekly 5-state ────────────────────────────────────────────────────────
    weekly_state = _classify_weekly_state(weekly_df, as_of_ts)
    weekly_trend = (
        "bullish" if weekly_state in ("BULLISH", "BULLISH_EXTENDED") else
        "bearish" if weekly_state in ("BEARISH_STRONG", "BEARISH_WEAK") else "neutral"
    )

    detail = {
        "trend": daily_trend, "weekly_trend": weekly_trend, "weekly_state": weekly_state,
        "rsi": round(rsif, 2) if rsif is not None else None,
        "adx": round(adxf, 2), "vol_ratio": vol_ratio,
        "swing_low": sw_low, "swing_high": sw_high,
    }

    # ── BB + Squeeze ──────────────────────────────────────────────────────────
    ddf.ta.bbands(length=20, append=True)
    _bbl = ddf.iloc[-1]
    _bbu_k = "BBU_20_2.0_2.0" if "BBU_20_2.0_2.0" in ddf.columns else "BBU_20_2.0"
    _bbl_k = "BBL_20_2.0_2.0" if "BBL_20_2.0_2.0" in ddf.columns else "BBL_20_2.0"
    _bbu_r = _bbl.get(_bbu_k); _bbl_r = _bbl.get(_bbl_k)
    bbu = float(_bbu_r) if _bbu_r is not None and not pd.isna(_bbu_r) else None
    bbl = float(_bbl_r) if _bbl_r is not None and not pd.isna(_bbl_r) else None

    try:
        _sqz = ta.squeeze_pro(ddf["high"], ddf["low"], ddf["close"])
        sq_on = bool(
            _sqz["SQZPRO_ON_NARROW"].iloc[-1]
            or _sqz["SQZPRO_ON_NORMAL"].iloc[-1]
            or _sqz["SQZPRO_ON_WIDE"].iloc[-1]
        )
        sq_released = bool(_sqz["SQZPRO_OFF"].iloc[-1]) and not sq_on
    except Exception:
        sq_on = sq_released = False

    # ── BOS / CHoCH ──────────────────────────────────────────────────────────
    choch_bull = False; choch_bear = False
    bos_bull   = False; bos_bear   = False
    if len(ddf) >= 40 and _smc is not None:
        try:
            _shl = _smc.swing_highs_lows(ddf, swing_length=10)
            _bc  = _smc.bos_choch(ddf, _shl, close_break=True)
            _n   = len(ddf)
            _bi  = _bc["BrokenIndex"].values
            _bv  = _bc["BOS"].values
            _cv  = _bc["CHOCH"].values
            for _i in range(len(_bc)):
                _b = _bv[_i]; _c = _cv[_i]
                _ba = not (isinstance(_b, float) and np.isnan(_b))
                _ca = not (isinstance(_c, float) and np.isnan(_c))
                if not _ba and not _ca:
                    continue
                _biv = _bi[_i]
                _bi_rec = (
                    _biv is not None
                    and not (isinstance(_biv, float) and np.isnan(_biv))
                    and int(_biv) >= _n - 60
                )
                if not (_bi_rec or _i >= _n - 60):
                    continue
                if _ba and _b == 1:  bos_bull  = True
                if _ba and _b == -1: bos_bear  = True
                if _ca and _c == 1:  choch_bull = True
                if _ca and _c == -1: choch_bear = True
        except Exception:
            pass

    # ── Divergence ────────────────────────────────────────────────────────────
    bull_div, bear_div = _rsi_divergence(ddf)
    detail["bull_divergence"] = bull_div
    detail["bear_divergence"] = bear_div

    # ── Weekly RSI / ADX ─────────────────────────────────────────────────────
    wk_rsi = None; wk_adx = None
    if hasattr(weekly_df, "index") and len(weekly_df) >= 15:
        _wk = weekly_df[weekly_df.index <= as_of_ts].copy()
        if len(_wk) >= 15:
            _wk.ta.rsi(length=14, append=True)
            _wk.ta.adx(length=14, append=True)
            _wr = _wk.iloc[-1].get("RSI_14"); _wa = _wk.iloc[-1].get("ADX_14")
            wk_rsi = float(_wr) if _wr is not None and not pd.isna(_wr) else None
            wk_adx = float(_wa) if _wa is not None and not pd.isna(_wa) else None

    # ── Misc ──────────────────────────────────────────────────────────────────
    prev_close   = float(ddf["close"].iloc[-2]) if len(ddf) >= 2 else close_now
    open_now     = float(ddf["open"].iloc[-1]) if "open" in ddf.columns else close_now
    _e200_raw    = ddf["EMA_200"].iloc[-1] if "EMA_200" in ddf.columns else None
    e200f        = float(_e200_raw) if _e200_raw is not None and not pd.isna(_e200_raw) else None
    ema21_ewm    = ddf["close"].ewm(span=21, adjust=False).mean()
    recent_high  = float(ddf["close"].iloc[-20:-1].max()) if len(ddf) >= 20 else close_now

    # =========================================================================
    # HIGH TIER — 8 patterns (first match wins within tier)
    # =========================================================================

    # ── PULLBACK (long) ───────────────────────────────────────────────────────
    # Uptrend price dips to EMA21 or EMA50. Vol quiet. RSI in dip zone.
    if (
        weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and daily_trend == "bullish"   # daily_trend==bullish already implies adxf > adx_p25
        and rsif is not None
        and rsi_p15 <= rsif <= rsi_p55
        and vol_ratio < vol_p65
    ):
        _at50 = -0.05 <= (close_now / ema50f - 1) <= 0.01
        _at21 = ema21f * 0.96 <= close_now <= ema21f * 1.04
        _sub  = "ema50" if _at50 else ("ema21" if _at21 else None)
        if _sub is not None:
            detail.update({"sub_type": _sub, "probability_tier": "HIGH", "direction": "long"})
            return {"pattern": "pullback", "confidence": 1.0, "detail": detail}

    # ── BREAKOUT (long) ───────────────────────────────────────────────────────
    # Price breaks above structural level: squeeze / base / N-bar high. BOS + vol_p85.
    if (
        weekly_state == "BULLISH"  # EXTENDED excluded — late-cycle risk
        and bos_bull
        and vol_ratio > vol_p85
    ):
        _sub = None
        # 1. Squeeze release
        if (sq_released and bbu is not None and close_now > bbu
                and open_now < close_now and (rsif is None or rsif < 90.0)):
            _sub = "squeeze_release"
            detail["bbu"] = round(bbu, 2)
        # 2. Base breakout (VCP)
        if _sub is None and len(ddf) >= 50:
            _std_s = ddf["close"].rolling(20).std().dropna()
            if len(_std_s) >= 10:
                _std_now = float(_std_s.iloc[-1])
                _std_p25 = float(np.percentile(_std_s.tail(63), 25))
                _h50 = float(ddf["close"].tail(50).max())
                if _std_now < _std_p25 and sq_on and close_now >= _h50 * 1.001:
                    _sub = "base_break"
                    detail["high_50d"] = round(_h50, 2)
        # 3. Level breakout
        if _sub is None and len(ddf) >= 60:
            _h60 = ddf["high"].values[-60:].astype(float)
            _shi = argrelextrema(_h60, np.greater, order=5)[0]
            if len(_shi) > 0:
                _nbh = _h60[_shi[-1]]
                _app = int(np.sum(np.abs(_h60[:_shi[-1]] / _nbh - 1) < 0.01))
                _held = (close_now > _nbh and len(ddf) >= 2
                         and float(ddf["close"].iloc[-2]) >= _nbh * 0.998)
                if _held and _app >= 1:
                    _sub = "level_break"
                    detail["n_bar_high"] = round(_nbh, 2)
        if _sub is not None:
            detail.update({"sub_type": _sub, "probability_tier": "HIGH", "direction": "long"})
            return {"pattern": "breakout", "confidence": 1.0, "detail": detail}

    # ── EMA_RECLAIM (long) ────────────────────────────────────────────────────
    # Price crosses EMA50 from below — regime change. BOS/CHoCH + vol.
    if (
        weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and len(ddf) >= 2
        and float(ddf["close"].iloc[-2]) < float(ddf["EMA_50"].iloc[-2])
        and close_now > ema50f * 1.005
        and vol_ratio > vol_p65
        and (bos_bull or choch_bull)
    ):
        detail.update({"probability_tier": "HIGH", "direction": "long"})
        return {"pattern": "ema_reclaim", "confidence": 1.0, "detail": detail}

    # ── REVERSAL_LONG (long) ──────────────────────────────────────────────────
    # Downtrend/sideways exhaustion. CHoCH + bull_div both required.
    if (
        weekly_state in ("BEARISH_WEAK", "NEUTRAL")
        and choch_bull
        and bull_div
        and vol_ratio > vol_p65
        and rsif is not None
    ):
        _sub = None
        # Oversold variant
        if (rsif < rsi_p20
                and close_now > ema21f
                and (e200f is None or close_now > e200f)
                and not (wk_adx is not None and wk_adx > 30.0)):
            _sub = "oversold"
        # Downtrend exhaustion variant
        elif (ema21f < ema50f
              and adxf >= adx_p30
              and rsif < rsi_p55
              and prev_close < close_now
              and (wk_rsi is None or wk_rsi < 35.0)):
            _sub = "downtrend_exhaustion"
        if _sub is not None:
            detail.update({"sub_type": _sub, "probability_tier": "HIGH", "direction": "long"})
            return {"pattern": "reversal_long", "confidence": 1.0, "detail": detail}

    # ── RALLY_SHORT (short) ───────────────────────────────────────────────────
    # Downtrend price rallies into EMA21 resistance. Vol quiet. RSI mid-zone.
    if (
        weekly_state in ("BEARISH_STRONG", "BEARISH_WEAK")
        and rsif is not None
        and rsi_p40 <= rsif <= rsi_p60
        and ema21f < ema50f
        and ema21f * 0.98 <= close_now <= ema21f
        and vol_ratio < vol_p65
    ):
        detail.update({"probability_tier": "HIGH", "direction": "short"})
        return {"pattern": "rally_short", "confidence": 1.0, "detail": detail}

    # ── BREAKDOWN (short) ─────────────────────────────────────────────────────
    # Price breaks below structural level: squeeze / base / N-bar low. BOS + vol_p85.
    if (
        weekly_state in ("BEARISH_WEAK", "BEARISH_STRONG")
        and bos_bear
        and vol_ratio > vol_p85
    ):
        _sub = None
        # 1. Squeeze release
        if (sq_released and bbl is not None and close_now < bbl and open_now > close_now):
            _sub = "squeeze_release"
            detail["bbl"] = round(bbl, 2)
        # 2. Base breakdown
        if _sub is None and len(ddf) >= 50:
            _std_sb = ddf["close"].rolling(20).std().dropna()
            if len(_std_sb) >= 10:
                _std_nb = float(_std_sb.iloc[-1])
                _std_p25b = float(np.percentile(_std_sb.tail(63), 25))
                _l50 = float(ddf["close"].tail(50).min())
                if _std_nb < _std_p25b and sq_on and close_now <= _l50 * 0.999:
                    _sub = "base_break"
                    detail["low_50d"] = round(_l50, 2)
        # 3. Level breakdown
        if _sub is None and len(ddf) >= 60:
            _l60 = ddf["low"].values[-60:].astype(float)
            _sli = argrelextrema(_l60, np.less, order=5)[0]
            if len(_sli) > 0:
                _nbl = _l60[_sli[-1]]
                _held_dn = (close_now < _nbl and len(ddf) >= 2
                            and float(ddf["close"].iloc[-2]) <= _nbl * 1.002)
                if _held_dn:
                    _sub = "level_break"
                    detail["n_bar_low"] = round(_nbl, 2)
        if _sub is not None:
            detail.update({"sub_type": _sub, "probability_tier": "HIGH", "direction": "short"})
            return {"pattern": "breakdown", "confidence": 1.0, "detail": detail}

    # ── EMA_REJECTION (short) ─────────────────────────────────────────────────
    # Price crosses EMA50 from above — regime change. BOS/CHoCH + vol.
    if (
        weekly_state in ("BEARISH_WEAK", "BEARISH_STRONG", "NEUTRAL")
        and len(ddf) >= 2
        and float(ddf["close"].iloc[-2]) > float(ddf["EMA_50"].iloc[-2])
        and close_now < ema50f * 0.995
        and vol_ratio > vol_p65
        and (bos_bear or choch_bear)
    ):
        detail.update({"probability_tier": "HIGH", "direction": "short"})
        return {"pattern": "ema_rejection", "confidence": 1.0, "detail": detail}

    # ── REVERSAL_SHORT (short) ────────────────────────────────────────────────
    # Uptrend/extended exhaustion. CHoCH + bear_div both required.
    if (
        weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and choch_bear
        and bear_div
        and vol_ratio > vol_p65
        and daily_trend == "bullish"
        and rsif is not None
    ):
        _sub = None
        # Strict variant (higher ADX + RSI extremes)
        if (adxf > adx_p70 and rsif > rsi_p85
                and (wk_rsi is None or wk_rsi > 65.0)):
            _sub = "strict"
        # Standard variant
        elif (adxf > adx_p40 and rsif > rsi_p80
              and prev_close > close_now and close_now < open_now
              and (wk_rsi is None or wk_rsi > 65.0)):
            _sub = "standard"
        if _sub is not None:
            detail.update({"sub_type": _sub, "probability_tier": "HIGH", "direction": "short"})
            return {"pattern": "reversal_short", "confidence": 1.0, "detail": detail}

    # =========================================================================
    # SPECULATIVE TIER — 8 patterns
    # =========================================================================

    # ── PULLBACK_STRUCTURE (long) ─────────────────────────────────────────────
    # Pullback to prior 60-bar swing high turned support. Noisier level detection.
    if (
        weekly_state in ("BULLISH", "BULLISH_EXTENDED")
        and daily_trend == "bullish"
        and rsif is not None
        and rsi_p30 <= rsif <= rsi_p55
        and vol_ratio < vol_p65
        and len(ddf) >= 60
    ):
        _h60s = ddf["high"].values[-60:].astype(float)
        _hi_s = argrelextrema(_h60s, np.greater, order=5)[0]
        if len(_hi_s) >= 2:
            _psh = _h60s[_hi_s[-2]]
            if abs(close_now / _psh - 1) < 0.02:
                detail.update({"prior_swing_high": round(_psh, 2),
                               "probability_tier": "SPECULATIVE", "direction": "long"})
                return {"pattern": "pullback_structure", "confidence": 1.0, "detail": detail}

    # ── FLAG (long) ───────────────────────────────────────────────────────────
    # Post-impulse consolidation (squeeze) with BOS on resolve. Weekly BULLISH only.
    if (
        weekly_state == "BULLISH"
        and rsif is not None
        and rsi_p40 <= rsif <= rsi_p65
        and vol_ratio < vol_p65
        and sq_on
        and len(ddf) >= 12
        and bos_bull
    ):
        _imp = (float(ddf["close"].iloc[-1]) / float(ddf["close"].iloc[-11]) - 1) * 100
        if _imp > 5.0:
            detail.update({"impulse_pct": round(_imp, 2),
                           "probability_tier": "SPECULATIVE", "direction": "long"})
            return {"pattern": "flag", "confidence": 1.0, "detail": detail}

    # ── FAILED_BREAKDOWN (long) ───────────────────────────────────────────────
    # Price dipped below EMA21 then recovered — CHoCH confirms structural flip.
    if (
        "low" in ddf.columns and len(ddf) >= 6
        and weekly_state in ("BULLISH", "BULLISH_EXTENDED", "NEUTRAL", "BEARISH_WEAK")
        and close_now <= recent_high
        and close_now > float(ema21_ewm.iloc[-1])
        and open_now <= float(ema21_ewm.iloc[-1]) * 1.01
        and int((ddf["close"].iloc[-5:-1].values < ema21_ewm.iloc[-5:-1].values).sum()) >= 2
        and vol_ratio > vol_p65
        and choch_bull
    ):
        detail.update({"probability_tier": "SPECULATIVE", "direction": "long"})
        return {"pattern": "failed_breakdown", "confidence": 1.0, "detail": detail}

    # ── FAILED_BREAKOUT (short) ───────────────────────────────────────────────
    # Price exceeded prior swing high, reversed back below — CHoCH confirms.
    if (
        len(ddf) >= 64
        and weekly_state in ("BEARISH_STRONG", "BEARISH_WEAK", "NEUTRAL")
    ):
        _h60f = ddf["high"].values[-60:].astype(float)
        _shif = argrelextrema(_h60f, np.greater, order=5)[0]
        _prf  = _shif[_shif < 56]
        if len(_prf) > 0:
            _spH = float(_h60f[_prf[-1]])
            if (
                bool((ddf["high"].iloc[-4:-1] > _spH).any())
                and close_now < _spH
                and close_now < open_now
                and vol_ratio < vol_p65
                and choch_bear
            ):
                detail.update({"prior_swing_high": round(_spH, 2),
                               "probability_tier": "SPECULATIVE", "direction": "short"})
                return {"pattern": "failed_breakout", "confidence": 1.0, "detail": detail}

    # ── BB_MR_LONG (long) ─────────────────────────────────────────────────────
    # Price at lower BB in low-ADX sideways range. Mean reversion.
    if bbl is not None and rsif is not None:
        if (
            close_now <= bbl * 1.005
            and adxf < adx_p35
            and rsif < rsi_p30
            and weekly_state not in ("BULLISH_EXTENDED", "BEARISH_STRONG")
        ):
            detail.update({"bbl": round(bbl, 2),
                           "probability_tier": "SPECULATIVE", "direction": "long"})
            return {"pattern": "bb_mr_long", "confidence": 1.0, "detail": detail}

    # ── BB_MR_SHORT (short) ───────────────────────────────────────────────────
    # Price at upper BB in low-ADX sideways range. Mean reversion.
    if bbu is not None and rsif is not None:
        if (
            close_now >= bbu * 0.995
            and adxf < adx_p35
            and rsif > rsi_p70
            and weekly_state not in ("BEARISH_STRONG", "BULLISH_EXTENDED")
        ):
            detail.update({"bbu": round(bbu, 2),
                           "probability_tier": "SPECULATIVE", "direction": "short"})
            return {"pattern": "bb_mr_short", "confidence": 1.0, "detail": detail}

    # ── EMA200_SNAP_LONG (long) ───────────────────────────────────────────────
    # Extreme stretch below EMA200. Threshold: stock's own historical p10 deviation.
    if e200f is not None and rsif is not None and len(ddf) >= 63:
        _dev = (close_now / e200f - 1)
        _dev_hist = ((ddf["close"] / ddf["EMA_200"]) - 1).dropna().tail(126).values
        _dev_p10  = float(np.percentile(_dev_hist, 10)) if len(_dev_hist) >= 20 else -0.15
        _up_day   = ("open" in ddf.columns
                     and float(ddf["close"].iloc[-1]) > float(ddf["open"].iloc[-1]))
        if (
            _dev < _dev_p10
            and adxf > min(adx_p40, 50.0)
            and (wk_rsi is None or wk_rsi < 35.0)
            and _up_day
        ):
            detail.update({"ema200": round(e200f, 2),
                           "ema200_deviation_pct": round(_dev * 100, 2),
                           "probability_tier": "SPECULATIVE", "direction": "long"})
            return {"pattern": "ema200_snap_long", "confidence": 1.0, "detail": detail}

    # ── EMA200_SNAP_SHORT (short) ─────────────────────────────────────────────
    # Extreme stretch above EMA200. Threshold: stock's own historical p90 deviation.
    if e200f is not None and rsif is not None and len(ddf) >= 63:
        _dev2 = (close_now / e200f - 1)
        _dev_hist2 = ((ddf["close"] / ddf["EMA_200"]) - 1).dropna().tail(126).values
        _dev_p90   = float(np.percentile(_dev_hist2, 90)) if len(_dev_hist2) >= 20 else 0.15
        _down_day  = ("open" in ddf.columns
                      and float(ddf["close"].iloc[-1]) < float(ddf["open"].iloc[-1]))
        if (
            _dev2 > _dev_p90
            and (wk_rsi is None or wk_rsi > 70.0)
            and _down_day
        ):
            detail.update({"ema200": round(e200f, 2),
                           "ema200_deviation_pct": round(_dev2 * 100, 2),
                           "probability_tier": "SPECULATIVE", "direction": "short"})
            return {"pattern": "ema200_snap_short", "confidence": 1.0, "detail": detail}

    return {"pattern": "no_pattern", "confidence": 0.0, "detail": detail}


# HIGH: 8 patterns — pullback, breakout, ema_reclaim, reversal_long,
#                    rally_short, breakdown, ema_rejection, reversal_short
# SPECULATIVE: 8 patterns — pullback_structure, flag, failed_breakdown,
#                            failed_breakout, bb_mr_long, bb_mr_short,
#                            ema200_snap_long, ema200_snap_short
SETUP_TAXONOMY: list[str] = [
    "pullback", "breakout", "ema_reclaim", "reversal_long",
    "rally_short", "breakdown", "ema_rejection", "reversal_short",
    "pullback_structure", "flag", "failed_breakdown", "failed_breakout",
    "bb_mr_long", "bb_mr_short", "ema200_snap_long", "ema200_snap_short",
]
