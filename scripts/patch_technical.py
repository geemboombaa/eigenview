"""Patch detect_pattern() in technical.py to add 6 new setups."""
import sys

src_path = "src/eigenview/factors/technical.py"

with open(src_path, "r", encoding="utf-8") as f:
    content = f.read()

# ── Fix 1: Expand vol percentile section ──────────────────────────────────────

OLD_VOL = (
    "    # Vol ratio percentile for pullback ceiling\n"
    "    _dp_vols = ddf['volume'].dropna().tail(64).values\n"
    "    if len(_dp_vols) >= 21:\n"
    "        _dp_avgs = np.array([\n"
    "            float(np.mean(_dp_vols[max(0, i-20):i])) if i > 0 else float(_dp_vols[0])\n"
    "            for i in range(len(_dp_vols))\n"
    "        ])\n"
    "        _dp_ratios = np.where(_dp_avgs > 0, _dp_vols / _dp_avgs, 1.0)\n"
    "        vol_p72_dp = float(np.percentile(_dp_ratios, 72))\n"
    "        vol_p35_dp = float(np.percentile(_dp_ratios, 35))\n"
    "    else:\n"
    "        vol_p72_dp = 1.5\n"
    "        vol_p35_dp = 0.9"
)

NEW_VOL = (
    "    # Vol ratio percentile -- used by pullback, breakout, breakdown, VCP, EMA setups\n"
    "    _dp_vols = ddf['volume'].dropna().tail(64).values\n"
    "    if len(_dp_vols) >= 21:\n"
    "        _dp_avgs = np.array([\n"
    "            float(np.mean(_dp_vols[max(0, i-20):i])) if i > 0 else float(_dp_vols[0])\n"
    "            for i in range(len(_dp_vols))\n"
    "        ])\n"
    "        _dp_ratios = np.where(_dp_avgs > 0, _dp_vols / _dp_avgs, 1.0)\n"
    "        vol_p35_dp = float(np.percentile(_dp_ratios, 35))\n"
    "        # vol_p40_dp: prior bars only so current bar can be compared against threshold\n"
    "        vol_p40_dp = float(np.percentile(_dp_ratios[:-1], 40)) if len(_dp_ratios) > 1 else 1.0\n"
    "        vol_p55_dp = float(np.percentile(_dp_ratios, 55))\n"
    "        vol_p70_dp = float(np.percentile(_dp_ratios, 70))\n"
    "        vol_p72_dp = float(np.percentile(_dp_ratios, 72))\n"
    "    else:\n"
    "        vol_p35_dp = 0.9\n"
    "        vol_p40_dp = 0.95\n"
    "        vol_p55_dp = 1.1\n"
    "        vol_p70_dp = 1.4\n"
    "        vol_p72_dp = 1.5"
)

assert OLD_VOL in content, "OLD_VOL not found in file"
content = content.replace(OLD_VOL, NEW_VOL, 1)
print("Fix 1 (vol percentile) applied")

# ── Fix 2: Add 6 pattern blocks ───────────────────────────────────────────────

OLD_TAIL = (
    '        confidence = round(min(1.0, confidence), 3)\n'
    '        return {"pattern": "pullback_in_trend", "confidence": confidence, "detail": detail}\n'
    '\n'
    '    return {"pattern": "no_pattern", "confidence": 0.0, "detail": detail}\n'
)

NEW_TAIL = '''\
        confidence = round(min(1.0, confidence), 3)
        return {"pattern": "pullback_in_trend", "confidence": confidence, "detail": detail}

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

    return {"pattern": "no_pattern", "confidence": 0.0, "detail": detail}
'''

assert OLD_TAIL in content, f"OLD_TAIL not found. Last 300 chars: {repr(content[-300:])}"
content = content.replace(OLD_TAIL, NEW_TAIL, 1)
print("Fix 2 (pattern blocks) applied")

with open(src_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Written OK. File size: {len(content)} chars")

# Verify
with open(src_path, "r", encoding="utf-8") as f:
    verify = f.read()

for term in ["vol_p40_dp", "vol_p55_dp", "vol_p70_dp", "base_breakout", "breakdown", "ema_reclaim", "ema_rejection"]:
    found = term in verify
    print(f"  {term}: {'OK' if found else 'MISSING'}")
