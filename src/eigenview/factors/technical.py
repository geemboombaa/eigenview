from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers df.ta accessor

from eigenview.config import settings
from eigenview.factors.base import FactorResult


def score_technical(df: pd.DataFrame, ticker: str = "") -> FactorResult:
    if df is None or len(df) < 30:
        return FactorResult.no_data("technical", "insufficient price history")

    df = df.copy()
    df.ta.ema(length=21, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.bbands(length=20, append=True)
    df.ta.atr(length=14, append=True)

    last = df.iloc[-1]
    recent = df.iloc[-20:]

    ema21 = last.get("EMA_21")
    ema50 = last.get("EMA_50")
    adx = last.get("ADX_14")
    rsi = last.get("RSI_14")
    bbu = last.get("BBU_20_2.0")
    atr_last5 = df["ATRr_14"].iloc[-5:].mean()
    atr_20avg = df["ATRr_14"].iloc[-20:].mean()
    close_now = last["close"]
    vol_now = df["volume"].iloc[-1]
    vol_avg = df["volume"].iloc[-20:-1].mean()
    recent_high = recent["close"].iloc[:-1].max()

    if ema21 is None or pd.isna(ema21) or ema50 is None or pd.isna(ema50) or adx is None or pd.isna(adx):
        return FactorResult.no_data("technical", "indicator computation failed")

    if adx <= 20:
        trend = "sideways"
    elif ema21 > ema50:
        trend = "bullish"
    else:
        trend = "bearish"

    pattern = "no_pattern"
    confidence = 0.0

    if (
        not pd.isna(atr_last5)
        and not pd.isna(atr_20avg)
        and atr_20avg > 0
        and atr_last5 < atr_20avg * 0.7
        and bbu is not None
        and not pd.isna(bbu)
        and close_now > bbu
    ):
        pattern = "compression_break"
        confidence = 0.75
    elif (
        trend == "bullish"
        and rsi is not None
        and not pd.isna(rsi)
        and 40 <= rsi <= 55
        and close_now > ema21 * 0.99
    ):
        pattern = "pullback_in_trend"
        confidence = 0.70
    elif (
        not pd.isna(recent_high)
        and close_now > recent_high
        and vol_avg > 0
        and vol_now > vol_avg * 1.5
    ):
        pattern = "breakout"
        confidence = 0.80

    firing = confidence >= settings.ta_pattern_confidence_threshold and trend != "bearish"

    swing_high = float(recent["close"].max())
    swing_low = float(recent["close"].min())

    vol_ratio = round(vol_now / vol_avg, 2) if vol_avg > 0 else 0.0
    narrative = (
        f"{'Bullish' if trend == 'bullish' else trend.capitalize()} {pattern.replace('_', ' ')} pattern "
        f"({int(confidence * 100)}% confidence): "
        f"ADX {round(float(adx), 1)}, RSI {round(float(rsi), 1) if rsi and not pd.isna(rsi) else 'n/a'}, "
        f"vol ratio {vol_ratio}x avg."
    )

    return FactorResult(
        factor_id="technical",
        firing=firing,
        strength=confidence,
        label=pattern,
        detail={
            "pattern": pattern,
            "confidence": confidence,
            "trend": trend,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "adx": round(float(adx), 2),
            "rsi": round(float(rsi), 2) if rsi is not None and not pd.isna(rsi) else None,
        },
        narrative=narrative,
    )
