from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers df.ta accessor
from scipy.signal import argrelextrema

from eigenview.config import settings
from eigenview.factors.base import FactorResult


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
        rsi_p55  = float(np.percentile(_rsi, 55))
        rsi_p60  = float(np.percentile(_rsi, 60))
        rsi_p65  = float(np.percentile(_rsi, 65))
        rsi_p80  = float(np.percentile(_rsi, 80))
        rsi_p85  = float(np.percentile(_rsi, 85))
        rsi_p88  = float(np.percentile(_rsi, 88))
        rsi_p90  = float(np.percentile(_rsi, 90))
        rsi_p93  = float(np.percentile(_rsi, 93))
    else:
        rsi_p10  = 28.0
        rsi_p12  = 30.0
        rsi_p15  = 32.0
        rsi_p20  = 32.0
        rsi_p25  = 38.0
        rsi_p40  = 45.0
        rsi_p55  = 55.0
        rsi_p60  = 57.0
        rsi_p65  = 60.0
        rsi_p80  = 68.0
        rsi_p85  = 72.0
        rsi_p88  = 75.0
        rsi_p90  = 78.0
        rsi_p93  = 80.0

    adx_series = df['ADX_14'].dropna()
    if len(adx_series) >= 60:
        _adx = adx_series.tail(63).values
        # Cap sideways/trend thresholds so strongly-trending regimes don't mis-classify
        adx_p25 = min(20.0, float(np.percentile(_adx, 25)))
        adx_p40 = min(25.0, float(np.percentile(_adx, 40)))
        adx_p70 = float(np.percentile(_adx, 70))
        adx_p75 = float(np.percentile(_adx, 75))
    else:
        adx_p25 = 15.0
        adx_p40 = 20.0
        adx_p70 = 25.0
        adx_p75 = 30.0

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
    # Prior downtrend ≥20 bars, RSI bull divergence, vol spike, 2-bar confirm
    in_downtrend_20 = (ema21f < ema50f) and (adxf > adx_p25)
    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else close_now
    two_bar_confirm = (prev_close < close_now) and (vol_now > vol_avg * vol_p65)
    if (in_downtrend_20 and bull_div and vol_now > vol_avg * vol_p80 and two_bar_confirm
            and rsif is not None and rsif < rsi_p55):
        # Only fire if weekly RSI not deeply bearish (>p15 required)
        weekly_rsi_ok = wc.rsi is None or wc.rsi > rsi_p15
        if weekly_rsi_ok:
            pattern = "bullish_reversal"
            confidence = 0.70
            if vol_now > vol_avg * vol_p92:
                confidence += 0.10  # exhaustion spike bonus

    # --- overbought_reversal (short) ---
    # Bullish trend + extended RSI + rolling over on volume
    elif (daily_trend == 'bullish' and adxf > adx_p40
          and rsif is not None and rsif > rsi_p80
          and len(df) >= 2 and float(df['close'].iloc[-2]) > close_now
          and vol_now > vol_avg * vol_p60):
        pattern    = "overbought_reversal"
        confidence = 0.60
        if rsif > rsi_p88:
            confidence += 0.05
        if bear_div:
            confidence += 0.08
        if weekly_trend_str == 'bearish_strong':
            confidence += 0.05
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
    # Bearish EMA stack, RSI bounced to p40-p65, dead-cat bounce entry
    elif (daily_trend == "bearish"
          and rsif is not None and rsi_p40 <= rsif <= rsi_p65
          and close_now < ema21f * 1.01
          and close_now > ema50f * 0.92
          and weekly_trend_str in ('bearish_strong', 'bearish_weak', 'unknown')):
        pattern    = "rally_in_downtrend"
        confidence = 0.68
        if vol_char == 'declining':
            confidence += 0.07  # low-vol rally = weak bounce = better short
        if close_now > ema50f * 0.98:
            confidence += 0.05  # close to EMA50 resistance

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
    # RSI deeply oversold (p20), bouncing, not catastrophic breakdown
    elif (rsif is not None and rsif < rsi_p20
          and len(df) >= 2 and float(df['close'].iloc[-2]) < close_now  # up day
          and vol_now > vol_avg * vol_p60
          and not (wc.adx is not None and wc.adx > adx_p75)
          and (ema200f is None or close_now > ema200f * 0.82)):
        pattern    = "oversold_bounce"
        confidence = 0.62
        if rsif < rsi_p12:
            confidence += 0.05
        if bull_div:
            confidence += 0.08

    # --- failed_breakdown ---
    # Intraday broke below EMA21 but closed above it on high volume
    elif ('low' in df.columns
          and len(df) >= 2
          and float(df['low'].iloc[-1]) < ema21f
          and close_now > ema21f
          and float(df['close'].iloc[-2]) > ema21f
          and vol_now > vol_avg * vol_p72):
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
    # Price broke above resistance yesterday, closed back below today
    elif (len(df) >= 3
          and float(df['close'].iloc[-2]) > recent_high
          and close_now < recent_high
          and vol_now > vol_avg * vol_p60):
        pattern    = "failed_breakout"
        confidence = 0.70
        if close_now < float(df['close'].iloc[-2]) * 0.97:
            confidence += 0.05  # hard rejection
        if vol_now > vol_avg * vol_p80:
            confidence += 0.05

    # --- bearish_reversal (last priority — short setup, macro RED context) ---
    # Sustained uptrend + bear RSI divergence + elevated RSI + vol spike
    elif (daily_trend == 'bullish' and adxf > adx_p70
          and bear_div
          and vol_now > vol_avg * vol_p75
          and rsif is not None and rsif > rsi_p85):
        pattern    = "bearish_reversal"
        confidence = 0.65
        if weekly_trend_str == 'bearish_strong':
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
            "swing_high": swing_high,
            "swing_low": swing_low,
            "adx": round(adxf, 2),
            "rsi": round(rsif, 2) if rsif is not None else None,
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

    if len(ddf) < 30:
        return {"pattern": "no_pattern", "confidence": 0.0, "detail": {}}

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
        return {"pattern": "no_pattern", "confidence": 0.0, "detail": {}}

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

    # Vol ratio percentile for pullback ceiling
    _dp_vols = ddf['volume'].dropna().tail(64).values
    if len(_dp_vols) >= 21:
        _dp_avgs = np.array([
            float(np.mean(_dp_vols[max(0, i-20):i])) if i > 0 else float(_dp_vols[0])
            for i in range(len(_dp_vols))
        ])
        _dp_ratios = np.where(_dp_avgs > 0, _dp_vols / _dp_avgs, 1.0)
        vol_p72_dp = float(np.percentile(_dp_ratios, 72))
        vol_p35_dp = float(np.percentile(_dp_ratios, 35))
    else:
        vol_p72_dp = 1.5
        vol_p35_dp = 0.9

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

    return {"pattern": "no_pattern", "confidence": 0.0, "detail": detail}
