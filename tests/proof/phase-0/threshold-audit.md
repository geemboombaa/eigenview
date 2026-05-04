# Threshold Audit — technical.py
**Date:** 2026-05-04
**Total hardcoded thresholds found:** 48

| # | Function | Line | Expression | Indicator | Current Value | Rolling Percentile Replacement |
|---|---|---|---|---|---|---|
| 1 | `_compute_weekly_context` | 53 | `(bbu_w - bbl_w) / close_w < 0.15` | BB width ratio | 0.15 | np.percentile(bb_width_series.tail(90), 15) |
| 2 | `_weekly_trend` | 69 | `wc.adx > 25` | Weekly ADX | 25 | np.percentile(df_weekly['ADX_14'].dropna().tail(90), 70) |
| 3 | `_vol_character` | 87 | `rel < -0.05` | Vol slope ratio | -0.05 | fixed directional heuristic — not a percentile candidate |
| 4 | `_vol_character` | 89 | `rel > 0.05` | Vol slope ratio | 0.05 | fixed directional heuristic — not a percentile candidate |
| 5 | `score_technical` | 200 | `adxf <= 20` | ADX | 20 | np.percentile(df['ADX_14'].dropna().tail(90), 40) |
| 6 | `score_technical` | 232 | `adxf > 15` | ADX (in downtrend check) | 15 | np.percentile(df['ADX_14'].dropna().tail(90), 25) |
| 7 | `score_technical` | 234 | `vol_now > vol_avg * 1.3` | Vol ratio | 1.3 | np.percentile(vol_ratio_series.tail(90), 65) |
| 8 | `score_technical` | 235 | `vol_now > vol_avg * 1.8` | Vol ratio | 1.8 | np.percentile(vol_ratio_series.tail(90), 80) |
| 9 | `score_technical` | 236 | `rsif < 55` | RSI | 55 | np.percentile(df['RSI_14'].dropna().tail(90), 55) |
| 10 | `score_technical` | 238 | `wc.rsi > 30` | Weekly RSI | 30 | np.percentile(df_weekly['RSI_14'].dropna().tail(90), 15) |
| 11 | `score_technical` | 242 | `vol_now > vol_avg * 2.5` | Vol ratio | 2.5 | np.percentile(vol_ratio_series.tail(90), 92) |
| 12 | `score_technical` | 247 | `adxf > 20` | ADX | 20 | np.percentile(df['ADX_14'].dropna().tail(90), 40) |
| 13 | `score_technical` | 248 | `rsif > 68` | RSI | 68 | np.percentile(df['RSI_14'].dropna().tail(90), 80) |
| 14 | `score_technical` | 250 | `vol_now > vol_avg * 1.2` | Vol ratio | 1.2 | np.percentile(vol_ratio_series.tail(90), 60) |
| 15 | `score_technical` | 253 | `rsif > 75` | RSI | 75 | np.percentile(df['RSI_14'].dropna().tail(90), 88) |
| 16 | `score_technical` | 259 | `vol_now > vol_avg * 1.8` | Vol ratio | 1.8 | np.percentile(vol_ratio_series.tail(90), 80) |
| 17 | `score_technical` | 265 | `atr_last5 < atr_20avg * 0.7` | ATR ratio | 0.7 | np.percentile(atr_ratio_series.tail(90), 20) |
| 18 | `score_technical` | 268 | `vol_now > vol_avg * 1.5` | Vol ratio | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 19 | `score_technical` | 269 | `rsif < 78` | RSI (extended guard) | 78 | np.percentile(df['RSI_14'].dropna().tail(90), 90) |
| 20 | `score_technical` | 274 | `vol_now > vol_avg * 2.0` | Vol ratio | 2.0 | np.percentile(vol_ratio_series.tail(90), 85) |
| 21 | `score_technical` | 282 | `atr_last5 < atr_20avg * 0.7` | ATR ratio | 0.7 | np.percentile(atr_ratio_series.tail(90), 20) |
| 22 | `score_technical` | 285 | `vol_now > vol_avg * 1.5` | Vol ratio | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 23 | `score_technical` | 286 | `rsif > 22` | RSI (oversold guard) | 22 | np.percentile(df['RSI_14'].dropna().tail(90), 10) |
| 24 | `score_technical` | 291 | `vol_now > vol_avg * 2.0` | Vol ratio | 2.0 | np.percentile(vol_ratio_series.tail(90), 85) |
| 25 | `score_technical` | 303 | `vol_now > vol_avg * 1.1` | Vol ratio | 1.1 | np.percentile(vol_ratio_series.tail(90), 55) |
| 26 | `score_technical` | 315 | `vol_now > vol_avg * 1.1` | Vol ratio | 1.1 | np.percentile(vol_ratio_series.tail(90), 55) |
| 27 | `score_technical` | 321 | `vol_now > vol_avg * 1.5` | Vol ratio | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 28 | `score_technical` | 327 | `rsif >= 38` | RSI lower bound | 38 | np.percentile(df['RSI_14'].dropna().tail(90), 25) |
| 29 | `score_technical` | 327 | `rsif <= 57` | RSI upper bound | 57 | np.percentile(df['RSI_14'].dropna().tail(90), 55) |
| 30 | `score_technical` | 328 | `close_now > ema21f * 0.99` | Price/EMA21 ratio | 0.99 | fixed structural margin — not a percentile candidate |
| 31 | `score_technical` | 329 | `close_now < ema50f * 1.08` | Price/EMA50 ratio | 1.08 | fixed structural margin — not a percentile candidate |
| 32 | `score_technical` | 335 | `close_now < ema50f * 1.02` | Price/EMA50 ratio | 1.02 | fixed structural margin — not a percentile candidate |
| 33 | `score_technical` | 345 | `rsif >= 43` | RSI lower bound | 43 | np.percentile(df['RSI_14'].dropna().tail(90), 40) |
| 34 | `score_technical` | 345 | `rsif <= 62` | RSI upper bound | 62 | np.percentile(df['RSI_14'].dropna().tail(90), 65) |
| 35 | `score_technical` | 347 | `close_now < ema21f * 1.01` | Price/EMA21 ratio | 1.01 | fixed structural margin — not a percentile candidate |
| 36 | `score_technical` | 348 | `close_now > ema50f * 0.92` | Price/EMA50 ratio | 0.92 | fixed structural margin — not a percentile candidate |
| 37 | `score_technical` | 360 | `atr_last5 < atr_20avg * 0.65` | ATR ratio | 0.65 | np.percentile(atr_ratio_series.tail(90), 15) |
| 38 | `score_technical` | 362 | `close_now >= float(df['close'].iloc[-50:].max()) * 0.97` | Price vs 50d high | 0.97 | fixed structural proximity — not a percentile candidate |
| 39 | `score_technical` | 368 | `vol_now > vol_avg * 1.3` | Vol ratio | 1.3 | np.percentile(vol_ratio_series.tail(90), 65) |
| 40 | `score_technical` | 373 | `atr_last5 < atr_20avg * 0.65` | ATR ratio | 0.65 | np.percentile(atr_ratio_series.tail(90), 15) |
| 41 | `score_technical` | 376 | `close_now <= float(df['close'].iloc[-50:].min()) * 1.03` | Price vs 50d low | 1.03 | fixed structural proximity — not a percentile candidate |
| 42 | `score_technical` | 383 | `vol_now > vol_avg * 1.3` | Vol ratio | 1.3 | np.percentile(vol_ratio_series.tail(90), 65) |
| 43 | `score_technical` | 387 | `rsif < 32` | RSI oversold | 32 | np.percentile(df['RSI_14'].dropna().tail(90), 20) |
| 44 | `score_technical` | 389 | `vol_now > vol_avg * 1.2` | Vol ratio | 1.2 | np.percentile(vol_ratio_series.tail(90), 60) |
| 45 | `score_technical` | 391 | `wc.adx > 30` | Weekly ADX | 30 | np.percentile(df_weekly['ADX_14'].dropna().tail(90), 75) |
| 46 | `score_technical` | 391 | `close_now > ema200f * 0.82` | Price/EMA200 ratio | 0.82 | fixed catastrophic-breakdown guard — not a percentile candidate |
| 47 | `score_technical` | 394 | `rsif < 25` | RSI deep oversold | 25 | np.percentile(df['RSI_14'].dropna().tail(90), 12) |
| 48 | `score_technical` | 406 | `vol_now > vol_avg * 1.5` | Vol ratio | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 49 | `score_technical` | 409 | `vol_now > vol_avg * 2.0` | Vol ratio | 2.0 | np.percentile(vol_ratio_series.tail(90), 85) |
| 50 | `score_technical` | 416 | `vol_now > vol_avg * 1.5` | Vol ratio | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 51 | `score_technical` | 421 | `vol_now > vol_avg * 2.0` | Vol ratio | 2.0 | np.percentile(vol_ratio_series.tail(90), 85) |
| 52 | `score_technical` | 423 | `rsif > 75` | RSI extended | 75 | np.percentile(df['RSI_14'].dropna().tail(90), 88) |
| 53 | `score_technical` | 429 | `touches >= 2` | Support touch count | 2 | fixed structural minimum — not a percentile candidate |
| 54 | `score_technical` | 435 | `vol_now > vol_avg * 1.5` | Vol ratio | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 55 | `score_technical` | 440 | `vol_now > vol_avg * 2.0` | Vol ratio | 2.0 | np.percentile(vol_ratio_series.tail(90), 85) |
| 56 | `score_technical` | 442 | `rsif < 25` | RSI oversold penalty | 25 | np.percentile(df['RSI_14'].dropna().tail(90), 12) |
| 57 | `score_technical` | 452 | `vol_now > vol_avg * 1.2` | Vol ratio | 1.2 | np.percentile(vol_ratio_series.tail(90), 60) |
| 58 | `score_technical` | 455 | `close_now < float(df['close'].iloc[-2]) * 0.97` | Price rejection pct | 0.97 | fixed structural margin — not a percentile candidate |
| 59 | `score_technical` | 457 | `vol_now > vol_avg * 1.8` | Vol ratio | 1.8 | np.percentile(vol_ratio_series.tail(90), 80) |
| 60 | `score_technical` | 462 | `adxf > 25` | ADX trend strength | 25 | np.percentile(df['ADX_14'].dropna().tail(90), 70) |
| 61 | `score_technical` | 465 | `vol_now > vol_avg * 1.6` | Vol ratio | 1.6 | np.percentile(vol_ratio_series.tail(90), 75) |
| 62 | `score_technical` | 465 | `rsif > 72` | RSI extended | 72 | np.percentile(df['RSI_14'].dropna().tail(90), 85) |
| 63 | `score_technical` | 471 | `rsif > 80` | RSI extreme | 80 | np.percentile(df['RSI_14'].dropna().tail(90), 93) |
| 64 | `_classify_weekly_state` | 565 | `rsi_f > 70` | Weekly RSI extended | 70 | np.percentile(df_weekly['RSI_14'].dropna().tail(90), 82) |
| 65 | `_classify_weekly_state` | 569 | `gap_pct < 0.02` | EMA gap ratio | 0.02 | fixed structural dead-zone — not a percentile candidate |
| 66 | `_classify_weekly_state` | 571 | `adx_f > 25` | Weekly ADX | 25 | np.percentile(df_weekly['ADX_14'].dropna().tail(90), 70) |
| 67 | `detect_pattern` | 658 | `adxf < 15` | ADX sideways threshold | 15 | np.percentile(df['ADX_14'].dropna().tail(90), 25) |
| 68 | `detect_pattern` | 692 | `rsif <= rsi_p40` | RSI (already adaptive) | p40 | already rolling percentile (rsi_p40) |
| 69 | `detect_pattern` | 693 | `rsif >= 30` | RSI absolute floor | 30 | np.percentile(df['RSI_14'].dropna().tail(90), 15) |
| 70 | `detect_pattern` | 694 | `close_now >= ema21f * 0.96` | Price/EMA21 lower bound | 0.96 | fixed structural margin — not a percentile candidate |
| 71 | `detect_pattern` | 695 | `close_now <= ema21f * 1.04` | Price/EMA21 upper bound | 1.04 | fixed structural margin — not a percentile candidate |
| 72 | `detect_pattern` | 696 | `vol_ratio < 1.5` | Vol ratio ceiling | 1.5 | np.percentile(vol_ratio_series.tail(90), 72) |
| 73 | `detect_pattern` | 699 | `vol_ratio < 0.9` | Vol ratio quiet | 0.9 | np.percentile(vol_ratio_series.tail(90), 35) |
| 74 | `detect_pattern` | 701 | `close_now >= ema21f * 0.99` | Price/EMA21 proximity | 0.99 | fixed structural margin — not a percentile candidate |

---

## Summary by Indicator

| Indicator | Count | Lines (approx) |
|---|---|---|
| Vol ratio (vol_now / vol_avg) | 26 | 234, 235, 242, 250, 259, 268, 274, 285, 291, 303, 315, 321, 368, 383, 389, 406, 409, 416, 421, 435, 440, 452, 457, 465, 696, 699 |
| RSI | 19 | 236, 238, 248, 253, 269, 286, 327×2, 345×2, 387, 391, 394, 423, 442, 462, 465, 471, 693 |
| ADX | 7 | 69, 200, 232, 247, 462, 571, 658 |
| ATR ratio (atr_last5 / atr_20avg) | 4 | 265, 282, 360, 373 |
| Price/EMA ratio (structural margins) | 11 | 328, 329, 335, 347, 348, 362, 376, 391, 455, 694, 695, 701 |
| BB width ratio | 1 | 53 |
| Weekly RSI | 2 | 238, 565 |
| EMA gap ratio | 1 | 569 |

## Notes

- **Already adaptive:** `rsi_p40` at line 648–651 in `detect_pattern` is already computed as a rolling 90-day percentile. Line 692 is not a hardcoded threshold — it's the result of that computation. Listed for completeness but flagged accordingly.
- **Not percentile candidates:** Price/EMA ratio margins (0.96, 0.99, 1.01, 1.02, 1.04, 1.08, 0.92, 0.82, 0.97), price vs 50d high/low proximity (0.97, 1.03), EMA gap dead-zone (0.02), vol slope direction heuristic (±0.05), support touch count minimum (≥2), rejection magnitude (0.97). These are structural definition thresholds — replacing them with percentiles would distort the pattern semantics.
- **Highest-impact replacements:** RSI oversold (32 → p20), RSI extended (68/75 → p80/p88), ADX sideways cutoff (20 → p40), ATR compression (0.7/0.65 → p20/p15), vol breakout confirmation (1.5 → p72).
