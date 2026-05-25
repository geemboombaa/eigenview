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


def score_technical(df: pd.DataFrame, ticker: str = "") -> FactorResult:
    if df is None or len(df) < 30:
        return FactorResult.no_data("technical", "insufficient price history")

    df = df.copy()
    # Ensure DatetimeIndex for weekly resampling
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'date' in df.columns:
            df.index = pd.to_datetime(df['date'])
        else:
            df.index = pd.to_datetime(df.index)

    # --- Daily indicators ---
    df.ta.ema(length=21,  append=True)
    df.ta.ema(length=50,  append=True)
    df.ta.ema(length=200, append=True)
    df.ta.adx(length=14,  append=True)
    df.ta.rsi(length=14,  append=True)
    df.ta.bbands(length=20, append=True)
    df.ta.atr(length=14,  append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)

    last = df.iloc[-1]
    recent = df.iloc[-20:]

    ema21   = last.get("EMA_21")
    ema50   = last.get("EMA_50")
    ema200  = last.get("EMA_200")
    adx     = last.get("ADX_14")
    rsi     = last.get("RSI_14")
    bbu     = last.get("BBU_20_2.0")
    bbl     = last.get("BBL_20_2.0")
    close_now = float(last["close"])
    vol_now   = float(df["volume"].iloc[-1])
    vol_avg   = float(df["volume"].iloc[-20:-1].mean())
    atr_last5 = float(df["ATRr_14"].iloc[-5:].mean())
    atr_20avg = float(df["ATRr_14"].iloc[-20:].mean())
    recent_high = float(recent["close"].iloc[:-1].max())
    recent_low  = float(recent["close"].iloc[:-1].min())  # exclude last bar for breakdown detection

    if ema21 is None or pd.isna(ema21) or ema50 is None or pd.isna(ema50) or adx is None or pd.isna(adx):
        return FactorResult.no_data("technical", "indicator computation failed")

    ema21f  = float(ema21)
    ema50f  = float(ema50)
    ema200f = float(ema200) if ema200 is not None and not pd.isna(ema200) else None
    adxf    = float(adx)
    rsif    = float(rsi) if rsi is not None and not pd.isna(rsi) else None

    # --- Rolling percentile thresholds (63-bar = 3 calendar months) ---
    # Computed once at top; used throughout. Fallback to static values when <60 bars.
    rsi_series = df['RSI_14'].dropna()
    if len(rsi_series) >= 60:
        _rsi = rsi_series.tail(63).values
        rsi_p10  = float(np.percentile(_rsi, 10))
        rsi_p12  = float(np.percentile(_rsi, 12))
        rsi_p15  = float(np.percentile(_rsi, 15))
        rsi_p20  = float(np.percentile(_rsi, 20))
        rsi_p25  = float(np.percentile(_rsi, 25))
        rsi_p40  = float(np.percentile(_rsi, 40))
        rsi_p43  = float(np.percentile(_rsi, 43))
        rsi_p55  = float(np.percentile(_rsi, 55))
        rsi_p60  = float(np.percentile(_rsi, 60))
        rsi_p62  = float(np.percentile(_rsi, 62))
        rsi_p65  = float(np.percentile(_rsi, 65))
        rsi_p80  = float(np.percentile(_rsi, 80))
        rsi_p85  = float(np.percentile(_rsi, 85))
        rsi_p88  = float(np.percentile(_rsi, 88))
        rsi_p90  = float(np.percentile(_rsi, 90))
        rsi_p93  = float(np.percentile(_rsi, 93))
    else:
        rsi_p10  = _RSI_FALLBACK_PCTL[10]
        rsi_p12  = _RSI_FALLBACK_PCTL[12]
        rsi_p15  = _RSI_FALLBACK_PCTL[15]
        rsi_p20  = _RSI_FALLBACK_PCTL[20]
        rsi_p25  = _RSI_FALLBACK_PCTL[25]
        rsi_p40  = _RSI_FALLBACK_PCTL[40]
        rsi_p43  = _RSI_FALLBACK_PCTL[43]
        rsi_p55  = _RSI_FALLBACK_PCTL[55]
        rsi_p60  = _RSI_FALLBACK_PCTL[60]
        rsi_p62  = _RSI_FALLBACK_PCTL[62]
        rsi_p65  = _RSI_FALLBACK_PCTL[65]
        rsi_p80  = _RSI_FALLBACK_PCTL[80]
        rsi_p85  = _RSI_FALLBACK_PCTL[85]
        rsi_p88  = _RSI_FALLBACK_PCTL[88]
        rsi_p90  = _RSI_FALLBACK_PCTL[90]
        rsi_p93  = _RSI_FALLBACK_PCTL[93]

    adx_series = df['ADX_14'].dropna()
    if len(adx_series) >= 60:
        _adx = adx_series.tail(63).values
        # Cap sideways/trend thresholds so strongly-trending regimes don't mis-classify
        adx_p25 = min(20.0, float(np.percentile(_adx, 25)))
        adx_p30 = min(22.0, float(np.percentile(_adx, 30)))
        adx_p40 = min(25.0, float(np.percentile(_adx, 40)))
        adx_p70 = float(np.percentile(_adx, 70))
        adx_p75 = float(np.percentile(_adx, 75))
    else:
        adx_p25 = _ADX_FALLBACK_PCTL[25]
        adx_p30 = _ADX_FALLBACK_PCTL[30]
        adx_p40 = _ADX_FALLBACK_PCTL[40]
        adx_p70 = _ADX_FALLBACK_PCTL[70]
        adx_p75 = _ADX_FALLBACK_PCTL[75]

    # ATR ratio series: atr_last5 / atr_20avg for each rolling window
    atr_col = df['ATRr_14'].dropna()
    if len(atr_col) >= 60:
        _atr = atr_col.tail(63).values
        # Compute rolling ratio: each bar's 5-bar mean / 20-bar mean
        _atr_ratios = np.array([
            (_atr[max(0, i-4):i+1].mean() / _atr[max(0, i-19):i+1].mean())
            if _atr[max(0, i-19):i+1].mean() > 0 else 1.0
            for i in range(len(_atr))
        ])
        atr_p15 = float(np.percentile(_atr_ratios, 15))
        atr_p20 = float(np.percentile(_atr_ratios, 20))
    else:
        atr_p15 = 0.65
        atr_p20 = 0.70

    # Vol ratio percentiles: use last 63 daily vol/vol_avg ratios
    vol_series = df['volume'].dropna()
    if len(vol_series) >= 60:
        _vols = vol_series.tail(64).values  # 64 so we can compute ratio vs prior 20
        _vol_avgs = np.array([
            float(np.mean(_vols[max(0, i-20):i])) if i > 0 else float(_vols[0])
            for i in range(len(_vols))
        ])
        _vol_ratios = np.where(_vol_avgs > 0, _vols / _vol_avgs, 1.0)
        vol_p55 = float(np.percentile(_vol_ratios, 55))
        vol_p60 = float(np.percentile(_vol_ratios, 60))
        vol_p65 = float(np.percentile(_vol_ratios, 65))
        vol_p72 = float(np.percentile(_vol_ratios, 72))
        vol_p75 = float(np.percentile(_vol_ratios, 75))
        vol_p80 = float(np.percentile(_vol_ratios, 80))
        vol_p85 = float(np.percentile(_vol_ratios, 85))
        vol_p92 = float(np.percentile(_vol_ratios, 92))
    else:
        vol_p55 = 1.1
        vol_p60 = 1.2
        vol_p65 = 1.3
        vol_p72 = 1.5
        vol_p75 = 1.6
        vol_p80 = 1.8
        vol_p85 = 2.0
        vol_p92 = 2.5

    # --- Weekly context (MTF) ---
    wc = _compute_weekly_context(df)
    weekly_trend_str = _weekly_trend(wc)

    # --- Volume character ---
    vol_char = _vol_character(df)
    vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 0.0

    # --- RSI divergence ---
    bull_div, bear_div = _rsi_divergence(df)

    # --- Fibonacci levels ---
    fib = _compute_fib_levels(df)

    # --- Daily trend ---
    if adxf <= adx_p40:
        daily_trend = "sideways"
    elif ema21f > ema50f:
        daily_trend = "bullish"
    else:
        daily_trend = "bearish"

    # Combined trend considering weekly
    if weekly_trend_str == 'bullish' and daily_trend == 'bullish':
        trend = 'bullish'
    elif weekly_trend_str == 'bearish_strong':
        trend = 'bearish'
    elif daily_trend == 'bearish':
        trend = 'bearish'
    else:
        trend = daily_trend

    # --- Squeeze Pro (pandas_ta) ---
    # squeeze_pro replaces manual ATR-range compression check.
    # ON_WIDE/NORMAL/NARROW = squeeze active; OFF = just released; NO = no squeeze.
    try:
        sqz = ta.squeeze_pro(df['high'], df['low'], df['close'])
        squeeze_on = bool(
            sqz['SQZPRO_ON_NARROW'].iloc[-1]
            or sqz['SQZPRO_ON_NORMAL'].iloc[-1]
            or sqz['SQZPRO_ON_WIDE'].iloc[-1]
        )
        squeeze_off = bool(sqz['SQZPRO_OFF'].iloc[-1])
        squeeze_released = squeeze_off and not squeeze_on  # was compressed, now releasing
    except Exception:
        # Graceful fallback: use ATR ratio as proxy
        squeeze_released = (not pd.isna(atr_last5) and not pd.isna(atr_20avg)
                            and atr_20avg > 0 and atr_last5 < atr_20avg * atr_p20)
        squeeze_on = (not pd.isna(atr_last5) and not pd.isna(atr_20avg)
                      and atr_20avg > 0 and atr_last5 < atr_20avg * atr_p15)

    # ------------------------------------------------------------------
    # PATTERN DETECTION (8 long + 7 short)
    # Long:  bullish_reversal > compression_break > ema_reclaim >
    #        pullback_in_trend > base_breakout > oversold_bounce >
    #        failed_breakdown > breakout
    # Short: overbought_reversal > compression_break_down > ema_rejection >
    #        rally_in_downtrend > base_breakdown > failed_breakout > breakdown
    #        bearish_reversal (last)
    # ------------------------------------------------------------------

    pattern    = "no_pattern"
    confidence = 0.0

    # --- bullish_reversal ---
    # P6·16: tightened — weekly RSI < 35 REQUIRED, BEARISH_WEAK weekly only, ADX >= adx_p30
    in_downtrend_20 = (ema21f < ema50f) and (adxf > adx_p25)
    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else close_now
    two_bar_confirm = (prev_close < close_now) and (vol_now > vol_avg * vol_p65)
    # Simplified RSI divergence: current RSI > RSI 10 bars ago but price lower
    rsi_10_ago = float(df['RSI_14'].iloc[-11]) if 'RSI_14' in df.columns and len(df) > 11 else rsif
    price_10_ago = float(df['close'].iloc[-11]) if len(df) > 11 else close_now
    rsi_diverge_bull = (rsif is not None and rsi_10_ago is not None
                        and rsif > rsi_10_ago and close_now < price_10_ago)
    weekly_rsi_ok = wc.rsi is not None and wc.rsi < 35.0
    weekly_state_ok = weekly_trend_str == 'bearish_weak'
    if (in_downtrend_20
            and (bull_div or rsi_diverge_bull)
            and vol_now > vol_avg * vol_p75
            and adxf >= adx_p30
            and two_bar_confirm
            and rsif is not None and rsif < rsi_p55
            and weekly_rsi_ok
            and weekly_state_ok):
        pattern = "bullish_reversal"
        confidence = 0.70
        if vol_now > vol_avg * vol_p92:
            confidence += 0.10  # exhaustion spike bonus

    # --- overbought_reversal (short) ---
    # P6·19: Bullish trend + extended RSI + down day/candle + vol expanding + weekly RSI>65 + BULLISH
    elif (daily_trend == 'bullish' and adxf > adx_p40
          and rsif is not None and rsif > rsi_p80
          and len(df) >= 2 and float(df['close'].iloc[-2]) > close_now
          and 'open' in df.columns and close_now < float(df['open'].iloc[-1])
          and vol_now > vol_avg * vol_p65
          and wc.rsi is not None and wc.rsi > 65.0
          and weekly_trend_str == 'bullish'):
        pattern    = "overbought_reversal"
        confidence = 0.60
        if wc.rsi is not None and wc.rsi > 70.0:
            confidence += 0.08
        if rsif > rsi_p88:
            confidence += 0.05
        if bear_div:
            confidence += 0.08
        if vol_now > vol_avg * vol_p80:
            confidence += 0.05

    # --- compression_break ---
    # squeeze_pro: squeeze just released (OFF) + momentum positive (close > BBU) + vol surge
    elif (squeeze_released
          and bbu is not None and not pd.isna(bbu)
          and close_now > float(bbu)             # close above BBU — upward momentum
          and vol_now > vol_avg * vol_p72         # volume confirmation
          and (rsif is None or rsif < rsi_p90)):  # not already extended
        pattern    = "compression_break"
        confidence = 0.75
        if wc.bb_squeeze:
            confidence += 0.05  # weekly BB also squeezing
        if vol_now > vol_avg * vol_p85:
            confidence += 0.05
        if weekly_trend_str == 'bearish_strong':
            confidence -= 0.20

    # --- compression_break_down (short) ---
    # squeeze_pro: squeeze just released (OFF) + momentum negative (close < BBL) + vol surge
    elif (squeeze_released
          and bbl is not None and not pd.isna(bbl)
          and close_now < float(bbl)
          and vol_now > vol_avg * vol_p72
          and (rsif is None or rsif > rsi_p10)):
        pattern    = "compression_break_down"
        confidence = 0.73
        if wc.bb_squeeze:
            confidence += 0.05
        if vol_now > vol_avg * vol_p85:
            confidence += 0.05
        if weekly_trend_str == 'bearish_strong':
            confidence += 0.05

    # --- ema_reclaim ---
    # Price was below EMA50, now closes back above it (requires non-bearish daily trend)
    elif (ema21f is not None
          and daily_trend != "bearish"
          and (float(df["close"].iloc[-3]) < ema50f if len(df) >= 3 else False)
          and close_now > ema50f
          and vol_now > vol_avg * vol_p55
          and weekly_trend_str in ('bullish', 'bearish_weak', 'unknown')):
        pattern    = "ema_reclaim"
        confidence = 0.65
        if ema50f > 0 and (ema50f - float(df["EMA_50"].iloc[-5:].min())) >= 0:
            confidence += 0.05  # EMA50 is rising

    # --- ema_rejection (short) ---
    # Price was above EMA50, closes back below it on volume
    elif (daily_trend != "bullish"
          and len(df) >= 3
          and float(df["close"].iloc[-3]) > ema50f
          and close_now < ema50f
          and vol_now > vol_avg * vol_p55
          and weekly_trend_str in ('bearish_strong', 'bearish_weak', 'unknown')):
        pattern    = "ema_rejection"
        confidence = 0.63
        if weekly_trend_str == 'bearish_strong':
            confidence += 0.07
        if vol_now > vol_avg * vol_p72:
            confidence += 0.05

    # --- pullback_in_trend ---
    # Bullish EMA stack, RSI in dip zone, price above EMA21, below EMA50 ceiling
    # Bounds: floor = min(rsi_p25, 45) so strong-trend stocks don't over-restrict;
    #         ceiling = min(rsi_p55, 60) so overbought conditions are excluded.
    elif (daily_trend == "bullish"
          and rsif is not None
          and min(rsi_p25, 45.0) <= rsif <= min(rsi_p55, 60.0)
          and close_now > ema21f * 0.99
          and close_now < ema50f * 1.08
          and weekly_trend_str in ('bullish', 'bearish_weak', 'unknown')):
        pattern    = "pullback_in_trend"
        confidence = 0.70
        if vol_char == 'expanding':
            confidence -= 0.08  # expanding vol on pullback = sellers present, weaker setup
        if close_now < ema50f * 1.02:
            confidence += 0.05
        # Fib confluence: near 38.2% or 61.8% retracement
        if fib.get('f382') and abs(close_now - fib['f382']) / close_now < 0.02:
            confidence += 0.05
        elif fib.get('f618') and abs(close_now - fib['f618']) / close_now < 0.02:
            confidence += 0.04

    # --- rally_in_downtrend (short) ---
    # P6·22: Weekly BEARISH context REQUIRED, RSI in bounce zone [p43,p62],
    #         price within 2% BELOW EMA21, EMA21<EMA50, vol declining
    elif (weekly_trend_str in ('bearish_strong', 'bearish_weak')
          and rsif is not None and rsi_p43 <= rsif <= rsi_p62
          and ema21f < ema50f
          and ema21f * 0.98 <= close_now <= ema21f
          and vol_now < vol_avg * vol_p55):
        pattern    = "rally_in_downtrend"
        confidence = 0.68
        if vol_char == 'declining':
            confidence += 0.07  # low-vol rally = weak bounce = better short
        if weekly_trend_str == 'bearish_strong':
            confidence += 0.05  # stronger macro headwind

    # --- base_breakout (VCP) ---
    # Tight coil near highs: squeeze_on (active compression) + vol declining + price near 50d high
    elif (squeeze_on
          and _vol_character(df, n=10) == 'declining'
          and len(df) >= 50 and close_now >= float(df['close'].iloc[-50:].max()) * 0.97
          and weekly_trend_str in ('bullish', 'bearish_weak', 'unknown')):
        pattern    = "base_breakout"
        confidence = 0.70
        if wc.bb_squeeze:
            confidence += 0.05
        if vol_now > vol_avg * vol_p65:
            confidence += 0.08  # early break from base

    # --- base_breakdown (short VCP) ---
    # Tight coil near lows: squeeze_on (active compression) + vol declining + breaks to 50d low
    elif (squeeze_on
          and _vol_character(df, n=10) == 'declining'
          and len(df) >= 50 and close_now <= float(df['close'].iloc[-50:].min()) * 1.03
          and weekly_trend_str in ('bearish_strong', 'bearish_weak', 'unknown')):
        pattern    = "base_breakdown"
        confidence = 0.68
        if wc.bb_squeeze:
            confidence += 0.05
        if vol_now > vol_avg * vol_p65:
            confidence += 0.08

    # --- oversold_bounce ---
    # P6·18: RSI < rsi_p20, up day (close > prev + open < close), above EMA200,
    #         weekly ADX < 30, not BEARISH_STRONG
    elif (rsif is not None and rsif < rsi_p20
          and len(df) >= 2 and float(df['close'].iloc[-2]) < close_now
          and 'open' in df.columns and close_now > float(df['open'].iloc[-1])
          and (ema200f is None or close_now > ema200f)
          and not (wc.adx is not None and wc.adx > 30.0)
          and weekly_trend_str != 'bearish_strong'
          and vol_now > vol_avg * vol_p60):
        pattern    = "oversold_bounce"
        confidence = 0.62
        if rsif < rsi_p12:
            confidence += 0.05
        if bull_div:
            confidence += 0.08

    # --- failed_breakdown ---
    # P6·20: Price dipped below EMA21 in last 5 bars, current bar recovered above,
    #         vol > vol_p65, weekly not BEARISH_STRONG
    # NOTE: compute ema21_series first so we can gate the outer elif on recent_dip
    elif ('low' in df.columns and len(df) >= 6
          and weekly_trend_str != 'bearish_strong'
          and close_now <= recent_high  # not a clean breakout above 20d high
          and close_now > df['close'].ewm(span=21, adjust=False).mean().iloc[-1]
          and (df['close'].iloc[-5:-1] < df['close'].ewm(span=21, adjust=False).mean().iloc[-5:-1]).any()
          and vol_now > vol_avg * vol_p65):
        pattern    = "failed_breakdown"
        confidence = 0.68
        if vol_now > vol_avg * vol_p85:
            confidence += 0.07
        if weekly_trend_str == 'bullish':
            confidence += 0.05

    # --- breakout ---
    elif (close_now > recent_high
          and vol_avg > 0 and vol_now > vol_avg * vol_p72
          and vol_char != 'declining'
          and weekly_trend_str != 'bearish_strong'):
        pattern    = "breakout"
        confidence = 0.80
        if vol_now > vol_avg * vol_p85:
            confidence += 0.05
        if rsif is not None and rsif > rsi_p88:
            confidence -= 0.15
        if len(df) >= 60:
            tolerance = recent_high * 0.01
            touches = ((df["close"].iloc[-60:-1] >= recent_high - tolerance) &
                       (df["close"].iloc[-60:-1] <= recent_high + tolerance)).sum()
            if touches >= 2:
                confidence += 0.08

    # --- breakdown (short) ---
    # Close below 20d low on high volume
    elif (close_now < recent_low
          and vol_avg > 0 and vol_now > vol_avg * vol_p72
          and vol_char != 'declining'
          and weekly_trend_str not in ('bullish',)):
        pattern    = "breakdown"
        confidence = 0.78
        if vol_now > vol_avg * vol_p85:
            confidence += 0.05
        if rsif is not None and rsif < rsi_p12:
            confidence -= 0.15  # already very oversold
        if weekly_trend_str == 'bearish_strong':
            confidence += 0.08

    # --- failed_breakout (short) ---
    # P6·21: recent scipy swing high exceeded in last 3 bars, closes back below it,
    #         vol declining (< vol_p55), weekly not BULLISH
    elif (len(df) >= 64
          and weekly_trend_str not in ('bullish',)):
        highs_arr = df['high'].values[-60:].astype(float)
        swing_high_idx = argrelextrema(highs_arr, np.greater, order=5)[0]
        # Only consider swing highs established BEFORE the last 4 bars (pos < 56)
        prior_swing_idx = swing_high_idx[swing_high_idx < 56]
        if len(prior_swing_idx) > 0:
            spH = float(highs_arr[prior_swing_idx[-1]])
            exceeded_recently = (df['high'].iloc[-4:-1] > spH).any()
            back_below = close_now < spH
            vol_declining_fb = vol_now < vol_avg * vol_p55
            if exceeded_recently and back_below and vol_declining_fb:
                pattern    = "failed_breakout"
                confidence = 0.70
                if close_now < float(df['close'].iloc[-2]) * 0.97:
                    confidence += 0.05  # hard rejection

    # --- bearish_reversal (last priority — short setup, macro RED context) ---
    # P6·17: tightened — weekly RSI > 65 REQUIRED, bullish weekly context (BULLISH_EXTENDED)
    elif (daily_trend == 'bullish' and adxf > adx_p70
          and bear_div
          and vol_now > vol_avg * vol_p75
          and rsif is not None and rsif > rsi_p85
          and wc.rsi is not None and wc.rsi > 65.0
          and weekly_trend_str == 'bullish'):
        pattern    = "bearish_reversal"
        confidence = 0.65
        if wc.rsi is not None and wc.rsi > 70.0:
            confidence += 0.10
        if rsif > rsi_p93:
            confidence += 0.05

    # Ensure confidence in [0, 1]
    confidence = max(0.0, min(1.0, confidence))

    # --- Firing decision ---
    SHORT_PATTERNS = {
        "bearish_reversal", "breakdown", "rally_in_downtrend",
        "compression_break_down", "ema_rejection", "base_breakdown",
        "overbought_reversal", "failed_breakout",
    }
    BULLISH_REVERSAL_PATTERNS = {"bullish_reversal", "oversold_bounce", "failed_breakdown", "ema_reclaim"}
    bullish_pattern = pattern not in (SHORT_PATTERNS | {"no_pattern"})

    # Weekly bearish_strong penalizes long patterns (not reversal types)
    if (weekly_trend_str == 'bearish_strong'
            and bullish_pattern
            and pattern not in BULLISH_REVERSAL_PATTERNS):
        confidence = max(0.0, confidence - 0.20)

    if pattern in SHORT_PATTERNS:
        firing = confidence >= settings.ta_pattern_confidence_threshold
    elif pattern in BULLISH_REVERSAL_PATTERNS:
        firing = confidence >= settings.ta_pattern_confidence_threshold  # fire regardless of trend
    else:
        firing = confidence >= settings.ta_pattern_confidence_threshold and trend != "bearish"

    swing_high = float(recent["close"].max())
    swing_low  = float(recent["close"].min())

    direction_label = "Bearish" if pattern in SHORT_PATTERNS else ("Bullish" if trend == "bullish" else trend.capitalize())
    narrative = (
        f"{direction_label} {pattern.replace('_', ' ')} "
        f"({int(confidence * 100)}% conf): "
        f"ADX {round(adxf, 1)}, RSI {round(rsif, 1) if rsif else 'n/a'}, "
        f"vol {vol_ratio}x avg ({vol_char}). "
        f"Weekly: {weekly_trend_str}."
    )

    # weekly_state: 5-state classifier consistent with detect_pattern()
    wt = weekly_trend_str  # 'bullish' | 'bearish_strong' | 'bearish_weak' | 'unknown'
    if wt == "bullish":
        weekly_state = "BULLISH"
    elif wt == "bearish_strong":
        weekly_state = "BEARISH_STRONG"
    elif wt == "bearish_weak":
        weekly_state = "BEARISH_WEAK"
    else:
        weekly_state = "NEUTRAL"

    return FactorResult(
        factor_id="technical",
        firing=firing,
        strength=confidence,
        label=pattern,
        detail={
            "pattern": pattern,
            "confidence": confidence,
            "direction": "short" if pattern in SHORT_PATTERNS else "long",
            "trend": trend,
            "weekly_trend": weekly_trend_str,
            "weekly_state": weekly_state,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "adx": round(adxf, 2),
            "rsi": round(rsif, 2) if rsif is not None else None,
            "rsi_p40": round(rsi_p40, 2),
            "vol_character": vol_char,
            "vol_ratio": vol_ratio,
            "bull_divergence": bull_div,
            "bear_divergence": bear_div,
            "ema200": round(ema200f, 2) if ema200f else None,
            "weekly_ema8": round(wc.ema8, 2) if wc.ema8 else None,
            "weekly_ema21": round(wc.ema21, 2) if wc.ema21 else None,
            "fib_levels": fib,
        },
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

    return {"pattern": "no_pattern", "confidence": 0.0, "detail": detail}


SETUP_TAXONOMY: list[str] = [
    "pullback_in_trend", "pullback_deep", "pullback_to_structure",
    "flag_continuation", "rally_in_downtrend",
    "breakout", "breakdown", "compression_break", "compression_break_down",
    "base_breakout", "base_breakdown", "ema_reclaim", "ema_rejection",
    "bos_bullish", "bos_bearish",
    "bullish_reversal", "bearish_reversal", "overbought_reversal",
    "oversold_bounce", "failed_breakdown", "failed_breakout",
    "choch_bullish", "choch_bearish",
    "bb_mean_reversion_long", "bb_mean_reversion_short",
    "ema200_snap_long", "ema200_snap_short",
]
